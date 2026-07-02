from __future__ import annotations

import ctypes
import re
import struct
import time
from pathlib import Path

from can_driver import CanDriver
from models import CanFrame

DEV_USBCAN2 = 4
DEFAULT_DLL_NAME = "ControlCAN.dll"
DEFAULT_INSTALL_DLL = Path(r"C:\Program Files (x86)\USB_CAN TOOL\ControlCAN.dll")
NOT_IMPLEMENTED_MESSAGE = "USB-CAN-B real driver is not implemented yet. Please provide SDK/DLL/manual."

BITRATE_TIMING: dict[int, tuple[int, int]] = {
    10_000: (0x31, 0x1C),
    20_000: (0x18, 0x1C),
    40_000: (0x87, 0xFF),
    50_000: (0x09, 0x1C),
    80_000: (0x83, 0xFF),
    100_000: (0x04, 0x1C),
    125_000: (0x03, 0x1C),
    200_000: (0x81, 0xFA),
    250_000: (0x01, 0x1C),
    400_000: (0x80, 0xFA),
    500_000: (0x00, 0x1C),
    666_000: (0x80, 0xB6),
    800_000: (0x00, 0x16),
    1_000_000: (0x00, 0x14),
}


class VciBoardInfo(ctypes.Structure):
    _fields_ = [
        ("hw_Version", ctypes.c_ushort),
        ("fw_Version", ctypes.c_ushort),
        ("dr_Version", ctypes.c_ushort),
        ("in_Version", ctypes.c_ushort),
        ("irq_Num", ctypes.c_ushort),
        ("can_Num", ctypes.c_ubyte),
        ("str_Serial_Num", ctypes.c_char * 20),
        ("str_hw_Type", ctypes.c_char * 40),
        ("Reserved", ctypes.c_ushort * 4),
    ]


class VciCanObj(ctypes.Structure):
    _fields_ = [
        ("ID", ctypes.c_uint),
        ("TimeStamp", ctypes.c_uint),
        ("TimeFlag", ctypes.c_ubyte),
        ("SendType", ctypes.c_ubyte),
        ("RemoteFlag", ctypes.c_ubyte),
        ("ExternFlag", ctypes.c_ubyte),
        ("DataLen", ctypes.c_ubyte),
        ("Data", ctypes.c_ubyte * 8),
        ("Reserved", ctypes.c_ubyte * 3),
    ]


class VciInitConfig(ctypes.Structure):
    _fields_ = [
        ("AccCode", ctypes.c_uint32),
        ("AccMask", ctypes.c_uint32),
        ("Reserved", ctypes.c_uint32),
        ("Filter", ctypes.c_ubyte),
        ("Timing0", ctypes.c_ubyte),
        ("Timing1", ctypes.c_ubyte),
        ("Mode", ctypes.c_ubyte),
    ]


