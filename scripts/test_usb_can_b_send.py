from __future__ import annotations

import argparse
import time

from protocol import build_command_frame, format_can_id, format_hex_data
from usb_can_b_driver import UsbCanBDriver


def print_frame(direction: str, can_id: int, data: bytes) -> None:
    print(f"{direction} ID={format_can_id(can_id)} DLC={len(data)} DATA={format_hex_data(data)}")


def poll_rx(driver: UsbCanBDriver, duration_s: float) -> None:
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
    parser = argparse.ArgumentParser(description="Manual USB-CAN-B smoke test for DC Combiner.")
    parser.add_argument("--device", default="USB-CAN-B Device 0")
    parser.add_argument("--channel", type=int, default=0)
    parser.add_argument("--bitrate", type=int, default=500_000)
    parser.add_argument("--node-id", type=int, default=0)
    parser.add_argument("--send-group1", action="store_true")
    parser.add_argument("--rx-seconds", type=float, default=1.0)
    args = parser.parse_args()

    print("WARNING: Run only after CAN_H/CAN_L/GND are wired correctly.")
    print("WARNING: Bitrate must match firmware. Test OFF ALL first.")

    driver = UsbCanBDriver()
    driver.open(args.device, args.channel, args.bitrate)
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
