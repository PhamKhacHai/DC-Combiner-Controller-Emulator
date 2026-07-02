import pytest

from models import CanFrame
from protocol import (
    DIAG_STATUS_INVALID_COUNTER_ID,
    DIAG_STATUS_INVALID_GROUP,
    DIAG_STATUS_OK,
    DIAG_STATUS_RESET_MAGIC_INVALID,
    bootloader_request_id,
    bootloader_response_id,
    build_bootloader_enter_frame,
    build_bootloader_get_info_frame,
    build_diag_read_counter_frame,
    build_diag_reset_all_frame,
    build_command_frame,
    build_command_mask,
    command_id,
    decode_bootloader_info_frame,
    decode_diag_response_frame,
    decode_heartbeat_frame,
    decode_status_frame,
    diag_request_id,
    diag_response_id,
    diag_status_to_text,
    group_to_bit,
    heartbeat_id,
    status_id,
)


@pytest.mark.parametrize(
    ("groups", "expected"),
    [
        ([1], 0x01),
        ([2], 0x02),
        ([3], 0x04),
        ([4], 0x08),
        ([5], 0x10),
        ([6], 0x20),
        ([1, 2], 0x03),
        ([3, 4], 0x0C),
        ([4, 6], 0x28),
        ([5, 6], 0x30),
        ([1, 2, 3, 4, 5, 6], 0x3F),
    ],
)
def test_command_mask(groups: list[int], expected: int) -> None:
    assert build_command_mask(groups) == expected


def test_can_ids() -> None:
    assert command_id(0) == 0x500
    assert command_id(7) == 0x507
    assert status_id(0) == 0x510
    assert heartbeat_id(0) == 0x520
    assert diag_request_id(0) == 0x530
    assert diag_response_id(0) == 0x540
    assert bootloader_request_id(0) == 0x550
    assert bootloader_response_id(0) == 0x560
    assert diag_request_id(7) == 0x537
    assert diag_response_id(7) == 0x547
    assert bootloader_request_id(7) == 0x557
    assert bootloader_response_id(7) == 0x567


def test_invalid_values() -> None:
    with pytest.raises(ValueError):
        group_to_bit(0)
    with pytest.raises(ValueError):
        group_to_bit(7)
    with pytest.raises(ValueError):
        command_id(8)


def test_command_frame() -> None:
    frame = build_command_frame(0, 0x03)
    assert frame.can_id == 0x500
    assert frame.data == bytes([0x03, 0x00])
    assert frame.dlc == 2
    assert frame.extended is False
    assert frame.rtr is False


def test_diag_read_counter_frame() -> None:
    frame = build_diag_read_counter_frame(0, 0x24, 0xFF)
    assert frame.can_id == 0x530
    assert frame.data == bytes([0x01, 0x24, 0xFF, 0, 0, 0, 0, 0])
    assert frame.dlc == 8
    assert frame.extended is False
    assert frame.rtr is False


def test_diag_reset_all_frame() -> None:
    frame = build_diag_reset_all_frame(0)
    assert frame.can_id == 0x530
    assert frame.data == bytes([0x02, 0xA5, 0x5A, 0, 0, 0, 0, 0])
    assert frame.dlc == 8


def test_bootloader_enter_frame() -> None:
    frame = build_bootloader_enter_frame(2)
    assert frame.can_id == 0x552
    assert frame.data == bytes([0x10, 0xA5, 0x5A, 0, 0, 0, 0, 0])
    assert frame.dlc == 8
    assert frame.extended is False
    assert frame.rtr is False


def test_bootloader_get_info_frame() -> None:
    frame = build_bootloader_get_info_frame(2)
    assert frame.can_id == 0x552
    assert frame.data == bytes([0x11, 0, 0, 0, 0, 0, 0, 0])
    assert frame.dlc == 8
    assert frame.extended is False
    assert frame.rtr is False


def test_bootloader_info_response_decode() -> None:
    frame = CanFrame(can_id=0x560, data=bytes([0x91, 0x00, 1, 0, 1, 1, 0, 0]), dlc=8)
    response = decode_bootloader_info_frame(frame, 0)
    assert response is not None
    assert response.status_text == "OK"
    assert response.bl_major == 1
    assert response.bl_minor == 0
    assert response.app_valid is True
    assert response.boot_mode_text == "BOOTLOADER"


