from __future__ import annotations

from can_driver import CanDriver
from models import (
    BoardStatus,
    BootloaderEraseAppResponse,
    BootloaderFlashLayoutResponse,
    BootloaderFlashSelfTestResponse,
    BootloaderInfoResponse,
    BootloaderSimpleUpdateResponse,
    BootloaderStartUpdateResponse,
    BootloaderVerifyCrcResponse,
    BootloaderWriteChunkResponse,
    CanFrame,
    DiagnosticCounterResponse,
    DiagnosticErrorResponse,
    DiagnosticResetResponse,
    HeartbeatStatus,
)
from protocol import (
    CAN_BITRATE,
    COMMAND_CLEAR_FAULT_MASK,
    build_bootloader_abort_update_frame,
    build_bootloader_enter_frame,
    build_bootloader_erase_app_frame,
    build_bootloader_finish_update_frame,
    build_bootloader_get_flash_layout_frame,
    build_bootloader_get_info_frame,
    build_bootloader_reset_to_app_frame,
    build_bootloader_run_flash_self_test_frame,
    build_bootloader_start_update_frame,
    build_bootloader_verify_crc_frame,
    build_bootloader_write_chunk_frame,
    build_command_frame,
    build_command_mask,
    build_diag_read_counter_frame,
    build_diag_reset_all_frame,
    decode_bootloader_erase_app_frame,
    decode_bootloader_flash_layout_frame,
    decode_bootloader_flash_self_test_frame,
    decode_bootloader_info_frame,
    decode_bootloader_simple_update_frame,
    decode_bootloader_start_update_frame,
    decode_bootloader_verify_crc_frame,
    decode_bootloader_write_chunk_frame,
    decode_diag_response_frame,
    decode_heartbeat_frame,
    decode_status_frame,
    validate_node_id,
)

DiagnosticResponse = DiagnosticCounterResponse | DiagnosticResetResponse | DiagnosticErrorResponse


