from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from usb_can_b_driver import UsbCanBDriver, dll_architecture_bits, python_architecture_bits


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Python and ControlCAN.dll bitness.")
    parser.add_argument(
        "--dll",
        help="Optional explicit ControlCAN.dll path. Defaults to the same resolution order used by UsbCanBDriver.",
    )
    args = parser.parse_args()

    python_bits = python_architecture_bits()
    print(f"Python executable: {sys.executable}")
    print(f"Python architecture: {python_bits}-bit")

    driver = UsbCanBDriver(dll_path=args.dll)
    try:
        dll_path = driver._resolve_dll_path()
    except RuntimeError as exc:
        print(f"DLL path: not found")
        print(f"Conclusion: cannot load USB-CAN-B driver. {exc}")
        return 1

    dll_bits = dll_architecture_bits(dll_path)
    print(f"DLL path: {dll_path}")
    print(f"DLL architecture: {dll_bits or 'unknown'}-bit")

    if dll_bits is not None and dll_bits != python_bits:
        print("Conclusion: cannot load. DLL and Python architectures do not match.")
        return 1

    try:
        driver._load_dll()
    except RuntimeError as exc:
        print(f"Conclusion: DLL architecture matches, but load failed: {exc}")
        return 1

    print("Conclusion: DLL can be loaded by this Python process.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
