import os
import subprocess
import sys
from pathlib import Path

import pytest

from bridge_can_driver import BridgeCanDriver


def test_bridge_requires_python32_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("USB_CAN_BACKEND_PYTHON32", raising=False)
    driver = BridgeCanDriver()
    with pytest.raises(RuntimeError, match="32-bit Python path"):
        driver.open("USB-CAN-B Bridge Device 0", 0, 500000)


def test_bridge_backend_ping_with_current_python() -> None:
    project_root = Path(__file__).resolve().parents[1]
    backend = project_root / "backend" / "usb_can_backend.py"
    process = subprocess.Popen(
        [sys.executable, str(backend), "--stdio"],
        cwd=str(project_root),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    try:
        process.stdin.write('{"cmd":"ping"}\n')
        process.stdin.flush()
        assert process.stdout.readline().strip() == '{"ok":true,"message":"pong"}'
    finally:
        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
