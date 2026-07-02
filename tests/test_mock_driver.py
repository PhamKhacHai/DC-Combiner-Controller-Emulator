import pytest

from can_driver import MockCanDriver
from controller import ControllerSimulator
from protocol import DIAG_GROUP_GLOBAL


def test_mock_driver_requires_open_before_send() -> None:
    driver = MockCanDriver()
    with pytest.raises(RuntimeError):
        driver.send_frame(0x500, bytes([0x00, 0x00]))


def test_mock_driver_generates_status_and_heartbeat_for_group5() -> None:
    driver = MockCanDriver()
    controller = ControllerSimulator(driver)
    controller.connect("Mock CAN Device")
    controller.poll_rx()

    controller.set_selected_groups([5])
    tx_frame = controller.send_once()
    rx_frames = controller.poll_rx()

    assert tx_frame.can_id == 0x500
    assert tx_frame.data == bytes([0x10, 0x00])
    assert len(rx_frames) == 2
    assert controller.last_status is not None
    assert controller.last_status.do_mask == 0x10
    assert controller.last_status.feedback_mask == 0x0300
    assert controller.last_heartbeat is not None
    assert controller.last_heartbeat.rx_count_low == 1


def test_mock_driver_clear_fault_does_not_restore_groups() -> None:
    driver = MockCanDriver()
    controller = ControllerSimulator(driver)
    controller.connect("Mock CAN Device")
    controller.set_selected_groups([1, 2])
    controller.clear_fault()
    controller.poll_rx()

    assert driver.tx_frames[-1].data == bytes([0x00, 0x01])
    assert controller.selected_groups == [1, 2]
    assert controller.last_status is not None
    assert controller.last_status.do_mask == 0x00


def test_mock_driver_diagnostic_read_returns_counter_response() -> None:
    driver = MockCanDriver()
    controller = ControllerSimulator(driver)
    controller.connect("Mock CAN Device")
    controller.poll_rx()

    controller.set_selected_groups([1])
    controller.send_once()
    controller.poll_rx()

    tx_frame = controller.send_diag_read_counter(0x01, 0)
    rx_frames = controller.poll_rx()

    assert tx_frame.can_id == 0x530
    assert tx_frame.data == bytes([0x01, 0x01, 0x00, 0, 0, 0, 0, 0])
    assert any(frame.can_id == 0x540 for frame in rx_frames)
    assert controller.last_diag_response is not None
    assert controller.last_diag_response.counter_id == 0x01
    assert controller.last_diag_response.group_index == 0
    assert controller.last_diag_response.value == 1
    assert controller.last_diag_response.status_text == "OK"


def test_mock_driver_diagnostic_reset_clears_counters() -> None:
    driver = MockCanDriver()
    controller = ControllerSimulator(driver)
    controller.connect("Mock CAN Device")
    controller.poll_rx()

    controller.set_selected_groups([1])
    controller.send_once()
    controller.poll_rx()
    controller.off_all()
    controller.poll_rx()

    controller.send_diag_reset_all()
    controller.poll_rx()
    assert controller.last_diag_response is not None
    assert controller.last_diag_response.status_text == "OK"

    controller.send_diag_read_counter(0x01, 0)
    controller.poll_rx()
    assert controller.last_diag_response is not None
    assert controller.last_diag_response.value == 0

    controller.send_diag_read_counter(0x26, DIAG_GROUP_GLOBAL)
    controller.poll_rx()
    assert controller.last_diag_response is not None
    assert controller.last_diag_response.status_text == "OK"


def test_controller_sends_enter_bootloader_frame_without_mock_response() -> None:
    driver = MockCanDriver()
    controller = ControllerSimulator(driver)
    controller.connect("Mock CAN Device")
    controller.poll_rx()
    controller.set_node_id(3)

    tx_frame = controller.send_enter_bootloader()
    rx_frames = controller.poll_rx()

    assert tx_frame.can_id == 0x553
    assert tx_frame.data == bytes([0x10, 0xA5, 0x5A, 0, 0, 0, 0, 0])
    assert driver.tx_frames[-1].can_id == 0x553
    assert rx_frames == []


