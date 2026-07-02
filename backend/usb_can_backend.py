from __future__ import annotations

import argparse
import ctypes
import sys
import time
import traceback
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bridge_protocol import decode_message, encode_message
from models import CanFrame
from usb_can_b_driver import BITRATE_TIMING, DEV_USBCAN2, VciCanObj, VciInitConfig

DEFAULT_DLL_PATH = Path(r"C:\Program Files (x86)\USB_CAN TOOL\ControlCAN.dll")
ERROR_RESULT = 0xFFFFFFFF


class UsbCanBackend:
    def __init__(self) -> None:
        self.dll: ctypes.WinDLL | None = None
        self.opened = False
        self.device_type = DEV_USBCAN2
        self.device_index = 0
        self.channel = 0
        self.rx_cache: list[CanFrame] = []

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        cmd = request.get("cmd")
        if cmd == "ping":
            return {"ok": True, "message": "pong"}
        if cmd == "open":
            return self.open(request)
        if cmd == "close":
            self.close()
            return {"ok": True}
        if cmd == "send":
            return self.send(request)
        if cmd == "read":
            return self.read(request)
        if cmd == "status":
            return {"ok": True, "opened": self.opened}
        return {"ok": False, "error": f"Unknown command: {cmd}"}

    def open(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.opened:
            self.close()

        dll_path = Path(str(request.get("dll_path") or DEFAULT_DLL_PATH))
        self.device_type = int(request.get("device_type", DEV_USBCAN2))
        self.device_index = int(request.get("device_index", 0))
        self.channel = int(request.get("channel", 0))
        bitrate = int(request.get("bitrate", 500_000))

        if bitrate not in BITRATE_TIMING:
            return {"ok": False, "error": f"Unsupported bitrate: {bitrate}"}
        if not dll_path.exists():
            return {"ok": False, "error": f"ControlCAN.dll not found: {dll_path}"}

        try:
            self.dll = ctypes.WinDLL(str(dll_path))
            bind_functions(self.dll)

            result = self.dll.VCI_OpenDevice(self.device_type, self.device_index, 0)
            if result != 1:
                self.dll = None
                return {"ok": False, "error": format_result("VCI_OpenDevice", result)}

            timing0, timing1 = BITRATE_TIMING[bitrate]
            init_config = VciInitConfig(
                AccCode=0x80000008,
                AccMask=0xFFFFFFFF,
                Reserved=0,
                Filter=1,
                Timing0=timing0,
                Timing1=timing1,
                Mode=0,
            )

            result = self.dll.VCI_InitCAN(self.device_type, self.device_index, self.channel, ctypes.byref(init_config))
            if result != 1:
                self._close_device_only()
                return {"ok": False, "error": format_result("VCI_InitCAN", result)}

            result = self.dll.VCI_ClearBuffer(self.device_type, self.device_index, self.channel)
            if result != 1:
                self._close_device_only()
                return {"ok": False, "error": format_result("VCI_ClearBuffer", result)}

            result = self.dll.VCI_StartCAN(self.device_type, self.device_index, self.channel)
            if result != 1:
                self._close_device_only()
                return {"ok": False, "error": format_result("VCI_StartCAN", result)}

            self.opened = True
            return {"ok": True}
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            self._close_device_only()
            return {"ok": False, "error": str(exc)}

    def close(self) -> None:
        self._close_device_only()

    def send(self, request: dict[str, Any]) -> dict[str, Any]:
        if not self.opened or self.dll is None:
            return {"ok": False, "error": "Backend is not open."}
        if bool(request.get("extended", False)):
            return {"ok": False, "error": "Extended CAN frames are not supported."}
        if bool(request.get("rtr", False)):
            return {"ok": False, "error": "RTR CAN frames are not supported."}

        try:
            can_id = int(request["can_id"])
            data = bytes.fromhex(str(request.get("data", "")))
        except Exception as exc:
            return {"ok": False, "error": f"Invalid send payload: {exc}"}

        if len(data) > 8:
            return {"ok": False, "error": "CAN data length must be <= 8 bytes."}
        if not 0 <= can_id <= 0x7FF:
            return {"ok": False, "error": f"Standard CAN ID must be in 0x000..0x7FF: 0x{can_id:X}"}

        frame = VciCanObj()
        frame.ID = can_id
        frame.TimeStamp = 0
        frame.TimeFlag = 0
        frame.SendType = 0
        frame.RemoteFlag = 0
        frame.ExternFlag = 0
        frame.DataLen = len(data)
        for index, byte in enumerate(data):
            frame.Data[index] = byte

        result = self.dll.VCI_Transmit(self.device_type, self.device_index, self.channel, ctypes.byref(frame), 1)
        if result != 1:
            return {"ok": False, "error": format_result("VCI_Transmit", result)}
        return {"ok": True}

    def read(self, request: dict[str, Any]) -> dict[str, Any]:
        if not self.opened or self.dll is None:
            return {"ok": False, "error": "Backend is not open."}
        if self.rx_cache:
            return {"ok": True, "frame": frame_to_response(self.rx_cache.pop(0))}

        timeout_ms = int(request.get("timeout_ms", 0))
        receive_len = 2500
        receive_array = (VciCanObj * receive_len)()
        result = self.dll.VCI_Receive(
            self.device_type,
            self.device_index,
            self.channel,
            receive_array,
            receive_len,
            timeout_ms,
        )
        if result == ERROR_RESULT:
            return {"ok": False, "error": format_result("VCI_Receive", result)}
        if result == 0:
            return {"ok": True, "frame": None}

        now = time.time()
        for index in range(int(result)):
            raw = receive_array[index]
            dlc = min(int(raw.DataLen), 8)
            data = bytes(raw.Data[i] for i in range(dlc))
            self.rx_cache.append(
                CanFrame(
                    can_id=int(raw.ID),
                    data=data,
                    dlc=dlc,
                    extended=bool(raw.ExternFlag),
                    rtr=bool(raw.RemoteFlag),
                    timestamp=now,
                )
            )
        return {"ok": True, "frame": frame_to_response(self.rx_cache.pop(0)) if self.rx_cache else None}

    def _close_device_only(self) -> None:
        if self.dll is not None and self.opened:
            self.dll.VCI_CloseDevice(self.device_type, self.device_index)
        elif self.dll is not None:
            try:
                self.dll.VCI_CloseDevice(self.device_type, self.device_index)
            except Exception:
                pass
        self.opened = False
        self.dll = None
        self.rx_cache.clear()


def bind_functions(dll: ctypes.WinDLL) -> None:
    dll.VCI_OpenDevice.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32]
    dll.VCI_OpenDevice.restype = ctypes.c_uint32
    dll.VCI_CloseDevice.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    dll.VCI_CloseDevice.restype = ctypes.c_uint32
    dll.VCI_InitCAN.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(VciInitConfig)]
    dll.VCI_InitCAN.restype = ctypes.c_uint32
    dll.VCI_ClearBuffer.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32]
    dll.VCI_ClearBuffer.restype = ctypes.c_uint32
    dll.VCI_StartCAN.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32]
    dll.VCI_StartCAN.restype = ctypes.c_uint32
    dll.VCI_Transmit.argtypes = [
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.POINTER(VciCanObj),
        ctypes.c_uint32,
    ]
    dll.VCI_Transmit.restype = ctypes.c_uint32
    dll.VCI_Receive.argtypes = [
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.POINTER(VciCanObj),
        ctypes.c_ulong,
        ctypes.c_int,
    ]
    dll.VCI_Receive.restype = ctypes.c_uint32


def format_result(function_name: str, result: int) -> str:
    if result == ERROR_RESULT:
        return f"{function_name} failed: device does not exist."
    return f"{function_name} failed with return value {result}."


def frame_to_response(frame: CanFrame) -> dict[str, Any]:
    return {
        "can_id": frame.can_id,
        "data": frame.data[: frame.dlc].hex(),
        "dlc": frame.dlc,
        "extended": frame.extended,
        "rtr": frame.rtr,
        "timestamp": frame.timestamp,
    }


def serve_stdio() -> int:
    backend = UsbCanBackend()
    try:
        for line in sys.stdin:
            try:
                request = decode_message(line)
                response = backend.handle(request)
            except Exception as exc:
                traceback.print_exc(file=sys.stderr)
                response = {"ok": False, "error": str(exc)}
            sys.stdout.write(encode_message(response))
            sys.stdout.flush()
    finally:
        backend.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="USB-CAN-B 32-bit backend.")
    parser.add_argument("--stdio", action="store_true")
    args = parser.parse_args()
    if not args.stdio:
        print("This backend is intended to run with --stdio.", file=sys.stderr)
        return 2
    return serve_stdio()


if __name__ == "__main__":
    raise SystemExit(main())
