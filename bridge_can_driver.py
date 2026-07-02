from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import TextIO

from bridge_protocol import decode_message, encode_message, frame_from_dict, make_request
from can_driver import CanDriver
from models import CanFrame

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_BACKEND_SCRIPT = PROJECT_ROOT / "backend" / "usb_can_backend.py"
DEFAULT_DLL_PATH = Path(r"C:\Program Files (x86)\USB_CAN TOOL\ControlCAN.dll")
DEFAULT_DEVICE_TYPE = 4
DEFAULT_DEVICE_INDEX = 0


class BridgeCanDriver(CanDriver):
    def __init__(
        self,
        python32_path: str | None = None,
        backend_script_path: str | None = None,
        dll_path: str | None = None,
        device_type: int = DEFAULT_DEVICE_TYPE,
        device_index: int = DEFAULT_DEVICE_INDEX,
        response_timeout_s: float = 2.0,
    ) -> None:
        self.python32_path = python32_path or os.environ.get("USB_CAN_BACKEND_PYTHON32")
        self.backend_script_path = Path(backend_script_path or DEFAULT_BACKEND_SCRIPT)
        self.dll_path = Path(dll_path or os.environ.get("USB_CAN_BACKEND_DLL", str(DEFAULT_DLL_PATH)))
        self.device_type = device_type
        self.device_index = device_index
        self.response_timeout_s = response_timeout_s

        self._process: subprocess.Popen[str] | None = None
        self._responses: queue.Queue[dict[str, object]] = queue.Queue()
        self._stderr_lines: queue.Queue[str] = queue.Queue()
        self._opened = False
        self._lock = threading.Lock()

    def list_devices(self) -> list[str]:
        return [f"USB-CAN-B Bridge Device {self.device_index}"]

    def open(self, device: str, channel: int, bitrate: int) -> None:
        with self._lock:
            self._ensure_backend_started()
            response = self._request_unlocked(make_request("ping"))
            if not response.get("ok"):
                raise RuntimeError(f"Backend ping failed: {response.get('error', response)}")

            response = self._request_unlocked(
                make_request(
                    "open",
                    device=device,
                    device_type=self.device_type,
                    device_index=self.device_index,
                    channel=channel,
                    bitrate=bitrate,
                    dll_path=str(self.dll_path),
                )
            )
            if not response.get("ok"):
                self._opened = False
                raise RuntimeError(str(response.get("error", "Backend open failed.")))
            self._opened = True

    def close(self) -> None:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                try:
                    self._request_unlocked(make_request("close"), timeout_s=1.0)
                except Exception:
                    pass
                self._process.terminate()
                try:
                    self._process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=1.0)
            self._process = None
            self._opened = False

    def is_open(self) -> bool:
        return self._opened and self._process is not None and self._process.poll() is None

    def send_frame(self, can_id: int, data: bytes, extended: bool = False, rtr: bool = False) -> None:
        if not self.is_open():
            raise RuntimeError("USB-CAN-B bridge is not open.")
        if extended:
            raise ValueError("USB-CAN-B bridge supports standard 11-bit CAN IDs only.")
        if rtr:
            raise ValueError("USB-CAN-B bridge supports data frames only, not RTR.")
        if len(data) > 8:
            raise ValueError("CAN data length must be <= 8 bytes.")

        with self._lock:
            response = self._request_unlocked(
                make_request(
                    "send",
                    can_id=can_id,
                    data=bytes(data).hex(),
                    extended=extended,
                    rtr=rtr,
                )
            )
        if not response.get("ok"):
            raise RuntimeError(str(response.get("error", "Backend send failed.")))

    def read_frame(self, timeout_ms: int = 0) -> CanFrame | None:
        if not self.is_open():
            return None
        with self._lock:
            response = self._request_unlocked(make_request("read", timeout_ms=timeout_ms), timeout_s=0.5)
        if not response.get("ok"):
            raise RuntimeError(str(response.get("error", "Backend read failed.")))
        frame = response.get("frame")
        if frame is None:
            return None
        if not isinstance(frame, dict):
            raise RuntimeError("Backend read returned invalid frame payload.")
        return frame_from_dict(frame)

    def _ensure_backend_started(self) -> None:
        if self.python32_path is None:
            raise RuntimeError(
                "Bridge mode requires 32-bit Python path. "
                "Set USB_CAN_BACKEND_PYTHON32 or configure python32_path."
            )
        if not self.backend_script_path.exists():
            raise RuntimeError(f"Backend script not found: {self.backend_script_path}")
        if self._process is not None and self._process.poll() is None:
            return

        self._process = subprocess.Popen(
            [self.python32_path, str(self.backend_script_path), "--stdio"],
            cwd=str(PROJECT_ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        if self._process.stdout is None or self._process.stdin is None:
            raise RuntimeError("Failed to open backend stdio pipes.")

        threading.Thread(target=self._read_stdout_loop, args=(self._process.stdout,), daemon=True).start()
        if self._process.stderr is not None:
            threading.Thread(target=self._read_stderr_loop, args=(self._process.stderr,), daemon=True).start()

    def _request_unlocked(self, message: dict[str, object], timeout_s: float | None = None) -> dict[str, object]:
        process = self._process
        if process is None or process.stdin is None:
            raise RuntimeError("Backend process is not running.")
        if process.poll() is not None:
            self._opened = False
            raise RuntimeError(f"Backend process exited with code {process.returncode}. {self._last_stderr()}")

        process.stdin.write(encode_message(message))
        process.stdin.flush()

        try:
            response = self._responses.get(timeout=timeout_s or self.response_timeout_s)
        except queue.Empty as exc:
            raise RuntimeError(f"Backend response timeout. {self._last_stderr()}") from exc

        if process.poll() is not None and not response:
            self._opened = False
            raise RuntimeError(f"Backend process exited with code {process.returncode}. {self._last_stderr()}")
        return response

    def _read_stdout_loop(self, stdout: TextIO) -> None:
        for line in stdout:
            try:
                self._responses.put(decode_message(line))
            except Exception as exc:
                self._responses.put({"ok": False, "error": f"Invalid backend JSON: {exc}"})

    def _read_stderr_loop(self, stderr: TextIO) -> None:
        for line in stderr:
            self._stderr_lines.put(line.rstrip())

    def _last_stderr(self) -> str:
        latest: list[str] = []
        while True:
            try:
                latest.append(self._stderr_lines.get_nowait())
            except queue.Empty:
                break
        if not latest:
            return ""
        return "Backend stderr: " + " | ".join(latest[-5:])
