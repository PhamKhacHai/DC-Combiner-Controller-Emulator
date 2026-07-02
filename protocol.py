from __future__ import annotations

import time

from models import (
    BoardStatus,
    BootloaderFlashLayoutResponse,
    BootloaderFlashSelfTestResponse,
    BootloaderInfoResponse,
    CanFrame,
    DiagnosticCounterResponse,
    DiagnosticErrorResponse,
    DiagnosticResetResponse,
    HeartbeatStatus,
)

GROUP_COUNT = 6
GROUP_ALL_MASK = 0x3F

CAN_BITRATE = 500_000
NODE_ID_MIN = 0
NODE_ID_MAX = 7

COMMAND_ID_BASE = 0x500
STATUS_ID_BASE = 0x510
HEARTBEAT_ID_BASE = 0x520
DIAG_REQUEST_ID_BASE = 0x530
DIAG_RESPONSE_ID_BASE = 0x540
BOOTLOADER_REQUEST_ID_BASE = 0x550
BOOTLOADER_RESPONSE_ID_BASE = 0x560

COMMAND_CLEAR_FAULT_MASK = 0x01

GLOBAL_CAN_ONLINE_MASK = 0x01
GLOBAL_ANY_FAULT_MASK = 0x02
GLOBAL_FAILSAFE_ACTIVE_MASK = 0x04

DIAG_CMD_READ_COUNTER = 0x01
DIAG_CMD_RESET_ALL_COUNTERS = 0x02

DIAG_RESP_ERROR = 0x80
DIAG_RESP_READ_COUNTER = 0x81
DIAG_RESP_RESET_ALL_COUNTERS = 0x82

DIAG_STATUS_OK = 0x00
DIAG_STATUS_INVALID_COMMAND = 0x01
DIAG_STATUS_INVALID_COUNTER_ID = 0x02
DIAG_STATUS_INVALID_GROUP = 0x03
DIAG_STATUS_BAD_DLC = 0x04
DIAG_STATUS_RESET_MAGIC_INVALID = 0x05
DIAG_STATUS_INTERNAL_ERROR = 0x06

DIAG_RESET_MAGIC_1 = 0xA5
DIAG_RESET_MAGIC_2 = 0x5A
DIAG_GROUP_GLOBAL = 0xFF

BOOTLOADER_CMD_ENTER = 0x10
BOOTLOADER_CMD_GET_BOOT_INFO = 0x11
BOOTLOADER_CMD_GET_FLASH_LAYOUT = 0x12
BOOTLOADER_CMD_RUN_FLASH_SELF_TEST = 0x20
BOOTLOADER_ENTER_MAGIC_1 = 0xA5
BOOTLOADER_ENTER_MAGIC_2 = 0x5A
BOOTLOADER_RESP_GET_BOOT_INFO = 0x91
BOOTLOADER_RESP_GET_FLASH_LAYOUT = 0x92
BOOTLOADER_RESP_FLASH_SELF_TEST = 0xA0
BOOTLOADER_STATUS_OK = 0x00
BOOTLOADER_STATUS_UNKNOWN_COMMAND = 0x01
BOOTLOADER_STATUS_BAD_DLC = 0x02
BOOTLOADER_MODE_ACTIVE = 0x01

BOOTLOADER_STATUS_TEXT: dict[int, str] = {
    BOOTLOADER_STATUS_OK: "OK",
    BOOTLOADER_STATUS_UNKNOWN_COMMAND: "UNKNOWN_COMMAND",
    BOOTLOADER_STATUS_BAD_DLC: "BAD_DLC",
}

BOOTLOADER_FLASH_STATUS_OK = 0x00
BOOTLOADER_FLASH_STATUS_BAD_MAGIC = 0x01
BOOTLOADER_FLASH_STATUS_ADDRESS_RANGE_ERROR = 0x02
BOOTLOADER_FLASH_STATUS_UNLOCK_FAIL = 0x03
BOOTLOADER_FLASH_STATUS_ERASE_FAIL = 0x04
BOOTLOADER_FLASH_STATUS_ERASE_VERIFY_FAIL = 0x05
BOOTLOADER_FLASH_STATUS_PROGRAM_FAIL = 0x06
BOOTLOADER_FLASH_STATUS_PROGRAM_VERIFY_FAIL = 0x07
BOOTLOADER_FLASH_STATUS_LOCK_FAIL = 0x08

