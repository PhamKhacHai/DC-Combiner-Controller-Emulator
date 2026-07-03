import pytest

from models import CanFrame
from protocol import (
    DIAG_STATUS_INVALID_COUNTER_ID,
    DIAG_STATUS_INVALID_GROUP,
    DIAG_STATUS_OK,
    DIAG_STATUS_RESET_MAGIC_INVALID,
    bootloader_request_id,
    bootloader_response_id,
    build_bootloader_abort_update_frame,
    build_bootloader_check_app_flash_crc_frame,
    build_bootloader_enter_frame,
    build_bootloader_erase_app_frame,
    build_bootloader_finish_update_frame,
    build_bootloader_get_app_size_info_frame,
    build_bootloader_get_app_status_summary_frame,
    build_bootloader_get_app_stored_crc_frame,
    build_bootloader_get_flash_layout_frame,
    build_bootloader_get_info_frame,
    build_bootloader_get_metadata_version_info_frame,
    build_bootloader_reset_to_app_frame,
    build_bootloader_run_flash_self_test_frame,
    build_bootloader_start_update_frame,
    build_bootloader_verify_crc_frame,
    build_bootloader_write_chunk_frame,
    build_diag_read_counter_frame,
    build_diag_reset_all_frame,
    build_command_frame,
    build_command_mask,
    command_id,
    decode_bootloader_app_size_info_frame,
    decode_bootloader_app_status_summary_frame,
    decode_bootloader_computed_crc_frame,
    decode_bootloader_flash_layout_frame,
    decode_bootloader_flash_self_test_frame,
    decode_bootloader_info_frame,
    decode_bootloader_metadata_version_frame,
    decode_bootloader_start_update_frame,
    decode_bootloader_stored_crc_frame,
    decode_bootloader_write_chunk_frame,
    decode_bootloader_verify_crc_frame,
    decode_diag_response_frame,
    decode_heartbeat_frame,
    decode_status_frame,
    diag_request_id,
    diag_response_id,
    diag_status_to_text,
    group_to_bit,
    heartbeat_id,
    status_id,
    validate_app_bin_data,
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


def test_bootloader_get_flash_layout_frame() -> None:
    frame = build_bootloader_get_flash_layout_frame(2)
    assert frame.can_id == 0x552
    assert frame.data == bytes([0x12, 0, 0, 0, 0, 0, 0, 0])
    assert frame.dlc == 8
    assert frame.extended is False
    assert frame.rtr is False


def test_bootloader_milestone7_info_request_frames() -> None:
    assert build_bootloader_get_app_status_summary_frame(2).data == bytes([0x13, 0, 0, 0, 0, 0, 0, 0])
    assert build_bootloader_get_app_size_info_frame(2).data == bytes([0x14, 0, 0, 0, 0, 0, 0, 0])
    assert build_bootloader_get_app_stored_crc_frame(2).data == bytes([0x15, 0, 0, 0, 0, 0, 0, 0])
    assert build_bootloader_check_app_flash_crc_frame(2).data == bytes([0x16, 0xA5, 0x5A, 0, 0, 0, 0, 0])
    assert build_bootloader_get_metadata_version_info_frame(2).data == bytes([0x17, 0, 0, 0, 0, 0, 0, 0])


def test_bootloader_run_flash_self_test_frame() -> None:
    frame = build_bootloader_run_flash_self_test_frame(2)
    assert frame.can_id == 0x552
    assert frame.data == bytes([0x20, 0xA5, 0x5A, 0, 0, 0, 0, 0])
    assert frame.dlc == 8
    assert frame.extended is False
    assert frame.rtr is False


def test_bootloader_update_command_frames() -> None:
    frame = build_bootloader_start_update_frame(2, 0x1234)
    assert frame.can_id == 0x552
    assert frame.data == bytes([0x30, 0xA5, 0x5A, 0x34, 0x12, 0, 0, 0])
    assert frame.dlc == 8

    assert build_bootloader_erase_app_frame(2).data == bytes([0x31, 0xA5, 0x5A, 0, 0, 0, 0, 0])
    assert build_bootloader_write_chunk_frame(2, 3, b"abc").data == bytes([0x32, 3, 0, 3, 0x61, 0x62, 0x63, 0xFF])
    assert build_bootloader_verify_crc_frame(2, 0x89ABCDEF).data == bytes([0x33, 0xEF, 0xCD, 0xAB, 0x89, 0, 0, 0])
    assert build_bootloader_finish_update_frame(2).data == bytes([0x34, 0xA5, 0x5A, 0, 0, 0, 0, 0])
    assert build_bootloader_abort_update_frame(2).data == bytes([0x35, 0xA5, 0x5A, 0, 0, 0, 0, 0])
    assert build_bootloader_reset_to_app_frame(2).data == bytes([0x36, 0xA5, 0x5A, 0, 0, 0, 0, 0])


def test_bootloader_info_response_decode() -> None:
    frame = CanFrame(can_id=0x560, data=bytes([0x91, 0x00, 1, 0, 1, 1, 0, 0]), dlc=8)
    response = decode_bootloader_info_frame(frame, 0)
    assert response is not None
    assert response.status_text == "OK"
    assert response.bl_major == 1
    assert response.bl_minor == 0
    assert response.app_valid is True
    assert response.boot_mode_text == "BOOTLOADER"


def test_bootloader_flash_layout_response_decode() -> None:
    frame = CanFrame(can_id=0x560, data=bytes([0x92, 0x00, 1, 16, 47, 63, 0, 0]), dlc=8)
    response = decode_bootloader_flash_layout_frame(frame, 0)
    assert response is not None
    assert response.status_text == "OK"
    assert response.page_kb == 1
    assert response.boot_kb == 16
    assert response.app_kb == 47
    assert response.scratch_page_index == 63


def test_bootloader_flash_self_test_response_decode() -> None:
    frame = CanFrame(can_id=0x560, data=bytes([0xA0, 0x00, 0, 0, 0, 0, 0, 0]), dlc=8)
    response = decode_bootloader_flash_self_test_frame(frame, 0)
    assert response is not None
    assert response.status_text == "OK"
    assert response.stage_text == "DONE"
    assert response.detail == bytes([0, 0, 0, 0, 0])


def test_bootloader_milestone7_info_response_decode() -> None:
    app_status = decode_bootloader_app_status_summary_frame(
        CanFrame(can_id=0x560, data=bytes([0x93, 0x00, 0x01, 1, 1, 0, 0, 0x0F]), dlc=8),
        0,
    )
    assert app_status is not None
    assert app_status.status_text == "OK"
    assert app_status.metadata_state_text == "VALID"
    assert app_status.app_valid is True
    assert app_status.vector_valid is True
    assert app_status.info_source_text == "METADATA"
    assert app_status.session_state_text == "IDLE"

    app_size = decode_bootloader_app_size_info_frame(
        CanFrame(can_id=0x560, data=bytes([0x94, 0x00, 0x20, 0x4C, 0, 0, 47, 1]), dlc=8),
        0,
    )
    assert app_size is not None
    assert app_size.app_size == 0x4C20
    assert app_size.max_app_kb == 47
    assert app_size.size_available is True

    stored_crc = decode_bootloader_stored_crc_frame(
        CanFrame(can_id=0x560, data=bytes([0x95, 0x00, 0x71, 0x08, 0xF3, 0x93, 1, 1]), dlc=8),
        0,
    )
    assert stored_crc is not None
    assert stored_crc.stored_crc32 == 0x93F30871
    assert stored_crc.crc_source_text == "METADATA"
    assert stored_crc.crc_available is True

    computed_crc = decode_bootloader_computed_crc_frame(
        CanFrame(can_id=0x560, data=bytes([0x96, 0x00, 0x71, 0x08, 0xF3, 0x93, 1, 0x0F]), dlc=8),
        0,
    )
    assert computed_crc is not None
    assert computed_crc.computed_crc32 == 0x93F30871
    assert computed_crc.crc_match is True
    assert computed_crc.crc_available is True

    metadata_version = decode_bootloader_metadata_version_frame(
        CanFrame(can_id=0x560, data=bytes([0x97, 0x00, 0, 0, 1, 0, 1, 1]), dlc=8),
        0,
    )
    assert metadata_version is not None
    assert metadata_version.metadata_version == 0x00010000
    assert metadata_version.magic_ok is True
    assert metadata_version.version_available is True


def test_bootloader_update_response_decode() -> None:
    start = decode_bootloader_start_update_frame(
        CanFrame(can_id=0x560, data=bytes([0xB0, 0x00, 1, 0x34, 0x12, 0, 0, 0]), dlc=8),
        0,
    )
    assert start is not None
    assert start.status_text == "OK"
    assert start.stage_text == "STARTED"
    assert start.app_size == 0x1234

    write = decode_bootloader_write_chunk_frame(
        CanFrame(can_id=0x560, data=bytes([0xB2, 0x0B, 3, 0, 4, 0, 0, 0]), dlc=8),
        0,
    )
    assert write is not None
    assert write.status_text == "BAD_SEQUENCE"
    assert write.sequence == 3
    assert write.next_sequence == 4

    verify = decode_bootloader_verify_crc_frame(
        CanFrame(can_id=0x560, data=bytes([0xB3, 0, 0xEF, 0xCD, 0xAB, 0x89, 0, 0]), dlc=8),
        0,
    )
    assert verify is not None
    assert verify.actual_crc == 0x89ABCDEF


def test_validate_app_bin_data_accepts_relocated_app_vector() -> None:
    app_bin = (
        (0x20001000).to_bytes(4, "little") +
        (0x08004101).to_bytes(4, "little") +
        bytes(range(16))
    )

    info = validate_app_bin_data(app_bin, "app.bin")

    assert info.valid is True
    assert info.size == len(app_bin)
    assert info.chunk_count == 6
    assert info.initial_sp == 0x20001000
    assert info.reset_handler == 0x08004101


def test_validate_app_bin_data_rejects_bad_vector() -> None:
    app_bin = (
        (0x10000000).to_bytes(4, "little") +
        (0x08004100).to_bytes(4, "little") +
        bytes(range(16))
    )

    info = validate_app_bin_data(app_bin, "bad.bin")

    assert info.valid is False
    assert "Initial SP" in info.error


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