class UsbCanBDriver(CanDriver):
    def __init__(self, dll_path: str | None = None, device_type: int = DEV_USBCAN2) -> None:
        self._explicit_dll_path = Path(dll_path) if dll_path else None
        self._device_type = device_type
        self._dll: ctypes.WinDLL | None = None
        self._dll_path: Path | None = None
        self._opened = False
        self._device_index = 0
        self._channel = 0
        self._rx_cache: list[CanFrame] = []

    def list_devices(self) -> list[str]:
        try:
            dll = self._load_dll()
        except RuntimeError:
            return ["USB-CAN-B Device 0"]

        if not hasattr(dll, "VCI_FindUsbDevice2"):
            return ["USB-CAN-B Device 0"]

        infos = (VciBoardInfo * 50)()
        count = int(dll.VCI_FindUsbDevice2(infos))
        if count <= 0:
            return ["USB-CAN-B Device 0"]

        devices: list[str] = []
        for index in range(min(count, 50)):
            serial = _decode_c_string(bytes(infos[index].str_Serial_Num))
            hw_type = _decode_c_string(bytes(infos[index].str_hw_Type))
            suffix = " ".join(part for part in (hw_type, f"SN={serial}" if serial else "") if part)
            devices.append(f"USB-CAN-B Device {index}" + (f" ({suffix})" if suffix else ""))
        return devices

    def open(self, device: str, channel: int, bitrate: int) -> None:
        timing0, timing1 = self._timing_for_bitrate(bitrate)
        self._device_index = self._parse_device_index(device)
        self._channel = channel
        dll = self._load_dll()

        result = dll.VCI_OpenDevice(self._device_type, self._device_index, 0)
        if result != 1:
            raise RuntimeError(self._format_result("VCI_OpenDevice", result))

        init_config = VciInitConfig(
            AccCode=0x80000008,
            AccMask=0xFFFFFFFF,
            Reserved=0,
            Filter=1,
            Timing0=timing0,
            Timing1=timing1,
            Mode=0,
        )

        try:
            result = dll.VCI_InitCAN(
                self._device_type,
                self._device_index,
                self._channel,
                ctypes.byref(init_config),
            )
            if result != 1:
                raise RuntimeError(self._format_result("VCI_InitCAN", result))

            result = dll.VCI_ClearBuffer(self._device_type, self._device_index, self._channel)
            if result != 1:
                raise RuntimeError(self._format_result("VCI_ClearBuffer", result))

            result = dll.VCI_StartCAN(self._device_type, self._device_index, self._channel)
            if result != 1:
                raise RuntimeError(self._format_result("VCI_StartCAN", result))
        except Exception:
            dll.VCI_CloseDevice(self._device_type, self._device_index)
            self._opened = False
            raise

        self._opened = True

    def close(self) -> None:
        if self._dll is not None and self._opened:
            self._dll.VCI_CloseDevice(self._device_type, self._device_index)
        self._opened = False
        self._rx_cache.clear()

    def is_open(self) -> bool:
        return self._opened

    def send_frame(self, can_id: int, data: bytes, extended: bool = False, rtr: bool = False) -> None:
        if not self._opened or self._dll is None:
            raise RuntimeError("USB-CAN-B driver is not open.")
        if extended:
            raise ValueError("USB-CAN-B driver is configured for standard 11-bit CAN IDs only.")
        if rtr:
            raise ValueError("USB-CAN-B driver is configured for data frames only, not RTR.")
        if not 0 <= can_id <= 0x7FF:
            raise ValueError(f"Standard CAN ID must be in 0x000..0x7FF: 0x{can_id:X}")
        if len(data) > 8:
            raise ValueError("CAN data length must be <= 8 bytes.")

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

        result = self._dll.VCI_Transmit(
            self._device_type,
            self._device_index,
            self._channel,
            ctypes.byref(frame),
            1,
        )
        if result != 1:
            raise RuntimeError(self._format_result("VCI_Transmit", result))

    def read_frame(self, timeout_ms: int = 0) -> CanFrame | None:
        if not self._opened or self._dll is None:
            return None

        if self._rx_cache:
            return self._rx_cache.pop(0)

        receive_len = 2500
        receive_array = (VciCanObj * receive_len)()
        result = self._dll.VCI_Receive(
            self._device_type,
            self._device_index,
            self._channel,
            receive_array,
            receive_len,
            int(timeout_ms),
        )

        if result == 0xFFFFFFFF:
            raise RuntimeError(self._format_result("VCI_Receive", result))
        if result == 0:
            return None

        now = time.time()
        for index in range(int(result)):
            raw = receive_array[index]
            dlc = min(int(raw.DataLen), 8)
            data = bytes(raw.Data[i] for i in range(dlc))
            self._rx_cache.append(
                CanFrame(
                    can_id=int(raw.ID),
                    data=data,
                    dlc=dlc,
                    extended=bool(raw.ExternFlag),
                    rtr=bool(raw.RemoteFlag),
                    timestamp=now,
                )
            )

        if self._rx_cache:
            return self._rx_cache.pop(0)
        return None

    def _load_dll(self) -> ctypes.WinDLL:
        if self._dll is not None:
            return self._dll

        dll_path = self._resolve_dll_path()
        dll_arch = dll_architecture_bits(dll_path)
        python_arch = python_architecture_bits()
        if dll_arch is not None and dll_arch != python_arch:
            raise RuntimeError(
                f"Cannot load {dll_path}: DLL is {dll_arch}-bit but Python is {python_arch}-bit. "
                "Use matching 32-bit Python or provide a 64-bit ControlCAN.dll."
            )

        windll = getattr(ctypes, "WinDLL", None)
        if windll is None:
            raise RuntimeError("USB-CAN-B ControlCAN.dll can only be loaded on Windows.")

        try:
            self._dll = windll(str(dll_path))
        except OSError as exc:
            raise RuntimeError(f"Failed to load {dll_path}: {exc}") from exc

        self._dll_path = dll_path
        self._bind_functions(self._dll)
        return self._dll

    def _resolve_dll_path(self) -> Path:
        candidates = []
        if self._explicit_dll_path is not None:
            candidates.append(self._explicit_dll_path)
        candidates.extend(
            [
                Path.cwd() / DEFAULT_DLL_NAME,
                Path(__file__).resolve().parent / DEFAULT_DLL_NAME,
                DEFAULT_INSTALL_DLL,
            ]
        )

        for candidate in candidates:
            if candidate.exists():
                return candidate

        raise RuntimeError(
            f"{NOT_IMPLEMENTED_MESSAGE} Expected {DEFAULT_DLL_NAME} beside the tool or at {DEFAULT_INSTALL_DLL}."
        )

    def _bind_functions(self, dll: ctypes.WinDLL) -> None:
        dll.VCI_OpenDevice.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32]
        dll.VCI_OpenDevice.restype = ctypes.c_uint32

        dll.VCI_CloseDevice.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        dll.VCI_CloseDevice.restype = ctypes.c_uint32

        dll.VCI_InitCAN.argtypes = [
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.POINTER(VciInitConfig),
        ]
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

        if hasattr(dll, "VCI_FindUsbDevice2"):
            dll.VCI_FindUsbDevice2.argtypes = [ctypes.POINTER(VciBoardInfo)]
            dll.VCI_FindUsbDevice2.restype = ctypes.c_uint32

    def _timing_for_bitrate(self, bitrate: int) -> tuple[int, int]:
        try:
            return BITRATE_TIMING[bitrate]
        except KeyError as exc:
            supported = ", ".join(str(value) for value in sorted(BITRATE_TIMING))
            raise ValueError(f"Unsupported USB-CAN-B bitrate {bitrate}. Supported: {supported}") from exc

    def _parse_device_index(self, device: str) -> int:
        match = re.search(r"Device\s+(\d+)", device)
        if match:
            return int(match.group(1))
        if device.strip().isdigit():
            return int(device.strip())
        return 0

    def _format_result(self, function_name: str, result: int) -> str:
        if result == 0xFFFFFFFF:
            return f"{function_name} failed: device does not exist."
        return f"{function_name} failed with return value {result}."


def _decode_c_string(value: bytes) -> str:
    return value.split(b"\0", 1)[0].decode(errors="replace").strip()


def python_architecture_bits() -> int:
    return 64 if ctypes.sizeof(ctypes.c_void_p) == 8 else 32


def dll_architecture_bits(path: Path) -> int | None:
    try:
        with path.open("rb") as file:
            header = file.read(0x1000)
    except OSError:
        return None

    if len(header) < 0x40 or header[:2] != b"MZ":
        return None

    pe_offset = struct.unpack_from("<I", header, 0x3C)[0]
    if pe_offset + 6 > len(header):
        return None

    machine = struct.unpack_from("<H", header, pe_offset + 4)[0]
    if machine == 0x14C:
        return 32
    if machine == 0x8664:
        return 64
    return None