BOOTLOADER_FLASH_STAGE_DONE = 0x00
BOOTLOADER_FLASH_STAGE_UNLOCK = 0x01
BOOTLOADER_FLASH_STAGE_ERASE = 0x02
BOOTLOADER_FLASH_STAGE_ERASE_VERIFY = 0x03
BOOTLOADER_FLASH_STAGE_PROGRAM = 0x04
BOOTLOADER_FLASH_STAGE_PROGRAM_VERIFY = 0x05
BOOTLOADER_FLASH_STAGE_FINAL_ERASE = 0x06
BOOTLOADER_FLASH_STAGE_LOCK = 0x07

BOOTLOADER_FLASH_STATUS_TEXT: dict[int, str] = {
    BOOTLOADER_FLASH_STATUS_OK: "OK",
    BOOTLOADER_FLASH_STATUS_BAD_MAGIC: "BAD_MAGIC",
    BOOTLOADER_FLASH_STATUS_ADDRESS_RANGE_ERROR: "ADDRESS_RANGE_ERROR",
    BOOTLOADER_FLASH_STATUS_UNLOCK_FAIL: "FLASH_UNLOCK_FAIL",
    BOOTLOADER_FLASH_STATUS_ERASE_FAIL: "ERASE_FAIL",
    BOOTLOADER_FLASH_STATUS_ERASE_VERIFY_FAIL: "ERASE_VERIFY_FAIL",
    BOOTLOADER_FLASH_STATUS_PROGRAM_FAIL: "PROGRAM_FAIL",
    BOOTLOADER_FLASH_STATUS_PROGRAM_VERIFY_FAIL: "PROGRAM_VERIFY_FAIL",
    BOOTLOADER_FLASH_STATUS_LOCK_FAIL: "FLASH_LOCK_FAIL",
}

BOOTLOADER_FLASH_STAGE_TEXT: dict[int, str] = {
    BOOTLOADER_FLASH_STAGE_DONE: "DONE",
    BOOTLOADER_FLASH_STAGE_UNLOCK: "UNLOCK",
    BOOTLOADER_FLASH_STAGE_ERASE: "ERASE",
    BOOTLOADER_FLASH_STAGE_ERASE_VERIFY: "ERASE_VERIFY",
    BOOTLOADER_FLASH_STAGE_PROGRAM: "PROGRAM",
    BOOTLOADER_FLASH_STAGE_PROGRAM_VERIFY: "PROGRAM_VERIFY",
    BOOTLOADER_FLASH_STAGE_FINAL_ERASE: "FINAL_ERASE",
    BOOTLOADER_FLASH_STAGE_LOCK: "LOCK",
}

DIAG_COUNTER_CONTACTOR_CLOSE = 0x01
DIAG_COUNTER_CONTACTOR_OPEN = 0x02
DIAG_COUNTER_FEEDBACK_MISMATCH = 0x03
DIAG_COUNTER_GROUP_FAULT = 0x04
DIAG_COUNTER_ON_TIMEOUT_FAULT = 0x05
DIAG_COUNTER_UNEXPECTED_OFF_FAULT = 0x06
DIAG_COUNTER_FAULT_CLEAR = 0x07

DIAG_COUNTER_CAN_COMMAND_RX = 0x20
DIAG_COUNTER_CAN_TX = 0x21
DIAG_COUNTER_CAN_RX_ERROR = 0x22
DIAG_COUNTER_CAN_TX_ERROR = 0x23
DIAG_COUNTER_CAN_TIMEOUT = 0x24
DIAG_COUNTER_FAILSAFE_ENTER = 0x25
DIAG_COUNTER_DIAG_REQUEST = 0x26
DIAG_COUNTER_DIAG_ERROR = 0x27

GROUP_DIAG_COUNTERS: tuple[tuple[int, str], ...] = (
    (DIAG_COUNTER_CONTACTOR_CLOSE, "ON Count"),
    (DIAG_COUNTER_CONTACTOR_OPEN, "OFF Count"),
    (DIAG_COUNTER_FEEDBACK_MISMATCH, "Feedback Mismatch"),
    (DIAG_COUNTER_GROUP_FAULT, "Group Fault"),
    (DIAG_COUNTER_ON_TIMEOUT_FAULT, "ON Timeout Fault"),
    (DIAG_COUNTER_UNEXPECTED_OFF_FAULT, "Unexpected OFF Fault"),
    (DIAG_COUNTER_FAULT_CLEAR, "Fault Clear"),
)

