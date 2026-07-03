from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections import deque
from typing import Deque

from models import CanFrame
from protocol import (
    APP_MAX_SIZE_BYTES,
    BOOTLOADER_CMD_ABORT_UPDATE,
    BOOTLOADER_CMD_CHECK_APP_FLASH_CRC,
    BOOTLOADER_CMD_ERASE_APP,
    BOOTLOADER_CMD_FINISH_UPDATE,
    BOOTLOADER_CMD_GET_APP_SIZE_INFO,
    BOOTLOADER_CMD_GET_APP_STATUS_SUMMARY,
    BOOTLOADER_CMD_GET_APP_STORED_CRC,
    BOOTLOADER_CMD_GET_FLASH_LAYOUT,
    BOOTLOADER_CMD_GET_BOOT_INFO,
    BOOTLOADER_CMD_GET_METADATA_VERSION_INFO,
    BOOTLOADER_CMD_RESET_TO_APP,
    BOOTLOADER_CMD_RUN_FLASH_SELF_TEST,
    BOOTLOADER_CMD_START_UPDATE,
    BOOTLOADER_CMD_VERIFY_CRC,
    BOOTLOADER_CMD_WRITE_CHUNK,
    BOOTLOADER_CRC_SOURCE_METADATA,
    BOOTLOADER_CRC_SOURCE_NONE,
    BOOTLOADER_ENTER_MAGIC_1,
    BOOTLOADER_ENTER_MAGIC_2,
    BOOTLOADER_FLASH_STATUS_BAD_MAGIC,
    BOOTLOADER_FLASH_STATUS_ADDRESS_RANGE_ERROR,
    BOOTLOADER_RESP_FLASH_SELF_TEST,
    BOOTLOADER_RESP_ABORT_UPDATE,
    BOOTLOADER_RESP_ERASE_APP,
    BOOTLOADER_RESP_FINISH_UPDATE,
    BOOTLOADER_RESP_GET_FLASH_LAYOUT,
    BOOTLOADER_INFO_FLAG_COMPUTED_AVAILABLE,
    BOOTLOADER_INFO_FLAG_CRC_MATCH,
    BOOTLOADER_INFO_FLAG_STORED_AVAILABLE,
    BOOTLOADER_INFO_FLAG_VALUE_AVAILABLE,
    BOOTLOADER_INFO_SOURCE_LEGACY_BLANK,
    BOOTLOADER_INFO_SOURCE_METADATA,
    BOOTLOADER_INFO_SOURCE_NO_VALID_APP,
    BOOTLOADER_METADATA_STATE_BLANK,
    BOOTLOADER_METADATA_STATE_IN_PROGRESS,
    BOOTLOADER_METADATA_STATE_INVALID,
    BOOTLOADER_METADATA_STATE_VALID,
    BOOTLOADER_REQUEST_ID_BASE,
    BOOTLOADER_RESP_APP_FLASH_CRC,
    BOOTLOADER_RESP_APP_SIZE_INFO,
    BOOTLOADER_RESP_APP_STATUS_SUMMARY,
    BOOTLOADER_RESP_APP_STORED_CRC,
    BOOTLOADER_RESP_RESET_TO_APP,
    BOOTLOADER_RESP_GET_BOOT_INFO,
    BOOTLOADER_RESP_START_UPDATE,
    BOOTLOADER_RESP_METADATA_VERSION_INFO,
    BOOTLOADER_RESP_VERIFY_CRC,
    BOOTLOADER_RESP_WRITE_CHUNK,
    BOOTLOADER_STATUS_OK,
    BOOTLOADER_UPDATE_STATE_CRC_OK,
    BOOTLOADER_UPDATE_STATE_ERASED,
    BOOTLOADER_UPDATE_STATE_ERROR,
    BOOTLOADER_UPDATE_STATE_FINISHED,
    BOOTLOADER_UPDATE_STATE_IDLE,
    BOOTLOADER_UPDATE_STATE_STARTED,
    BOOTLOADER_UPDATE_STATE_WRITE_COMPLETE,
    BOOTLOADER_UPDATE_STATE_WRITING,
    BOOTLOADER_UPDATE_STATUS_ADDRESS_RANGE_ERROR,
    BOOTLOADER_UPDATE_STATUS_APP_INVALID,
    BOOTLOADER_UPDATE_STATUS_BAD_MAGIC,
    BOOTLOADER_UPDATE_STATUS_BAD_SEQUENCE,
    BOOTLOADER_UPDATE_STATUS_BAD_STATE,
    BOOTLOADER_UPDATE_STATUS_CRC_MISMATCH,
    BOOTLOADER_UPDATE_STATUS_OK,
    BOOTLOADER_UPDATE_STATUS_SIZE_ERROR,
    DIAG_CMD_READ_COUNTER,
    DIAG_CMD_RESET_ALL_COUNTERS,
    DIAG_COUNTER_CAN_COMMAND_RX,
    DIAG_COUNTER_CAN_TX,
    DIAG_COUNTER_CONTACTOR_CLOSE,
    DIAG_COUNTER_CONTACTOR_OPEN,
    DIAG_COUNTER_DIAG_ERROR,
    DIAG_COUNTER_DIAG_REQUEST,
    DIAG_GROUP_GLOBAL,
    DIAG_REQUEST_ID_BASE,
    DIAG_RESET_MAGIC_1,
    DIAG_RESET_MAGIC_2,
    DIAG_RESP_ERROR,
    DIAG_RESP_READ_COUNTER,
    DIAG_RESP_RESET_ALL_COUNTERS,
    DIAG_STATUS_BAD_DLC,
    DIAG_STATUS_INVALID_COMMAND,
    DIAG_STATUS_INVALID_COUNTER_ID,
    DIAG_STATUS_INVALID_GROUP,
    DIAG_STATUS_OK,
    DIAG_STATUS_RESET_MAGIC_INVALID,
    GLOBAL_CAN_ONLINE_MASK,
    GLOBAL_DIAG_COUNTERS,
    GROUP_ALL_MASK,
    GROUP_COUNT,
    GROUP_DIAG_COUNTERS,
    diag_response_id,
    feedback_mask_from_command_mask,
    heartbeat_id,
    is_global_counter,
    is_group_counter,
    bootloader_response_id,
    crc32_ieee,
    status_id,
)


