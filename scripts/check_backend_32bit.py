from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKEND = PROJECT_ROOT / "backend" / "usb_can_backend.py"
DEFAULT_DLL = Path(r"C:\Program Files (x86)\USB_CAN TOOL\ControlCAN.dll")


def main() -> int:
    print(f"Current Python: {sys.executable}")
    print(f"Current Python architecture: {struct.calcsize('P') * 8}-bit")
    print(f"Backend script: {DEFAULT_BACKEND} exists={DEFAULT_BACKEND.exists()}")
    print(f"Official DLL: {DEFAULT_DLL} exists={DEFAULT_DLL.exists()}")

    python32 = os.environ.get("USB_CAN_BACKEND_PYTHON32")
    if not python32:
        print("USB_CAN_BACKEND_PYTHON32 is not set.")
        print(r'Set it with: setx USB_CAN_BACKEND_PYTHON32 "C:\Path\To\Python32\python.exe"')
        return 1

    print(f"USB_CAN_BACKEND_PYTHON32={python32}")
    arch_cmd = [
        python32,
        "-c",
        'import struct, sys; print(sys.executable); print(struct.calcsize("P") * 8)',
    ]
    arch_result = subprocess.run(arch_cmd, capture_output=True, text=True, timeout=5)
    print("Backend Python architecture check stdout:")
    print(arch_result.stdout.strip())
    if arch_result.returncode != 0:
        print("Backend Python architecture check stderr:")
        print(arch_result.stderr.strip())
        return arch_result.returncode
    if "32" not in arch_result.stdout.splitlines()[-1:]:
        print("Backend Python is not 32-bit.")
        return 1

    process = subprocess.Popen(
        [python32, str(DEFAULT_BACKEND), "--stdio"],
        cwd=str(PROJECT_ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    try:
        process.stdin.write(json.dumps({"cmd": "ping"}) + "\n")
        process.stdin.flush()
        line = process.stdout.readline()
        print(f"Backend ping response: {line.strip()}")
        response = json.loads(line)
        if response.get("ok") is True and response.get("message") == "pong":
            print("Backend ping OK.")
            return 0
        print("Backend ping failed.")
        return 1
    finally:
        try:
            process.stdin.write(json.dumps({"cmd": "close"}) + "\n")
            process.stdin.flush()
        except Exception:
            pass
        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