def test_controller_get_boot_info_receives_mock_response() -> None:
    driver = MockCanDriver()
    controller = ControllerSimulator(driver)
    controller.connect("Mock CAN Device")
    controller.poll_rx()
    controller.set_node_id(3)

    tx_frame = controller.send_get_boot_info()
    rx_frames = controller.poll_rx()

    assert tx_frame.can_id == 0x553
    assert tx_frame.data == bytes([0x11, 0, 0, 0, 0, 0, 0, 0])
    assert any(frame.can_id == 0x563 for frame in rx_frames)
    assert controller.last_boot_info_response is not None
    assert controller.last_boot_info_response.status_text == "OK"
    assert controller.last_boot_info_response.bl_major == 1
    assert controller.last_boot_info_response.bl_minor == 0
    assert controller.last_boot_info_response.app_valid is True
    assert controller.last_boot_info_response.boot_mode_text == "BOOTLOADER"


def test_controller_get_flash_layout_receives_mock_response() -> None:
    driver = MockCanDriver()
    controller = ControllerSimulator(driver)
    controller.connect("Mock CAN Device")
    controller.poll_rx()
    controller.set_node_id(3)

    tx_frame = controller.send_get_flash_layout()
    rx_frames = controller.poll_rx()

    assert tx_frame.can_id == 0x553
    assert tx_frame.data == bytes([0x12, 0, 0, 0, 0, 0, 0, 0])
    assert any(frame.can_id == 0x563 for frame in rx_frames)
    assert controller.last_flash_layout_response is not None
    assert controller.last_flash_layout_response.status_text == "OK"
    assert controller.last_flash_layout_response.page_kb == 1
    assert controller.last_flash_layout_response.boot_kb == 16
    assert controller.last_flash_layout_response.app_kb == 47
    assert controller.last_flash_layout_response.scratch_page_index == 63


def test_controller_run_flash_self_test_receives_mock_response() -> None:
    driver = MockCanDriver()
    controller = ControllerSimulator(driver)
    controller.connect("Mock CAN Device")
    controller.poll_rx()
    controller.set_node_id(3)

    tx_frame = controller.send_run_flash_self_test()
    rx_frames = controller.poll_rx()

    assert tx_frame.can_id == 0x553
    assert tx_frame.data == bytes([0x20, 0xA5, 0x5A, 0, 0, 0, 0, 0])
    assert any(frame.can_id == 0x563 for frame in rx_frames)
    assert controller.last_flash_self_test_response is not None
    assert controller.last_flash_self_test_response.status_text == "ADDRESS_RANGE_ERROR"
    assert controller.last_flash_self_test_response.stage_text == "DONE"


def test_mock_driver_accepts_firmware_update_flow() -> None:
    driver = MockCanDriver()
    controller = ControllerSimulator(driver)
    app_bin = (
        (0x20001000).to_bytes(4, "little") +
        (0x08004101).to_bytes(4, "little") +
        bytes(range(16))
    )

    controller.connect("Mock CAN Device")
    controller.poll_rx()
    controller.set_node_id(3)

    controller.send_start_update(len(app_bin))
    controller.poll_rx()
    assert controller.last_start_update_response is not None
    assert controller.last_start_update_response.status_text == "OK"

    controller.send_erase_app()
    controller.poll_rx()
    assert controller.last_erase_app_response is not None
    assert controller.last_erase_app_response.status_text == "OK"

    for sequence, offset in enumerate(range(0, len(app_bin), 4)):
        controller.send_write_chunk(sequence, app_bin[offset:offset + 4])
        controller.poll_rx()
        assert controller.last_write_chunk_response is not None
        assert controller.last_write_chunk_response.status_text == "OK"
        assert controller.last_write_chunk_response.next_sequence == sequence + 1

    from protocol import crc32_ieee

    controller.send_verify_crc(crc32_ieee(app_bin))
    controller.poll_rx()
    assert controller.last_verify_crc_response is not None
    assert controller.last_verify_crc_response.status_text == "OK"

    controller.send_finish_update()
    controller.poll_rx()
    assert controller.last_simple_update_response is not None
    assert controller.last_simple_update_response.status_text == "OK"

    controller.send_abort_update()
    controller.poll_rx()
    assert controller.last_simple_update_response is not None
    assert controller.last_simple_update_response.status_text == "BAD_STATE"

    controller.send_get_boot_info()
    controller.poll_rx()
    assert controller.last_boot_info_response is not None
    assert controller.last_boot_info_response.app_valid is True


