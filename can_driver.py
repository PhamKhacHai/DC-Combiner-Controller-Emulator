from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections import deque
from typing import Deque

from models import CanFrame
from protocol import (
    BOOTLOADER_CMD_GET_FLASH_LAYOUT,
    BOOTLOADER_CMD_GET_BOOT_INFO,
    BOOTLOADER_CMD_RUN_FLASH_SELF_TEST,
    BOOTLOADER_ENTER_MAGIC_1,
    BOOTLOADER_ENTER_MAGIC_2,
    BOOTLOADER_FLASH_STATUS_BAD_MAGIC,
    BOOTLOADER_FLASH_STATUS_OK,
    BOOTLOADER_RESP_FLASH_SELF_TEST,
    BOOTLOADER_RESP_GET_FLASH_LAYOUT,
    BOOTLOADER_REQUEST_ID_BASE,
    BOOTLOADER_RESP_GET_BOOT_INFO,
    BOOTLOADER_STATUS_OK,
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

        if len(data) == 8 and command == BOOTLOADER_CMD_RUN_FLASH_SELF_TEST:
            if data[1] == BOOTLOADER_ENTER_MAGIC_1 and data[2] == BOOTLOADER_ENTER_MAGIC_2:
                self._enqueue_flash_self_test_response(BOOTLOADER_FLASH_STATUS_OK, 0)
            else:
                self._enqueue_flash_self_test_response(BOOTLOADER_FLASH_STATUS_BAD_MAGIC, 0)

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
        data = bytes([BOOTLOADER_RESP_GET_BOOT_INFO, BOOTLOADER_STATUS_OK, 1, 0, 1, 1, 0, 0])
        self._enqueue_rx_frame(bootloader_response_id(self._node_id), data)

    def _enqueue_flash_layout_response(self) -> None:
        data = bytes([BOOTLOADER_RESP_GET_FLASH_LAYOUT, BOOTLOADER_STATUS_OK, 1, 16, 47, 63, 0, 0])
        self._enqueue_rx_frame(bootloader_response_id(self._node_id), data)

    def _enqueue_flash_self_test_response(self, status: int, stage: int) -> None:
        data = bytes([BOOTLOADER_RESP_FLASH_SELF_TEST, status, stage, 0, 0, 0, 0, 0])
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
