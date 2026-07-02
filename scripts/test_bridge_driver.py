from __future__ import annotations

import argparse
import time

from bridge_can_driver import BridgeCanDriver
from protocol import build_command_frame, format_can_id, format_hex_data


def print_frame(direction: str, can_id: int, data: bytes) -> None:
    print(f"{direction} ID={format_can_id(can_id)} DLC={len(data)} DATA={format_hex_data(data)}")


def poll_rx(driver: BridgeCanDriver, duration_s: float) -> None:
    deadline = time.time() + duration_s
    while time.time() < deadline:
        frame = driver.read_frame(timeout_ms=0)
        if frame is None:
            time.sleep(0.02)
            continue
        print(
            f"RX ID={format_can_id(frame.can_id)} DLC={frame.dlc} "
            f"DATA={format_hex_data(frame.data)} EXT={frame.extended} RTR={frame.rtr}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Manual USB-CAN-B bridge smoke test.")
    parser.add_argument("--python32")
    parser.add_argument("--dll")
    parser.add_argument("--node-id", type=int, default=0)
    parser.add_argument("--channel", type=int, default=0)
    parser.add_argument("--bitrate", type=int, default=500_000)
    parser.add_argument("--send-group1", action="store_true")
    parser.add_argument("--rx-seconds", type=float, default=1.0)
    args = parser.parse_args()

    print("WARNING: Close the original USB CAN Tool before running this script.")
    print("WARNING: Test OFF ALL first and verify CAN_H/CAN_L/GND wiring.")

    driver = BridgeCanDriver(python32_path=args.python32, dll_path=args.dll)
    driver.open("USB-CAN-B Bridge Device 0", args.channel, args.bitrate)
    try:
        off_frame = build_command_frame(args.node_id, 0x00, 0x00)
        driver.send_frame(off_frame.can_id, off_frame.data)
        print_frame("TX", off_frame.can_id, off_frame.data)
        poll_rx(driver, args.rx_seconds)

        if args.send_group1:
            group1_frame = build_command_frame(args.node_id, 0x01, 0x00)
            driver.send_frame(group1_frame.can_id, group1_frame.data)
            print_frame("TX", group1_frame.can_id, group1_frame.data)
            poll_rx(driver, args.rx_seconds)
    finally:
        driver.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