def test_mock_driver_abort_update_active_session_returns_ok() -> None:
    driver = MockCanDriver()
    controller = ControllerSimulator(driver)
    controller.connect("Mock CAN Device")
    controller.poll_rx()

    controller.send_start_update(16)
    controller.poll_rx()
    controller.send_erase_app()
    controller.poll_rx()

    controller.send_abort_update()
    controller.poll_rx()

    assert controller.last_simple_update_response is not None
    assert controller.last_simple_update_response.status_text == "OK"

    controller.send_reset_to_app()
    controller.poll_rx()

    assert controller.last_simple_update_response is not None
    assert controller.last_simple_update_response.status_text == "APP_INVALID"


def test_mock_driver_abort_update_idle_returns_bad_state() -> None:
    driver = MockCanDriver()
    controller = ControllerSimulator(driver)
    controller.connect("Mock CAN Device")
    controller.poll_rx()

    controller.send_abort_update()
    controller.poll_rx()

    assert controller.last_simple_update_response is not None
    assert controller.last_simple_update_response.status_text == "BAD_STATE"


def test_mock_driver_rejects_wrong_write_sequence() -> None:
    driver = MockCanDriver()
    controller = ControllerSimulator(driver)
    controller.connect("Mock CAN Device")
    controller.poll_rx()

    controller.send_start_update(16)
    controller.poll_rx()
    controller.send_erase_app()
    controller.poll_rx()
    controller.send_write_chunk(1, b"abcd")
    controller.poll_rx()

    assert controller.last_write_chunk_response is not None
    assert controller.last_write_chunk_response.status_text == "BAD_SEQUENCE"
    assert controller.last_write_chunk_response.next_sequence == 0

    controller.send_write_chunk(0, b"abcd")
    controller.poll_rx()

    assert controller.last_write_chunk_response is not None
    assert controller.last_write_chunk_response.status_text == "OK"
    assert controller.last_write_chunk_response.next_sequence == 1


def test_mock_driver_crc_mismatch_blocks_finish_reset_and_allows_retry() -> None:
    driver = MockCanDriver()
    controller = ControllerSimulator(driver)
    app_bin = (
        (0x20001000).to_bytes(4, "little") +
        (0x08004101).to_bytes(4, "little") +
        bytes(range(16))
    )

    controller.connect("Mock CAN Device")
    controller.poll_rx()

    controller.send_start_update(len(app_bin))
    controller.poll_rx()
    controller.send_erase_app()
    controller.poll_rx()

    for sequence, offset in enumerate(range(0, len(app_bin), 4)):
        controller.send_write_chunk(sequence, app_bin[offset:offset + 4])
        controller.poll_rx()

    from protocol import crc32_ieee

    controller.send_verify_crc(crc32_ieee(app_bin) ^ 0x00000001)
    controller.poll_rx()
    assert controller.last_verify_crc_response is not None
    assert controller.last_verify_crc_response.status_text == "CRC_MISMATCH"

    controller.send_finish_update()
    controller.poll_rx()
    assert controller.last_simple_update_response is not None
    assert controller.last_simple_update_response.status_text == "BAD_STATE"

    controller.send_reset_to_app()
    controller.poll_rx()
    assert controller.last_simple_update_response is not None
    assert controller.last_simple_update_response.status_text == "APP_INVALID"

    controller.send_start_update(len(app_bin))
    controller.poll_rx()
    assert controller.last_start_update_response is not None
    assert controller.last_start_update_response.status_text == "OK"
    controller.send_erase_app()
    controller.poll_rx()

    for sequence, offset in enumerate(range(0, len(app_bin), 4)):
        controller.send_write_chunk(sequence, app_bin[offset:offset + 4])
        controller.poll_rx()

    controller.send_verify_crc(crc32_ieee(app_bin))
    controller.poll_rx()
    assert controller.last_verify_crc_response is not None
    assert controller.last_verify_crc_response.status_text == "OK"

    controller.send_finish_update()
    controller.poll_rx()
    assert controller.last_simple_update_response is not None
    assert controller.last_simple_update_response.status_text == "OK"

    controller.send_reset_to_app()
    controller.poll_rx()
    assert controller.last_simple_update_response is not None
    assert controller.last_simple_update_response.status_text == "OK"