class ControllerSimulator:
    def __init__(self, driver: CanDriver) -> None:
        self.driver = driver
        self.node_id = 0
        self.selected_groups: list[int] = []
        self.connected = False
        self.last_status: BoardStatus | None = None
        self.last_heartbeat: HeartbeatStatus | None = None
        self.last_diag_response: DiagnosticResponse | None = None
        self.diag_response_history: list[DiagnosticResponse] = []
        self.last_boot_info_response: BootloaderInfoResponse | None = None
        self.boot_info_response_history: list[BootloaderInfoResponse] = []
        self.last_flash_layout_response: BootloaderFlashLayoutResponse | None = None
        self.flash_layout_response_history: list[BootloaderFlashLayoutResponse] = []
        self.last_flash_self_test_response: BootloaderFlashSelfTestResponse | None = None
        self.flash_self_test_response_history: list[BootloaderFlashSelfTestResponse] = []
        self.last_start_update_response: BootloaderStartUpdateResponse | None = None
        self.start_update_response_history: list[BootloaderStartUpdateResponse] = []
        self.last_erase_app_response: BootloaderEraseAppResponse | None = None
        self.erase_app_response_history: list[BootloaderEraseAppResponse] = []
        self.last_write_chunk_response: BootloaderWriteChunkResponse | None = None
        self.write_chunk_response_history: list[BootloaderWriteChunkResponse] = []
        self.last_verify_crc_response: BootloaderVerifyCrcResponse | None = None
        self.verify_crc_response_history: list[BootloaderVerifyCrcResponse] = []
        self.last_simple_update_response: BootloaderSimpleUpdateResponse | None = None
        self.simple_update_response_history: list[BootloaderSimpleUpdateResponse] = []

    def connect(self, device: str, channel: int = 0, bitrate: int = CAN_BITRATE) -> None:
        self.driver.open(device, channel, bitrate)
        self.connected = self.driver.is_open()

    def disconnect(self) -> None:
        self.driver.close()
        self.connected = False

    def set_node_id(self, node_id: int) -> None:
        self.node_id = validate_node_id(node_id)

    def set_selected_groups(self, groups: list[int]) -> None:
        build_command_mask(groups)
        self.selected_groups = list(groups)

    def get_command_mask(self) -> int:
        return build_command_mask(self.selected_groups)

    def send_once(self) -> CanFrame:
        return self.send_command(self.get_command_mask(), 0)

    def send_command(self, command_mask: int, command_flags: int = 0) -> CanFrame:
        if not self.connected or not self.driver.is_open():
            raise RuntimeError("CAN is not connected.")

        frame = build_command_frame(self.node_id, command_mask, command_flags)
        self.driver.send_frame(frame.can_id, frame.data, frame.extended, frame.rtr)
        return frame

    def off_all(self) -> CanFrame:
        self.selected_groups = []
        return self.send_command(0x00, 0x00)

    def clear_fault(self) -> CanFrame:
        return self.send_command(0x00, COMMAND_CLEAR_FAULT_MASK)

    def send_diag_read_counter(self, counter_id: int, group_index: int) -> CanFrame:
        if not self.connected or not self.driver.is_open():
            raise RuntimeError("CAN is not connected.")

        frame = build_diag_read_counter_frame(self.node_id, counter_id, group_index)
        self.driver.send_frame(frame.can_id, frame.data, frame.extended, frame.rtr)
        return frame

    def send_diag_reset_all(self) -> CanFrame:
        if not self.connected or not self.driver.is_open():
            raise RuntimeError("CAN is not connected.")

        frame = build_diag_reset_all_frame(self.node_id)
        self.driver.send_frame(frame.can_id, frame.data, frame.extended, frame.rtr)
        return frame

    def send_enter_bootloader(self) -> CanFrame:
        if not self.connected or not self.driver.is_open():
            raise RuntimeError("CAN is not connected.")

        frame = build_bootloader_enter_frame(self.node_id)
        self.driver.send_frame(frame.can_id, frame.data, frame.extended, frame.rtr)
        return frame

    def send_get_boot_info(self) -> CanFrame:
        if not self.connected or not self.driver.is_open():
            raise RuntimeError("CAN is not connected.")

        frame = build_bootloader_get_info_frame(self.node_id)
        self.driver.send_frame(frame.can_id, frame.data, frame.extended, frame.rtr)
        return frame

    def send_get_flash_layout(self) -> CanFrame:
        if not self.connected or not self.driver.is_open():
            raise RuntimeError("CAN is not connected.")

        frame = build_bootloader_get_flash_layout_frame(self.node_id)
        self.driver.send_frame(frame.can_id, frame.data, frame.extended, frame.rtr)
        return frame

    def send_run_flash_self_test(self) -> CanFrame:
        if not self.connected or not self.driver.is_open():
            raise RuntimeError("CAN is not connected.")

        frame = build_bootloader_run_flash_self_test_frame(self.node_id)
        self.driver.send_frame(frame.can_id, frame.data, frame.extended, frame.rtr)
        return frame

    def send_start_update(self, app_size: int, flags: int = 0) -> CanFrame:
        if not self.connected or not self.driver.is_open():
            raise RuntimeError("CAN is not connected.")

        frame = build_bootloader_start_update_frame(self.node_id, app_size, flags)
        self.driver.send_frame(frame.can_id, frame.data, frame.extended, frame.rtr)
        return frame

    def send_erase_app(self) -> CanFrame:
        if not self.connected or not self.driver.is_open():
            raise RuntimeError("CAN is not connected.")

        frame = build_bootloader_erase_app_frame(self.node_id)
        self.driver.send_frame(frame.can_id, frame.data, frame.extended, frame.rtr)
        return frame

    def send_write_chunk(self, sequence: int, payload: bytes) -> CanFrame:
        if not self.connected or not self.driver.is_open():
            raise RuntimeError("CAN is not connected.")

        frame = build_bootloader_write_chunk_frame(self.node_id, sequence, payload)
        self.driver.send_frame(frame.can_id, frame.data, frame.extended, frame.rtr)
        return frame

    def send_verify_crc(self, crc32_value: int) -> CanFrame:
        if not self.connected or not self.driver.is_open():
            raise RuntimeError("CAN is not connected.")

        frame = build_bootloader_verify_crc_frame(self.node_id, crc32_value)
        self.driver.send_frame(frame.can_id, frame.data, frame.extended, frame.rtr)
        return frame

    def send_finish_update(self) -> CanFrame:
        if not self.connected or not self.driver.is_open():
            raise RuntimeError("CAN is not connected.")

        frame = build_bootloader_finish_update_frame(self.node_id)
        self.driver.send_frame(frame.can_id, frame.data, frame.extended, frame.rtr)
        return frame

    def send_abort_update(self) -> CanFrame:
        if not self.connected or not self.driver.is_open():
            raise RuntimeError("CAN is not connected.")

        frame = build_bootloader_abort_update_frame(self.node_id)
        self.driver.send_frame(frame.can_id, frame.data, frame.extended, frame.rtr)
        return frame

    def send_reset_to_app(self) -> CanFrame:
        if not self.connected or not self.driver.is_open():
            raise RuntimeError("CAN is not connected.")

        frame = build_bootloader_reset_to_app_frame(self.node_id)
        self.driver.send_frame(frame.can_id, frame.data, frame.extended, frame.rtr)
        return frame

    def poll_rx(self) -> list[CanFrame]:
        frames: list[CanFrame] = []
        for _ in range(32):
            frame = self.driver.read_frame(timeout_ms=0)
            if frame is None:
                break
            frames.append(frame)

            status = decode_status_frame(frame, self.node_id)
            if status is not None:
                self.last_status = status
                continue

            heartbeat = decode_heartbeat_frame(frame, self.node_id)
            if heartbeat is not None:
                self.last_heartbeat = heartbeat
                continue

            diag_response = decode_diag_response_frame(frame, self.node_id)
            if diag_response is not None:
                self.last_diag_response = diag_response
                self.diag_response_history.append(diag_response)
                continue

            boot_info_response = decode_bootloader_info_frame(frame, self.node_id)
            if boot_info_response is not None:
                self.last_boot_info_response = boot_info_response
                self.boot_info_response_history.append(boot_info_response)
                continue

            flash_layout_response = decode_bootloader_flash_layout_frame(frame, self.node_id)
            if flash_layout_response is not None:
                self.last_flash_layout_response = flash_layout_response
                self.flash_layout_response_history.append(flash_layout_response)
                continue

            flash_self_test_response = decode_bootloader_flash_self_test_frame(frame, self.node_id)
            if flash_self_test_response is not None:
                self.last_flash_self_test_response = flash_self_test_response
                self.flash_self_test_response_history.append(flash_self_test_response)
                continue

            start_update_response = decode_bootloader_start_update_frame(frame, self.node_id)
            if start_update_response is not None:
                self.last_start_update_response = start_update_response
                self.start_update_response_history.append(start_update_response)
                continue

            erase_app_response = decode_bootloader_erase_app_frame(frame, self.node_id)
            if erase_app_response is not None:
                self.last_erase_app_response = erase_app_response
                self.erase_app_response_history.append(erase_app_response)
                continue

            write_chunk_response = decode_bootloader_write_chunk_frame(frame, self.node_id)
            if write_chunk_response is not None:
                self.last_write_chunk_response = write_chunk_response
                self.write_chunk_response_history.append(write_chunk_response)
                continue

            verify_crc_response = decode_bootloader_verify_crc_frame(frame, self.node_id)
            if verify_crc_response is not None:
                self.last_verify_crc_response = verify_crc_response
                self.verify_crc_response_history.append(verify_crc_response)
                continue

            simple_update_response = decode_bootloader_simple_update_frame(frame, self.node_id)
            if simple_update_response is not None:
                self.last_simple_update_response = simple_update_response
                self.simple_update_response_history.append(simple_update_response)

        return frames