GLOBAL_DIAG_COUNTERS: tuple[tuple[int, str], ...] = (
    (DIAG_COUNTER_CAN_COMMAND_RX, "CAN Command RX Count"),
    (DIAG_COUNTER_CAN_TX, "CAN TX Count"),
    (DIAG_COUNTER_CAN_RX_ERROR, "CAN RX Error Count"),
    (DIAG_COUNTER_CAN_TX_ERROR, "CAN TX Error Count"),
    (DIAG_COUNTER_CAN_TIMEOUT, "CAN Timeout Count"),
    (DIAG_COUNTER_FAILSAFE_ENTER, "Failsafe Enter Count"),
    (DIAG_COUNTER_DIAG_REQUEST, "Diagnostic Request Count"),
    (DIAG_COUNTER_DIAG_ERROR, "Diagnostic Error Count"),
)

DIAG_STATUS_TEXT: dict[int, str] = {
    DIAG_STATUS_OK: "OK",
    DIAG_STATUS_INVALID_COMMAND: "INVALID_COMMAND",
    DIAG_STATUS_INVALID_COUNTER_ID: "INVALID_COUNTER_ID",
    DIAG_STATUS_INVALID_GROUP: "INVALID_GROUP",
    DIAG_STATUS_BAD_DLC: "BAD_DLC",
    DIAG_STATUS_RESET_MAGIC_INVALID: "RESET_MAGIC_INVALID",
    DIAG_STATUS_INTERNAL_ERROR: "INTERNAL_ERROR",
}


def validate_node_id(node_id: int) -> int:
    if not NODE_ID_MIN <= node_id <= NODE_ID_MAX:
        raise ValueError(f"Node ID must be in {NODE_ID_MIN}..{NODE_ID_MAX}: {node_id}")
    return node_id


def command_id(node_id: int) -> int:
    return COMMAND_ID_BASE + validate_node_id(node_id)


def status_id(node_id: int) -> int:
    return STATUS_ID_BASE + validate_node_id(node_id)


def heartbeat_id(node_id: int) -> int:
    return HEARTBEAT_ID_BASE + validate_node_id(node_id)


def diag_request_id(node_id: int) -> int:
    return DIAG_REQUEST_ID_BASE + validate_node_id(node_id)


def diag_response_id(node_id: int) -> int:
    return DIAG_RESPONSE_ID_BASE + validate_node_id(node_id)


def bootloader_request_id(node_id: int) -> int:
    return BOOTLOADER_REQUEST_ID_BASE + validate_node_id(node_id)


def bootloader_response_id(node_id: int) -> int:
    return BOOTLOADER_RESPONSE_ID_BASE + validate_node_id(node_id)


def group_to_bit(group_number: int) -> int:
    if not 1 <= group_number <= GROUP_COUNT:
        raise ValueError(f"Group number must be in 1..{GROUP_COUNT}: {group_number}")
    return 1 << (group_number - 1)


def build_command_mask(selected_groups: list[int]) -> int:
    mask = 0
    for group_number in selected_groups:
        mask |= group_to_bit(group_number)
    return mask & GROUP_ALL_MASK


def build_command_frame(node_id: int, command_mask: int, command_flags: int = 0) -> CanFrame:
    data = bytes([command_mask & GROUP_ALL_MASK, command_flags & 0xFF])
    return CanFrame(
        can_id=command_id(node_id),
        data=data,
        dlc=len(data),
        extended=False,
        rtr=False,
        timestamp=time.time(),
    )


def build_diag_read_counter_frame(node_id: int, counter_id: int, group_index: int) -> CanFrame:
    data = bytes(
        [
            DIAG_CMD_READ_COUNTER,
            _validate_u8(counter_id, "Counter ID"),
            _validate_u8(group_index, "Group index"),
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
        ]
    )
    return CanFrame(
        can_id=diag_request_id(node_id),
        data=data,
        dlc=8,
        extended=False,
        rtr=False,
        timestamp=time.time(),
    )


def build_diag_reset_all_frame(node_id: int) -> CanFrame:
    data = bytes(
        [
            DIAG_CMD_RESET_ALL_COUNTERS,
            DIAG_RESET_MAGIC_1,
            DIAG_RESET_MAGIC_2,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
        ]
    )
    return CanFrame(
        can_id=diag_request_id(node_id),
        data=data,
        dlc=8,
        extended=False,
        rtr=False,
        timestamp=time.time(),
    )


