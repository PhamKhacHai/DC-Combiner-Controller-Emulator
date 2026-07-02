from __future__ import annotations

import argparse
import ctypes
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from usb_can_b_driver import (
    VciBoardInfo,
    UsbCanBDriver,
    dll_architecture_bits,
    python_architecture_bits,
)

DEFAULT_DEVICE_TYPES = [
    ("VCI_USBCAN1", 3),
    ("VCI_USBCAN2", 4),
]


def parse_usb_device_types(header_path: Path) -> list[tuple[str, int]]:
    if not header_path.exists():
        return DEFAULT_DEVICE_TYPES

    pattern = re.compile(r"^\s*#define\s+(VCI_[A-Za-z0-9_]*CAN[A-Za-z0-9_]*)\s+(\d+)\b")
    device_types: list[tuple[str, int]] = []

    for line in header_path.read_text(errors="ignore").splitlines():
        match = pattern.match(line)
        if not match:
            continue
        name = match.group(1)
        value = int(match.group(2))
        if "USB" in name or name in {"VCI_CAN232", "VCI_CANLITE"}:
            device_types.append((name, value))

    return merge_device_types(DEFAULT_DEVICE_TYPES + device_types)


def merge_device_types(device_types: list[tuple[str, int]]) -> list[tuple[str, int]]:
    merged: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for name, value in device_types:
        key = (name, value)
        if key in seen:
            continue
        seen.add(key)
        merged.append((name, value))
    return merged


def print_find_usb_device2(dll: ctypes.WinDLL) -> None:
    try:
        find_usb_device2 = dll.VCI_FindUsbDevice2
    except AttributeError:
        print("VCI_FindUsbDevice2: not exported by this DLL")
        return

    find_usb_device2.argtypes = [ctypes.POINTER(VciBoardInfo)]
    find_usb_device2.restype = ctypes.c_uint32

    infos = (VciBoardInfo * 50)()
    result = int(find_usb_device2(infos))
    print(f"VCI_FindUsbDevice2 ret={result}")
    for index in range(min(result, 50)):
        serial = bytes(infos[index].str_Serial_Num).split(b"\0", 1)[0].decode(errors="replace")
        hw_type = bytes(infos[index].str_hw_Type).split(b"\0", 1)[0].decode(errors="replace")
        print(
            f"  device[{index}] can_num={infos[index].can_Num} "
            f"serial={serial!r} hw_type={hw_type!r}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug VCI_OpenDevice for USB-CAN-B.")
    parser.add_argument("--dll", help="Optional explicit ControlCAN.dll path.")
    parser.add_argument("--header", default=str(PROJECT_ROOT / "ControlCAN.h"))
    parser.add_argument("--max-index", type=int, default=3)
    args = parser.parse_args()

    driver = UsbCanBDriver(dll_path=args.dll)
    dll_path = driver._resolve_dll_path()
    python_bits = python_architecture_bits()
    dll_bits = dll_architecture_bits(dll_path)

    print(f"Python executable: {sys.executable}")
    print(f"Python architecture: {python_bits}-bit")
    print(f"DLL path: {dll_path}")
    print(f"DLL architecture: {dll_bits or 'unknown'}-bit")

    try:
        dll = driver._load_dll()
    except RuntimeError as exc:
        print(f"DLL load: failed: {exc}")
        return 1
    print("DLL load: OK")

    print_find_usb_device2(dll)

    header_path = Path(args.header)
    device_types = parse_usb_device_types(header_path)
    print(f"ControlCAN.h: {header_path}")
    print("DeviceTypes to try:")
    for name, value in device_types:
        print(f"  {name}={value}")

    for name, device_type in device_types:
        for device_index in range(args.max_index + 1):
            result = int(dll.VCI_OpenDevice(device_type, device_index, 0))
            print(f"OpenDevice type={device_type} ({name}) index={device_index} ret={result}")
            if result == 1:
                print(f"OPEN OK type={device_type} ({name}) index={device_index}")
                close_result = int(dll.VCI_CloseDevice(device_type, device_index))
                print(f"CloseDevice type={device_type} index={device_index} ret={close_result}")
                return 0

    print("OPEN FAILED for all tested DeviceType/DeviceIndex combinations.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