def test_diag_counter_response_decode() -> None:
    frame = CanFrame(can_id=0x540, data=bytes([0x81, 0x24, 0xFF, 0x03, 0, 0, 0, 0]), dlc=8)
    response = decode_diag_response_frame(frame, 0)
    assert response is not None
    assert response.counter_id == 0x24
    assert response.group_index == 0xFF
    assert response.value == 3
    assert response.status == DIAG_STATUS_OK
    assert response.status_text == "OK"


def test_diag_counter_response_little_endian_decode() -> None:
    frame = CanFrame(can_id=0x540, data=bytes([0x81, 0x01, 0x00, 0x2C, 0x01, 0, 0, 0]), dlc=8)
    response = decode_diag_response_frame(frame, 0)
    assert response is not None
    assert response.value == 300


def test_diag_status_text() -> None:
    assert diag_status_to_text(DIAG_STATUS_OK) == "OK"
    assert diag_status_to_text(DIAG_STATUS_INVALID_COUNTER_ID) == "INVALID_COUNTER_ID"
    assert diag_status_to_text(DIAG_STATUS_INVALID_GROUP) == "INVALID_GROUP"
    assert diag_status_to_text(DIAG_STATUS_RESET_MAGIC_INVALID) == "RESET_MAGIC_INVALID"


def test_status_decode() -> None:
    frame = CanFrame(can_id=0x510, data=bytes([0x03, 0x0F, 0x00, 0x00, 0x01, 0, 0, 0]), dlc=8)
    status = decode_status_frame(frame, 0)
    assert status is not None
    assert status.do_mask == 0x03
    assert status.feedback_mask == 0x000F
    assert status.fault_mask == 0x00
    assert status.global_status == 0x01
    assert status.can_online is True
    assert status.any_fault is False
    assert status.failsafe_active is False


def test_status_decode_fault_mask_group4() -> None:
    frame = CanFrame(can_id=0x510, data=bytes([0x30, 0x00, 0x0F, 0x08, 0x03, 0, 0, 0]), dlc=8)
    status = decode_status_frame(frame, 0)
    assert status is not None
    assert status.do_mask == 0x30
    assert status.feedback_mask == 0x0F00
    assert status.fault_mask == 0x08
    assert status.global_status == 0x03
    assert status.any_fault is True


@pytest.mark.parametrize(
    ("feedback_mask", "expected_group4", "expected_group5", "expected_group6"),
    [
        (0x0FC0, (True, True), (True, True), (True, True)),
        (0x0F80, (False, True), (True, True), (True, True)),
        (0x0F40, (True, False), (True, True), (True, True)),
        (0x0F00, (False, False), (True, True), (True, True)),
    ],
)
def test_feedback_pn_decode_from_raw_feedback_mask(
    feedback_mask: int,
    expected_group4: tuple[bool, bool],
    expected_group5: tuple[bool, bool],
    expected_group6: tuple[bool, bool],
) -> None:
    frame = CanFrame(
        can_id=0x510,
        data=bytes([0x00, feedback_mask & 0xFF, (feedback_mask >> 8) & 0xFF, 0x08, 0x03, 0, 0, 0]),
        dlc=8,
    )
    status = decode_status_frame(frame, 0)
    assert status is not None
    assert status.do_mask == 0x00
    assert status.fault_mask == 0x08
    assert status.feedback_mask == feedback_mask

    def feedback_pair(group_number: int) -> tuple[bool, bool]:
        group_index = group_number - 1
        p_bit = group_index * 2
        n_bit = group_index * 2 + 1
        return (
            (status.feedback_mask & (1 << p_bit)) != 0,
            (status.feedback_mask & (1 << n_bit)) != 0,
        )

    assert feedback_pair(4) == expected_group4
    assert feedback_pair(5) == expected_group5
    assert feedback_pair(6) == expected_group6


def test_heartbeat_decode() -> None:
    frame = CanFrame(can_id=0x520, data=bytes([1, 0, 0, 0, 0x01, 5, 0, 9]), dlc=8)
    heartbeat = decode_heartbeat_frame(frame, 0)
    assert heartbeat is not None
    assert heartbeat.fw_version == "1.0.0"
    assert heartbeat.node_id == 0
    assert heartbeat.sequence == 9