def build_bootloader_enter_frame(node_id: int) -> CanFrame:
    data = bytes(
        [
            BOOTLOADER_CMD_ENTER,
            BOOTLOADER_ENTER_MAGIC_1,
            BOOTLOADER_ENTER_MAGIC_2,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
        ]
    )
    return CanFrame(
        can_id=bootloader_request_id(node_id),
        data=data,
        dlc=8,
        extended=False,
        rtr=False,
        timestamp=time.time(),
    )


def build_bootloader_get_info_frame(node_id: int) -> CanFrame:
    data = bytes(
        [
            BOOTLOADER_CMD_GET_BOOT_INFO,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
        ]
    )
    return CanFrame(
        can_id=bootloader_request_id(node_id),
        data=data,
        dlc=8,
        extended=False,
        rtr=False,
        timestamp=time.time(),
    )


def build_bootloader_get_flash_layout_frame(node_id: int) -> CanFrame:
    data = bytes([BOOTLOADER_CMD_GET_FLASH_LAYOUT, 0, 0, 0, 0, 0, 0, 0])
    return CanFrame(
        can_id=bootloader_request_id(node_id),
        data=data,
        dlc=8,
        extended=False,
        rtr=False,
        timestamp=time.time(),
    )


def build_bootloader_run_flash_self_test_frame(node_id: int) -> CanFrame:
    data = bytes([BOOTLOADER_CMD_RUN_FLASH_SELF_TEST, BOOTLOADER_ENTER_MAGIC_1, BOOTLOADER_ENTER_MAGIC_2, 0, 0, 0, 0, 0])
    return CanFrame(
        can_id=bootloader_request_id(node_id),
        data=data,
        dlc=8,
        extended=False,
        rtr=False,
        timestamp=time.time(),
    )


def decode_status_frame(frame: CanFrame, node_id: int) -> BoardStatus | None:
    if frame.can_id != status_id(node_id):
        return None
    if frame.dlc < 5 or len(frame.data) < 5:
        return None

    data = frame.data
    global_status = data[4]
    return BoardStatus(
        do_mask=data[0] & GROUP_ALL_MASK,
        feedback_mask=data[1] | (data[2] << 8),
        fault_mask=data[3] & GROUP_ALL_MASK,
        global_status=global_status,
        can_online=bool(global_status & GLOBAL_CAN_ONLINE_MASK),
        any_fault=bool(global_status & GLOBAL_ANY_FAULT_MASK),
        failsafe_active=bool(global_status & GLOBAL_FAILSAFE_ACTIVE_MASK),
    )


def decode_heartbeat_frame(frame: CanFrame, node_id: int) -> HeartbeatStatus | None:
    if frame.can_id != heartbeat_id(node_id):
        return None
    if frame.dlc < 8 or len(frame.data) < 8:
        return None

    data = frame.data
    global_status = data[4]
    return HeartbeatStatus(
        fw_version=f"{data[0]}.{data[1]}.{data[2]}",
        node_id=data[3],
        global_status=global_status,
        can_online=bool(global_status & GLOBAL_CAN_ONLINE_MASK),
        any_fault=bool(global_status & GLOBAL_ANY_FAULT_MASK),
        failsafe_active=bool(global_status & GLOBAL_FAILSAFE_ACTIVE_MASK),
        rx_count_low=data[5],
        tx_error_count_low=data[6],
        sequence=data[7],
    )


def decode_diag_response_frame(
    frame: CanFrame,
    node_id: int,
) -> DiagnosticCounterResponse | DiagnosticResetResponse | DiagnosticErrorResponse | None:
    if frame.can_id != diag_response_id(node_id):
        return None
    if frame.dlc < 8 or len(frame.data) < 8:
        return None

    data = frame.data
    response_type = data[0]
    counter_id = data[1]
    group_index = data[2]
    status = data[7]
    status_text = diag_status_to_text(status)

    if response_type == DIAG_RESP_READ_COUNTER:
        value = data[3] | (data[4] << 8) | (data[5] << 16) | (data[6] << 24)
        return DiagnosticCounterResponse(
            response_type=response_type,
            counter_id=counter_id,
            group_index=group_index,
            value=value,
            status=status,
            status_text=status_text,
        )

    if response_type == DIAG_RESP_RESET_ALL_COUNTERS:
        return DiagnosticResetResponse(
            response_type=response_type,
            counter_id=counter_id,
            group_index=group_index,
            status=status,
            status_text=status_text,
        )

    if response_type == DIAG_RESP_ERROR:
        return DiagnosticErrorResponse(
            response_type=response_type,
            command=data[3],
            counter_id=counter_id,
            group_index=group_index,
            status=status,
            status_text=status_text,
        )

    return None