class CanDriver(ABC):
    @abstractmethod
    def list_devices(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def open(self, device: str, channel: int, bitrate: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_open(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def send_frame(self, can_id: int, data: bytes, extended: bool = False, rtr: bool = False) -> None:
        raise NotImplementedError

    @abstractmethod
    def read_frame(self, timeout_ms: int = 0) -> CanFrame | None:
        raise NotImplementedError


class MockCanDriver(CanDriver):
    def __init__(self) -> None:
        self._is_open = False
        self._tx_frames: list[CanFrame] = []
        self._rx_queue: Deque[CanFrame] = deque()
        self._node_id = 0
        self._rx_count = 0
        self._heartbeat_sequence = 0
        self._output_mask = 0
        self._group_counters: list[dict[int, int]] = []
        self._global_counters: dict[int, int] = {}
        self._boot_update_state = BOOTLOADER_UPDATE_STATE_IDLE
        self._boot_update_app_size = 0
        self._boot_update_expected_seq = 0
        self._boot_update_data = bytearray()
        self._boot_update_crc_ok = False
        self._boot_flash_app_data = bytearray()
        self._boot_metadata_state = BOOTLOADER_METADATA_STATE_BLANK
        self._boot_metadata_version = 0x00010000
        self._boot_metadata_app_size = 0
        self._boot_metadata_crc32 = 0
        self._boot_app_valid = True
        self._reset_diag_counters()

    @property
    def tx_frames(self) -> list[CanFrame]:
        return list(self._tx_frames)

    def list_devices(self) -> list[str]:
        return ["Mock CAN Device"]

    def open(self, device: str, channel: int, bitrate: int) -> None:
        self._is_open = True
        self._rx_queue.clear()
        self._tx_frames.clear()
        self._rx_count = 0
        self._heartbeat_sequence = 0
        self._output_mask = 0
        self._reset_diag_counters()
        self._reset_bootloader_update_state()
        self._enqueue_status(0, node_id=self._node_id)
        self._enqueue_heartbeat(node_id=self._node_id)

    def close(self) -> None:
        self._is_open = False
        self._rx_queue.clear()

    def is_open(self) -> bool:
        return self._is_open

    def send_frame(self, can_id: int, data: bytes, extended: bool = False, rtr: bool = False) -> None:
        if not self._is_open:
            raise RuntimeError("CAN driver is not open.")

        frame = CanFrame(
            can_id=can_id,
            data=bytes(data),
            dlc=len(data),
            extended=extended,
            rtr=rtr,
            timestamp=time.time(),
        )
        self._tx_frames.append(frame)

        if extended or rtr or len(data) < 1:
            return

        if 0x500 <= can_id <= 0x507:
            self._handle_command_frame(can_id, data)
            return

        if DIAG_REQUEST_ID_BASE <= can_id <= DIAG_REQUEST_ID_BASE + 7:
            self._handle_diag_request_frame(can_id, data)
            return

        if BOOTLOADER_REQUEST_ID_BASE <= can_id <= BOOTLOADER_REQUEST_ID_BASE + 7:
            self._handle_bootloader_request_frame(can_id, data)
            return

    def read_frame(self, timeout_ms: int = 0) -> CanFrame | None:
        if not self._is_open:
            return None
        if self._rx_queue:
            return self._rx_queue.popleft()
        return None

    def _enqueue_status(self, command_mask: int, node_id: int) -> None:
        feedback_mask = feedback_mask_from_command_mask(command_mask)
        data = bytes(
            [
                command_mask & GROUP_ALL_MASK,
                feedback_mask & 0xFF,
                (feedback_mask >> 8) & 0xFF,
                0x00,
                GLOBAL_CAN_ONLINE_MASK,
                0x00,
                0x00,
                0x00,
            ]
        )
        self._enqueue_rx_frame(status_id(node_id), data)

    def _enqueue_heartbeat(self, node_id: int) -> None:
        data = bytes([1, 0, 0, node_id, GLOBAL_CAN_ONLINE_MASK, self._rx_count, 0, self._heartbeat_sequence])
        self._heartbeat_sequence = (self._heartbeat_sequence + 1) & 0xFF
        self._enqueue_rx_frame(heartbeat_id(node_id), data)

    def _enqueue_rx_frame(self, can_id: int, data: bytes) -> None:
        self._increment_global(DIAG_COUNTER_CAN_TX)
        self._rx_queue.append(
            CanFrame(can_id=can_id, data=data, dlc=len(data), timestamp=time.time())
        )

    def _handle_command_frame(self, can_id: int, data: bytes) -> None:
        self._node_id = can_id - 0x500
        command_mask = data[0] & GROUP_ALL_MASK
        command_flags = data[1] if len(data) > 1 else 0
        if command_flags & 0x01:
            command_mask = 0

        old_mask = self._output_mask
        for group_index in range(GROUP_COUNT):
            group_bit = 1 << group_index
            was_on = bool(old_mask & group_bit)
            is_on = bool(command_mask & group_bit)
            if is_on and not was_on:
                self._increment_group(group_index, DIAG_COUNTER_CONTACTOR_CLOSE)
            elif was_on and not is_on:
                self._increment_group(group_index, DIAG_COUNTER_CONTACTOR_OPEN)

        self._output_mask = command_mask
        self._rx_count = (self._rx_count + 1) & 0xFF
        self._increment_global(DIAG_COUNTER_CAN_COMMAND_RX)
        self._enqueue_status(command_mask, node_id=self._node_id)
        self._enqueue_heartbeat(node_id=self._node_id)

    def _handle_diag_request_frame(self, can_id: int, data: bytes) -> None:
        self._node_id = can_id - DIAG_REQUEST_ID_BASE
        command = data[0] if len(data) > 0 else 0
        counter_id = data[1] if len(data) > 1 else 0
        group_index = data[2] if len(data) > 2 else DIAG_GROUP_GLOBAL

        if len(data) < 3:
            self._increment_global(DIAG_COUNTER_DIAG_ERROR)
            self._enqueue_diag_error(command, counter_id, group_index, DIAG_STATUS_BAD_DLC)
            return

        if command == DIAG_CMD_READ_COUNTER:
            status, value = self._get_counter(counter_id, group_index)
            if status == DIAG_STATUS_OK:
                self._increment_global(DIAG_COUNTER_DIAG_REQUEST)
                status, value = self._get_counter(counter_id, group_index)
            else:
                self._increment_global(DIAG_COUNTER_DIAG_ERROR)
            self._enqueue_diag_counter_response(counter_id, group_index, value, status)
            return

        if command == DIAG_CMD_RESET_ALL_COUNTERS:
            if counter_id == DIAG_RESET_MAGIC_1 and group_index == DIAG_RESET_MAGIC_2:
                self._increment_global(DIAG_COUNTER_DIAG_REQUEST)
                self._reset_diag_counters()
                self._enqueue_diag_reset_response(DIAG_STATUS_OK)
            else:
                self._increment_global(DIAG_COUNTER_DIAG_ERROR)
                self._enqueue_diag_reset_response(DIAG_STATUS_RESET_MAGIC_INVALID)
            return

        self._increment_global(DIAG_COUNTER_DIAG_ERROR)
        self._enqueue_diag_error(command, counter_id, group_index, DIAG_STATUS_INVALID_COMMAND)

    def _handle_bootloader_request_frame(self, can_id: int, data: bytes) -> None:
        self._node_id = can_id - BOOTLOADER_REQUEST_ID_BASE
        command = data[0] if len(data) > 0 else 0

        if len(data) == 8 and command == BOOTLOADER_CMD_GET_BOOT_INFO:
            self._enqueue_boot_info_response()
            return

        if len(data) == 8 and command == BOOTLOADER_CMD_GET_FLASH_LAYOUT:
            self._enqueue_flash_layout_response()
            return

        if len(data) == 8 and command == BOOTLOADER_CMD_GET_APP_STATUS_SUMMARY:
            self._enqueue_app_status_summary_response()
            return

        if len(data) == 8 and command == BOOTLOADER_CMD_GET_APP_SIZE_INFO:
            self._enqueue_app_size_info_response()
            return

        if len(data) == 8 and command == BOOTLOADER_CMD_GET_APP_STORED_CRC:
            self._enqueue_app_stored_crc_response()
            return

        if len(data) == 8 and command == BOOTLOADER_CMD_CHECK_APP_FLASH_CRC:
            if data[1] != BOOTLOADER_ENTER_MAGIC_1 or data[2] != BOOTLOADER_ENTER_MAGIC_2:
                self._enqueue_app_flash_crc_response(BOOTLOADER_UPDATE_STATUS_BAD_MAGIC)
            else:
                self._enqueue_app_flash_crc_response(BOOTLOADER_UPDATE_STATUS_OK)
            return

        if len(data) == 8 and command == BOOTLOADER_CMD_GET_METADATA_VERSION_INFO:
            self._enqueue_metadata_version_response()
            return

        if len(data) == 8 and command == BOOTLOADER_CMD_RUN_FLASH_SELF_TEST:
            if data[1] != BOOTLOADER_ENTER_MAGIC_1 or data[2] != BOOTLOADER_ENTER_MAGIC_2:
                self._enqueue_flash_self_test_response(BOOTLOADER_FLASH_STATUS_BAD_MAGIC, 0)
            else:
                self._enqueue_flash_self_test_response(BOOTLOADER_FLASH_STATUS_ADDRESS_RANGE_ERROR, 0)
            return

        if len(data) == 8 and command == BOOTLOADER_CMD_START_UPDATE:
            self._handle_start_update(data)
            return

        if len(data) == 8 and command == BOOTLOADER_CMD_ERASE_APP:
            self._handle_erase_app(data)
            return

        if len(data) == 8 and command == BOOTLOADER_CMD_WRITE_CHUNK:
            self._handle_write_chunk(data)
            return

        if len(data) == 8 and command == BOOTLOADER_CMD_VERIFY_CRC:
            self._handle_verify_crc(data)
            return

        if len(data) == 8 and command == BOOTLOADER_CMD_FINISH_UPDATE:
            self._handle_finish_update(data)
            return

        if len(data) == 8 and command == BOOTLOADER_CMD_ABORT_UPDATE:
            self._handle_abort_update(data)
            return

        if len(data) == 8 and command == BOOTLOADER_CMD_RESET_TO_APP:
            self._handle_reset_to_app(data)

    def _enqueue_diag_counter_response(
        self,
        counter_id: int,
        group_index: int,
        value: int,
        status: int,
    ) -> None:
        data = bytes(
            [DIAG_RESP_READ_COUNTER, counter_id, group_index]
            + list((value & 0xFFFFFFFF).to_bytes(4, "little"))
            + [status]
        )
        self._enqueue_rx_frame(diag_response_id(self._node_id), data)

    def _enqueue_diag_reset_response(self, status: int) -> None:
        data = bytes([DIAG_RESP_RESET_ALL_COUNTERS, 0x00, DIAG_GROUP_GLOBAL, 0x00, 0x00, 0x00, 0x00, status])
        self._enqueue_rx_frame(diag_response_id(self._node_id), data)

    def _enqueue_diag_error(self, command: int, counter_id: int, group_index: int, status: int) -> None:
        data = bytes([DIAG_RESP_ERROR, counter_id, group_index, command, 0x00, 0x00, 0x00, status])
        self._enqueue_rx_frame(diag_response_id(self._node_id), data)

    def _enqueue_boot_info_response(self) -> None:
        data = bytes([BOOTLOADER_RESP_GET_BOOT_INFO, BOOTLOADER_STATUS_OK, 1, 0, 1 if self._mock_app_valid() else 0, 1, 0, 0])
        self._enqueue_rx_frame(bootloader_response_id(self._node_id), data)

    def _enqueue_flash_layout_response(self) -> None:
        data = bytes([BOOTLOADER_RESP_GET_FLASH_LAYOUT, BOOTLOADER_STATUS_OK, 1, 16, 47, 63, 0, 0])
        self._enqueue_rx_frame(bootloader_response_id(self._node_id), data)

    def _enqueue_flash_self_test_response(self, status: int, stage: int) -> None:
        data = bytes([BOOTLOADER_RESP_FLASH_SELF_TEST, status, stage, 0, 0, 0, 0, 0])
        self._enqueue_rx_frame(bootloader_response_id(self._node_id), data)

    def _enqueue_app_status_summary_response(self) -> None:
        size_available = self._mock_metadata_size_available()
        stored_available = self._mock_stored_crc_available()
        computed_available = size_available
        crc_match = self._mock_crc_match() if computed_available else False
        flags = 0
        if size_available:
            flags |= BOOTLOADER_INFO_FLAG_VALUE_AVAILABLE
        if stored_available:
            flags |= BOOTLOADER_INFO_FLAG_STORED_AVAILABLE
        if computed_available:
            flags |= BOOTLOADER_INFO_FLAG_COMPUTED_AVAILABLE
        if crc_match:
            flags |= BOOTLOADER_INFO_FLAG_CRC_MATCH

        data = bytes([
            BOOTLOADER_RESP_APP_STATUS_SUMMARY,
            BOOTLOADER_UPDATE_STATUS_OK,
            self._boot_metadata_state,
            1 if self._mock_app_valid() else 0,
            1 if self._mock_vector_valid() else 0,
            self._mock_info_source(),
            self._boot_update_state,
            flags,
        ])
        self._enqueue_rx_frame(bootloader_response_id(self._node_id), data)

    def _enqueue_app_size_info_response(self) -> None:
        size_available = self._mock_metadata_size_available()
        app_size = self._boot_metadata_app_size if size_available else 0
        flags = BOOTLOADER_INFO_FLAG_VALUE_AVAILABLE if size_available else 0
        data = bytes([
            BOOTLOADER_RESP_APP_SIZE_INFO,
            BOOTLOADER_UPDATE_STATUS_OK,
            *app_size.to_bytes(4, "little"),
            APP_MAX_SIZE_BYTES // 1024,
            flags,
        ])
        self._enqueue_rx_frame(bootloader_response_id(self._node_id), data)

    def _enqueue_app_stored_crc_response(self) -> None:
        crc_available = self._mock_stored_crc_available()
        stored_crc = self._boot_metadata_crc32 if crc_available else 0
        crc_source = BOOTLOADER_CRC_SOURCE_METADATA if crc_available else BOOTLOADER_CRC_SOURCE_NONE
        flags = BOOTLOADER_INFO_FLAG_VALUE_AVAILABLE if crc_available else 0
        data = bytes([
            BOOTLOADER_RESP_APP_STORED_CRC,
            BOOTLOADER_UPDATE_STATUS_OK,
            *stored_crc.to_bytes(4, "little"),
            crc_source,
            flags,
        ])
        self._enqueue_rx_frame(bootloader_response_id(self._node_id), data)

    def _enqueue_app_flash_crc_response(self, status: int) -> None:
        size_available = self._mock_metadata_size_available()
        response_status = status
        computed_crc = 0
        crc_match = False
        flags = 0

        if status == BOOTLOADER_UPDATE_STATUS_OK:
            if not size_available:
                response_status = BOOTLOADER_UPDATE_STATUS_SIZE_ERROR
            else:
                computed_crc = self._mock_computed_crc()
                crc_match = computed_crc == self._boot_metadata_crc32
                flags |= BOOTLOADER_INFO_FLAG_VALUE_AVAILABLE | BOOTLOADER_INFO_FLAG_COMPUTED_AVAILABLE
                if self._mock_stored_crc_available():
                    flags |= BOOTLOADER_INFO_FLAG_STORED_AVAILABLE
                if crc_match:
                    flags |= BOOTLOADER_INFO_FLAG_CRC_MATCH

        data = bytes([
            BOOTLOADER_RESP_APP_FLASH_CRC,
            response_status,
            *computed_crc.to_bytes(4, "little"),
            1 if crc_match else 0,
            flags,
        ])
        self._enqueue_rx_frame(bootloader_response_id(self._node_id), data)

    def _enqueue_metadata_version_response(self) -> None:
        version_available = self._boot_metadata_state != BOOTLOADER_METADATA_STATE_BLANK
        metadata_version = self._boot_metadata_version if version_available else 0
        magic_ok = self._boot_metadata_state != BOOTLOADER_METADATA_STATE_BLANK
        flags = BOOTLOADER_INFO_FLAG_VALUE_AVAILABLE if version_available else 0
        data = bytes([
            BOOTLOADER_RESP_METADATA_VERSION_INFO,
            BOOTLOADER_UPDATE_STATUS_OK,
            *metadata_version.to_bytes(4, "little"),
            1 if magic_ok else 0,
            flags,
        ])
        self._enqueue_rx_frame(bootloader_response_id(self._node_id), data)

    def _mock_metadata_size_available(self) -> bool:
        return (
            self._boot_metadata_state in {
                BOOTLOADER_METADATA_STATE_VALID,
                BOOTLOADER_METADATA_STATE_IN_PROGRESS,
                BOOTLOADER_METADATA_STATE_INVALID,
            } and
            8 < self._boot_metadata_app_size <= APP_MAX_SIZE_BYTES
        )

    def _mock_stored_crc_available(self) -> bool:
        return self._boot_metadata_state in {
            BOOTLOADER_METADATA_STATE_VALID,
            BOOTLOADER_METADATA_STATE_IN_PROGRESS,
            BOOTLOADER_METADATA_STATE_INVALID,
        }

    def _mock_padded_flash_app_data(self) -> bytes:
        if not self._mock_metadata_size_available():
            return bytes(self._boot_flash_app_data)
        app_data = bytes(self._boot_flash_app_data[:self._boot_metadata_app_size])
        if len(app_data) < self._boot_metadata_app_size:
            app_data += b"\xFF" * (self._boot_metadata_app_size - len(app_data))
        return app_data

    def _mock_computed_crc(self) -> int:
        return crc32_ieee(self._mock_padded_flash_app_data())

    def _mock_crc_match(self) -> bool:
        return self._mock_stored_crc_available() and self._mock_computed_crc() == self._boot_metadata_crc32

    def _mock_vector_valid(self) -> bool:
        app_data = bytes(self._boot_flash_app_data)
        if len(app_data) < 8:
            return False
        initial_sp = int.from_bytes(app_data[0:4], "little")
        reset_handler = int.from_bytes(app_data[4:8], "little")
        reset_address = reset_handler & ~1
        return (
            0x20000000 <= initial_sp <= 0x20005000 and
            (initial_sp & 0x3) == 0 and
            (reset_handler & 1) != 0 and
            0x08004000 <= reset_address <= 0x0800FBFF
        )

    def _mock_app_valid(self) -> bool:
        return (
            self._boot_metadata_state == BOOTLOADER_METADATA_STATE_VALID and
            self._mock_metadata_size_available() and
            self._mock_vector_valid() and
            self._mock_crc_match()
        )

    def _mock_info_source(self) -> int:
        if self._boot_metadata_state == BOOTLOADER_METADATA_STATE_BLANK:
            if self._mock_vector_valid():
                return BOOTLOADER_INFO_SOURCE_LEGACY_BLANK
            return BOOTLOADER_INFO_SOURCE_NO_VALID_APP
        if self._boot_metadata_state in {
            BOOTLOADER_METADATA_STATE_VALID,
            BOOTLOADER_METADATA_STATE_IN_PROGRESS,
            BOOTLOADER_METADATA_STATE_INVALID,
        }:
            return BOOTLOADER_INFO_SOURCE_METADATA
        return BOOTLOADER_INFO_SOURCE_NO_VALID_APP

    def _reset_bootloader_update_state(self) -> None:
        default_app = (
            (0x20001000).to_bytes(4, "little") +
            (0x08004101).to_bytes(4, "little") +
            bytes(range(56))
        )
        self._boot_update_state = BOOTLOADER_UPDATE_STATE_IDLE
        self._boot_update_app_size = 0
        self._boot_update_expected_seq = 0
        self._boot_update_data = bytearray()
        self._boot_update_crc_ok = False
        self._boot_flash_app_data = bytearray(default_app)
        self._boot_metadata_state = BOOTLOADER_METADATA_STATE_VALID
        self._boot_metadata_version = 0x00010000
        self._boot_metadata_app_size = len(default_app)
        self._boot_metadata_crc32 = crc32_ieee(default_app)
        self._boot_app_valid = True

    def _has_boot_magic(self, data: bytes) -> bool:
        return len(data) >= 3 and data[1] == BOOTLOADER_ENTER_MAGIC_1 and data[2] == BOOTLOADER_ENTER_MAGIC_2

    def _handle_start_update(self, data: bytes) -> None:
        app_size = int.from_bytes(data[3:7], "little")
        flags = data[7]

        if not self._has_boot_magic(data):
            self._enqueue_start_update_response(BOOTLOADER_UPDATE_STATUS_BAD_MAGIC, app_size)
            return

        if app_size <= 8 or app_size > APP_MAX_SIZE_BYTES:
            self._enqueue_start_update_response(BOOTLOADER_UPDATE_STATUS_SIZE_ERROR, app_size)
            return

        if flags != 0:
            self._enqueue_start_update_response(BOOTLOADER_UPDATE_STATUS_BAD_STATE, app_size)
            return

        self._boot_update_state = BOOTLOADER_UPDATE_STATE_STARTED
        self._boot_update_app_size = app_size
        self._boot_update_expected_seq = 0
        self._boot_update_data = bytearray()
        self._boot_update_crc_ok = False
        self._boot_metadata_state = BOOTLOADER_METADATA_STATE_IN_PROGRESS
        self._boot_metadata_app_size = app_size
        self._boot_metadata_crc32 = 0xFFFFFFFF
        self._boot_app_valid = False
        self._enqueue_start_update_response(BOOTLOADER_UPDATE_STATUS_OK, app_size)

    def _handle_erase_app(self, data: bytes) -> None:
        if not self._has_boot_magic(data):
            self._enqueue_erase_app_response(BOOTLOADER_UPDATE_STATUS_BAD_MAGIC, 0)
            return

        if self._boot_update_state != BOOTLOADER_UPDATE_STATE_STARTED:
            self._enqueue_erase_app_response(BOOTLOADER_UPDATE_STATUS_BAD_STATE, 0)
            return

        erased_pages = (self._boot_update_app_size + 1023) // 1024
        self._boot_update_state = BOOTLOADER_UPDATE_STATE_ERASED
        self._boot_update_data = bytearray()
        self._boot_flash_app_data = bytearray()
        self._enqueue_erase_app_response(BOOTLOADER_UPDATE_STATUS_OK, erased_pages)

    def _handle_write_chunk(self, data: bytes) -> None:
        sequence = int.from_bytes(data[1:3], "little")
        payload_len = data[3]
        payload = data[4:4 + min(payload_len, 4)]

        if payload_len < 1 or payload_len > 4:
            self._enqueue_write_chunk_response(BOOTLOADER_UPDATE_STATUS_SIZE_ERROR, sequence)
            return

        if self._boot_update_state not in {
            BOOTLOADER_UPDATE_STATE_ERASED,
            BOOTLOADER_UPDATE_STATE_WRITING,
        }:
            self._enqueue_write_chunk_response(BOOTLOADER_UPDATE_STATUS_BAD_STATE, sequence)
            return

        if sequence != self._boot_update_expected_seq:
            self._enqueue_write_chunk_response(BOOTLOADER_UPDATE_STATUS_BAD_SEQUENCE, sequence)
            return

        if len(self._boot_update_data) + payload_len > self._boot_update_app_size:
            self._enqueue_write_chunk_response(BOOTLOADER_UPDATE_STATUS_ADDRESS_RANGE_ERROR, sequence)
            return

        self._boot_update_data.extend(payload)
        self._boot_flash_app_data = bytearray(self._boot_update_data)
        self._boot_update_expected_seq += 1
        if len(self._boot_update_data) == self._boot_update_app_size:
            self._boot_update_state = BOOTLOADER_UPDATE_STATE_WRITE_COMPLETE
        else:
            self._boot_update_state = BOOTLOADER_UPDATE_STATE_WRITING

        self._enqueue_write_chunk_response(BOOTLOADER_UPDATE_STATUS_OK, sequence)

    def _handle_verify_crc(self, data: bytes) -> None:
        expected_crc = int.from_bytes(data[1:5], "little")
        actual_crc = crc32_ieee(bytes(self._boot_update_data))

        if self._boot_update_state != BOOTLOADER_UPDATE_STATE_WRITE_COMPLETE:
            self._enqueue_verify_crc_response(BOOTLOADER_UPDATE_STATUS_BAD_STATE, actual_crc)
            return

        if len(self._boot_update_data) != self._boot_update_app_size:
            self._enqueue_verify_crc_response(BOOTLOADER_UPDATE_STATUS_BAD_STATE, actual_crc)
            return

        if actual_crc != expected_crc:
            self._boot_update_state = BOOTLOADER_UPDATE_STATE_ERROR
            self._enqueue_verify_crc_response(BOOTLOADER_UPDATE_STATUS_CRC_MISMATCH, actual_crc)
            return

        self._boot_update_state = BOOTLOADER_UPDATE_STATE_CRC_OK
        self._boot_update_crc_ok = True
        self._enqueue_verify_crc_response(BOOTLOADER_UPDATE_STATUS_OK, actual_crc)

    def _handle_finish_update(self, data: bytes) -> None:
        if not self._has_boot_magic(data):
            self._enqueue_simple_update_response(BOOTLOADER_RESP_FINISH_UPDATE, BOOTLOADER_UPDATE_STATUS_BAD_MAGIC)
            return

        if self._boot_update_state != BOOTLOADER_UPDATE_STATE_CRC_OK or not self._boot_update_crc_ok:
            self._enqueue_simple_update_response(BOOTLOADER_RESP_FINISH_UPDATE, BOOTLOADER_UPDATE_STATUS_BAD_STATE)
            return

        self._boot_update_state = BOOTLOADER_UPDATE_STATE_FINISHED
        self._boot_flash_app_data = bytearray(self._boot_update_data)
        self._boot_metadata_state = BOOTLOADER_METADATA_STATE_VALID
        self._boot_metadata_app_size = self._boot_update_app_size
        self._boot_metadata_crc32 = crc32_ieee(bytes(self._boot_update_data))
        self._boot_app_valid = True
        self._enqueue_simple_update_response(BOOTLOADER_RESP_FINISH_UPDATE, BOOTLOADER_UPDATE_STATUS_OK)

    def _handle_abort_update(self, data: bytes) -> None:
        if not self._has_boot_magic(data):
            self._enqueue_simple_update_response(BOOTLOADER_RESP_ABORT_UPDATE, BOOTLOADER_UPDATE_STATUS_BAD_MAGIC)
            return

        if self._boot_update_state not in {
            BOOTLOADER_UPDATE_STATE_STARTED,
            BOOTLOADER_UPDATE_STATE_ERASED,
            BOOTLOADER_UPDATE_STATE_WRITING,
            BOOTLOADER_UPDATE_STATE_WRITE_COMPLETE,
            BOOTLOADER_UPDATE_STATE_CRC_OK,
        }:
            self._enqueue_simple_update_response(BOOTLOADER_RESP_ABORT_UPDATE, BOOTLOADER_UPDATE_STATUS_BAD_STATE)
            return

        self._boot_update_state = BOOTLOADER_UPDATE_STATE_ERROR
        self._boot_metadata_state = BOOTLOADER_METADATA_STATE_INVALID
        self._boot_metadata_crc32 = 0
        self._boot_app_valid = False
        self._enqueue_simple_update_response(BOOTLOADER_RESP_ABORT_UPDATE, BOOTLOADER_UPDATE_STATUS_OK)

    def _handle_reset_to_app(self, data: bytes) -> None:
        if not self._has_boot_magic(data):
            self._enqueue_simple_update_response(BOOTLOADER_RESP_RESET_TO_APP, BOOTLOADER_UPDATE_STATUS_BAD_MAGIC)
            return

        status = BOOTLOADER_UPDATE_STATUS_OK if self._mock_app_valid() else BOOTLOADER_UPDATE_STATUS_APP_INVALID
        self._enqueue_simple_update_response(BOOTLOADER_RESP_RESET_TO_APP, status)

    def _enqueue_start_update_response(self, status: int, app_size: int) -> None:
        data = bytes(
            [
                BOOTLOADER_RESP_START_UPDATE,
                status,
                self._boot_update_state,
                *app_size.to_bytes(4, "little"),
                0,
            ]
        )
        self._enqueue_rx_frame(bootloader_response_id(self._node_id), data)

    def _enqueue_erase_app_response(self, status: int, erased_pages: int) -> None:
        data = bytes(
            [
                BOOTLOADER_RESP_ERASE_APP,
                status,
                self._boot_update_state,
                *erased_pages.to_bytes(2, "little"),
                0,
                0,
                0,
            ]
        )
        self._enqueue_rx_frame(bootloader_response_id(self._node_id), data)

    def _enqueue_write_chunk_response(self, status: int, sequence: int) -> None:
        data = bytes(
            [
                BOOTLOADER_RESP_WRITE_CHUNK,
                status,
                *sequence.to_bytes(2, "little"),
                *self._boot_update_expected_seq.to_bytes(2, "little"),
                0,
                0,
            ]
        )
        self._enqueue_rx_frame(bootloader_response_id(self._node_id), data)

    def _enqueue_verify_crc_response(self, status: int, actual_crc: int) -> None:
        data = bytes([BOOTLOADER_RESP_VERIFY_CRC, status, *actual_crc.to_bytes(4, "little"), 0, 0])
        self._enqueue_rx_frame(bootloader_response_id(self._node_id), data)

    def _enqueue_simple_update_response(self, response_type: int, status: int) -> None:
        data = bytes([response_type, status, 0, 0, 0, 0, 0, 0])
        self._enqueue_rx_frame(bootloader_response_id(self._node_id), data)

    def _get_counter(self, counter_id: int, group_index: int) -> tuple[int, int]:
        if is_group_counter(counter_id):
            if not 0 <= group_index < GROUP_COUNT:
                return DIAG_STATUS_INVALID_GROUP, 0
            return DIAG_STATUS_OK, self._group_counters[group_index][counter_id]

        if is_global_counter(counter_id):
            if group_index != DIAG_GROUP_GLOBAL:
                return DIAG_STATUS_INVALID_GROUP, 0
            return DIAG_STATUS_OK, self._global_counters[counter_id]

        return DIAG_STATUS_INVALID_COUNTER_ID, 0

    def _reset_diag_counters(self) -> None:
        self._group_counters = [
            {counter_id: 0 for counter_id, _name in GROUP_DIAG_COUNTERS}
            for _group_index in range(GROUP_COUNT)
        ]
        self._global_counters = {counter_id: 0 for counter_id, _name in GLOBAL_DIAG_COUNTERS}

    def _increment_group(self, group_index: int, counter_id: int) -> None:
        if 0 <= group_index < GROUP_COUNT:
            self._group_counters[group_index][counter_id] = min(
                self._group_counters[group_index][counter_id] + 1,
                0xFFFFFFFF,
            )

    def _increment_global(self, counter_id: int) -> None:
        if counter_id in self._global_counters:
            self._global_counters[counter_id] = min(
                self._global_counters[counter_id] + 1,
                0xFFFFFFFF,
            )