def decode_bootloader_info_frame(frame: CanFrame, node_id: int) -> BootloaderInfoResponse | None:
    if frame.can_id != bootloader_response_id(node_id):
        return None
    if frame.dlc < 8 or len(frame.data) < 8:
        return None

    data = frame.data
    if data[0] != BOOTLOADER_RESP_GET_BOOT_INFO:
        return None

    boot_mode = data[5]
    return BootloaderInfoResponse(
        response_type=data[0],
        status=data[1],
        status_text=bootloader_status_to_text(data[1]),
        bl_major=data[2],
        bl_minor=data[3],
        app_valid=data[4] != 0,
        boot_mode=boot_mode,
        boot_mode_text="BOOTLOADER" if boot_mode == BOOTLOADER_MODE_ACTIVE else f"0x{boot_mode:02X}",
    )


def decode_bootloader_flash_layout_frame(frame: CanFrame, node_id: int) -> BootloaderFlashLayoutResponse | None:
    if frame.can_id != bootloader_response_id(node_id):
        return None
    if frame.dlc < 8 or len(frame.data) < 8:
        return None

    data = frame.data
    if data[0] != BOOTLOADER_RESP_GET_FLASH_LAYOUT:
        return None

    return BootloaderFlashLayoutResponse(
        response_type=data[0],
        status=data[1],
        status_text=bootloader_status_to_text(data[1]),
        page_kb=data[2],
        boot_kb=data[3],
        app_kb=data[4],
        scratch_page_index=data[5],
        flags=data[6],
    )


def decode_bootloader_flash_self_test_frame(frame: CanFrame, node_id: int) -> BootloaderFlashSelfTestResponse | None:
    if frame.can_id != bootloader_response_id(node_id):
        return None
    if frame.dlc < 8 or len(frame.data) < 8:
        return None

    data = frame.data
    if data[0] != BOOTLOADER_RESP_FLASH_SELF_TEST:
        return None

    return BootloaderFlashSelfTestResponse(
        response_type=data[0],
        status=data[1],
        status_text=bootloader_flash_status_to_text(data[1]),
        stage=data[2],
        stage_text=bootloader_flash_stage_to_text(data[2]),
        detail=bytes(data[3:8]),
    )


def diag_status_to_text(status: int) -> str:
    return DIAG_STATUS_TEXT.get(status, f"UNKNOWN_STATUS_0x{status:02X}")


def bootloader_status_to_text(status: int) -> str:
    return BOOTLOADER_STATUS_TEXT.get(status, f"UNKNOWN_STATUS_0x{status:02X}")


def bootloader_flash_status_to_text(status: int) -> str:
    return BOOTLOADER_FLASH_STATUS_TEXT.get(status, f"UNKNOWN_STATUS_0x{status:02X}")


def bootloader_flash_stage_to_text(stage: int) -> str:
    return BOOTLOADER_FLASH_STAGE_TEXT.get(stage, f"UNKNOWN_STAGE_0x{stage:02X}")


def counter_id_to_name(counter_id: int) -> str:
    for known_id, name in GROUP_DIAG_COUNTERS + GLOBAL_DIAG_COUNTERS:
        if counter_id == known_id:
            return name
    return f"Unknown Counter 0x{counter_id:02X}"


def group_index_to_name(group_index: int) -> str:
    if group_index == DIAG_GROUP_GLOBAL:
        return "Global"
    if 0 <= group_index < GROUP_COUNT:
        return f"Group {group_index + 1}"
    return f"Invalid Group 0x{group_index:02X}"


def is_group_counter(counter_id: int) -> bool:
    return any(counter_id == known_id for known_id, _ in GROUP_DIAG_COUNTERS)


def is_global_counter(counter_id: int) -> bool:
    return any(counter_id == known_id for known_id, _ in GLOBAL_DIAG_COUNTERS)


def feedback_mask_from_command_mask(command_mask: int) -> int:
    feedback_mask = 0
    for group_index in range(GROUP_COUNT):
        if command_mask & (1 << group_index):
            feedback_mask |= 0b11 << (group_index * 2)
    return feedback_mask


def format_hex_data(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)


def format_can_id(can_id: int) -> str:
    return f"0x{can_id:03X}"


def _validate_u8(value: int, name: str) -> int:
    if not 0 <= value <= 0xFF:
        raise ValueError(f"{name} must be in 0..255: {value}")
    return value
