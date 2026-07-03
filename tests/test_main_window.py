import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from main import MainWindow
from models import BoardStatus
from protocol import DIAG_GROUP_GLOBAL


def test_clear_log_only_clears_log_display() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.connect_can()
        window.poll_rx()
        window.group_checks[4].setChecked(True)
        window.status_labels["do_mask"].setText("0x10")
        window.log_message("manual log line")
        window.periodic_timer.start(100)
        tx_count_before = len(window.driver.tx_frames)

        window.clear_log()

        assert window.log_text.toPlainText() == ""
        assert window.controller.connected is True
        assert window.periodic_timer.isActive()
        assert window.group_checks[4].isChecked()
        assert window.command_mask_label.text() == "0x10"
        assert window.status_labels["do_mask"].text() == "0x10"
        assert len(window.driver.tx_frames) == tx_count_before
    finally:
        window.periodic_timer.stop()
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_fault_status_auto_unchecks_requested_group() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        for group_index in (3, 4, 5):
            window.group_checks[group_index].setChecked(True)
        assert window.command_mask_label.text() == "0x38"

        window.controller.last_status = BoardStatus(
            do_mask=0x30,
            feedback_mask=0x0F00,
            fault_mask=0x08,
            global_status=0x03,
            can_online=True,
            any_fault=True,
            failsafe_active=False,
        )
        window.update_status_labels()

        assert window.group_checks[3].isChecked() is False
        assert window.group_checks[4].isChecked() is True
        assert window.group_checks[5].isChecked() is True
        assert window.command_mask_label.text() == "0x30"
        assert window.controller.get_command_mask() == 0x30
        assert "Group 4 fault detected, auto-unchecked." in window.log_text.toPlainText()
        assert window.group_status_labels[3]["requested"].text() == "OFF"
        assert window.group_status_labels[3]["do"].text() == "OFF"
        assert window.group_status_labels[3]["feedback"].text() == "P=OFF / N=OFF"
        assert window.group_status_labels[3]["fault"].text() == "Yes"
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_failsafe_status_auto_unchecks_requested_groups_without_group_fault() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.group_checks[5].setChecked(True)
        assert window.command_mask_label.text() == "0x20"

        window.controller.last_status = BoardStatus(
            do_mask=0x00,
            feedback_mask=0x0000,
            fault_mask=0x00,
            global_status=0x05,
            can_online=True,
            any_fault=False,
            failsafe_active=True,
        )
        window.update_status_labels()

        assert window.group_checks[5].isChecked() is False
        assert window.command_mask_label.text() == "0x00"
        assert window.controller.get_command_mask() == 0x00
        assert window.group_status_labels[5]["requested"].text() == "OFF"
        assert window.group_status_labels[5]["do"].text() == "OFF"
        assert window.group_status_labels[5]["fault"].text() == "No"
        assert (
            "Failsafe/CAN timeout detected, all requested groups auto-unchecked."
            in window.log_text.toPlainText()
        )
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_actual_do_off_auto_unchecks_requested_group_without_group_fault() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.group_checks[5].setChecked(True)
        assert window.command_mask_label.text() == "0x20"
        window.actual_do_was_on_since_requested[5] = True

        window.controller.last_status = BoardStatus(
            do_mask=0x00,
            feedback_mask=0x0000,
            fault_mask=0x00,
            global_status=0x01,
            can_online=True,
            any_fault=False,
            failsafe_active=False,
        )
        window.update_status_labels()

        assert window.group_checks[5].isChecked() is False
        assert window.command_mask_label.text() == "0x00"
        assert window.controller.get_command_mask() == 0x00
        assert window.group_status_labels[5]["fault"].text() == "No"
        assert "Group 6 actual DO dropped OFF while requested ON, auto-unchecked." in window.log_text.toPlainText()
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_checking_group_is_not_immediately_cleared_by_old_do_off_status() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.controller.last_status = BoardStatus(
            do_mask=0x00,
            feedback_mask=0x0000,
            fault_mask=0x00,
            global_status=0x01,
            can_online=True,
            any_fault=False,
            failsafe_active=False,
        )
        window.update_status_labels()

        window.group_checks[5].setChecked(True)
        window.update_status_labels()

        assert window.group_checks[5].isChecked() is True
        assert window.command_mask_label.text() == "0x20"
        assert "Group 6 actual DO dropped OFF while requested ON, auto-unchecked." not in window.log_text.toPlainText()
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_requested_group_stays_checked_when_status_do_is_still_off_before_send() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.group_checks[5].setChecked(True)

        window.controller.last_status = BoardStatus(
            do_mask=0x00,
            feedback_mask=0x0000,
            fault_mask=0x00,
            global_status=0x01,
            can_online=True,
            any_fault=False,
            failsafe_active=False,
        )
        window.update_status_labels()

        assert window.group_checks[5].isChecked() is True
        assert window.command_mask_label.text() == "0x20"
        assert window.actual_do_was_on_since_requested[5] is False
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_actual_do_on_marks_requested_group_as_observed_on() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.group_checks[5].setChecked(True)

        window.controller.last_status = BoardStatus(
            do_mask=0x20,
            feedback_mask=0x0C00,
            fault_mask=0x00,
            global_status=0x01,
            can_online=True,
            any_fault=False,
            failsafe_active=False,
        )
        window.update_status_labels()

        assert window.group_checks[5].isChecked() is True
        assert window.actual_do_was_on_since_requested[5] is True
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_group6_fault_status_auto_unchecks_without_marking_other_groups_fault() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.group_checks[5].setChecked(True)

        window.controller.last_status = BoardStatus(
            do_mask=0x00,
            feedback_mask=0x0000,
            fault_mask=0x20,
            global_status=0x03,
            can_online=True,
            any_fault=True,
            failsafe_active=False,
        )
        window.update_status_labels()

        assert window.group_checks[5].isChecked() is False
        assert window.command_mask_label.text() == "0x00"
        assert window.group_status_labels[5]["fault"].text() == "Yes"
        assert window.group_status_labels[4]["fault"].text() == "No"
        assert "Group 6 fault detected, auto-unchecked." in window.log_text.toPlainText()
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_periodic_send_uses_mask_after_fault_auto_uncheck() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.connect_can()
        window.poll_rx()
        for group_index in (3, 4, 5):
            window.group_checks[group_index].setChecked(True)
        window.periodic_timer.start(100)

        window.controller.last_status = BoardStatus(
            do_mask=0x30,
            feedback_mask=0x0F00,
            fault_mask=0x08,
            global_status=0x03,
            can_online=True,
            any_fault=True,
            failsafe_active=False,
        )
        window.update_status_labels()
        window.send_once()

        assert window.driver.tx_frames[-1].data == bytes([0x30, 0x00])
        assert window.periodic_timer.isActive()
    finally:
        window.periodic_timer.stop()
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_periodic_stops_when_failsafe_status_auto_unchecks_requests() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.connect_can()
        window.poll_rx()
        window.group_checks[5].setChecked(True)
        window.periodic_timer.start(100)

        window.controller.last_status = BoardStatus(
            do_mask=0x00,
            feedback_mask=0x0000,
            fault_mask=0x00,
            global_status=0x05,
            can_online=True,
            any_fault=False,
            failsafe_active=True,
        )
        window.update_status_labels()

        assert window.group_checks[5].isChecked() is False
        assert window.command_mask_label.text() == "0x00"
        assert window.controller.get_command_mask() == 0x00
        assert not window.periodic_timer.isActive()
        assert "Periodic TX stopped because failsafe/CAN timeout was detected." in window.log_text.toPlainText()
    finally:
        window.periodic_timer.stop()
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_start_periodic_sets_start_button_active_state() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.connect_can()

        window.start_periodic()

        assert window.periodic_timer.isActive()
        assert window.start_button.property("activeState") is True
        assert "background-color" in window.start_button.styleSheet()
        assert "#2f6fa3" in window.start_button.styleSheet()
        assert "#d0d0d0" not in window.start_button.styleSheet()
    finally:
        window.periodic_timer.stop()
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_stop_periodic_clears_start_button_active_state() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.connect_can()
        window.start_periodic()

        window.stop_periodic()

        assert not window.periodic_timer.isActive()
        assert window.start_button.property("activeState") is False
        assert window.start_button.styleSheet() == ""
    finally:
        window.periodic_timer.stop()
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_enter_bootloader_stops_periodic_and_sends_current_node_frame() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.connect_can()
        window.poll_rx()
        window.node_spin.setValue(4)
        window.start_periodic()

        frame = window.enter_bootloader(confirm=False)

        assert frame is not None
        assert not window.periodic_timer.isActive()
        assert frame.can_id == 0x554
        assert frame.data == bytes([0x10, 0xA5, 0x5A, 0, 0, 0, 0, 0])
        assert window.driver.tx_frames[-1].can_id == 0x554
        assert "TX BOOT ID=0x554 DLC=8 DATA=10 A5 5A 00 00 00 00 00" in window.log_text.toPlainText()
    finally:
        window.periodic_timer.stop()
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_get_boot_info_sends_request_and_logs_response() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.connect_can()
        window.poll_rx()
        window.node_spin.setValue(4)

        frame = window.get_boot_info()

        assert frame is not None
        assert frame.can_id == 0x554
        assert frame.data == bytes([0x11, 0, 0, 0, 0, 0, 0, 0])
        assert window.controller.last_boot_info_response is not None
        assert "TX BOOT ID=0x554 DLC=8 DATA=11 00 00 00 00 00 00 00" in window.log_text.toPlainText()
        assert (
            "RX BOOT ID=0x564 DLC=8 DATA=91 00 01 00 01 01 00 00 "
            "BL=1.0 APP_VALID=1 MODE=BOOTLOADER"
        ) in window.log_text.toPlainText()
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_get_flash_layout_sends_request_and_logs_response() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.connect_can()
        window.poll_rx()
        window.node_spin.setValue(4)

        frame = window.get_flash_layout()

        assert frame is not None
        assert frame.can_id == 0x554
        assert frame.data == bytes([0x12, 0, 0, 0, 0, 0, 0, 0])
        assert window.controller.last_flash_layout_response is not None
        assert "TX BOOT ID=0x554 DLC=8 DATA=12 00 00 00 00 00 00 00" in window.log_text.toPlainText()
        assert (
            "RX BOOT ID=0x564 DLC=8 DATA=92 00 01 10 2F 3F 00 00 "
            "PAGE=1KB BOOT=16KB APP=47KB SCRATCH_PAGE=63"
        ) in window.log_text.toPlainText()
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_refresh_bootloader_status_updates_info_labels() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.connect_can()
        window.poll_rx()
        window.node_spin.setValue(4)

        window.refresh_bootloader_status()

        sent_commands = [frame.data[0] for frame in window.driver.tx_frames if frame.data]
        assert sent_commands[-6:] == [0x11, 0x13, 0x14, 0x15, 0x16, 0x17]
        assert window.boot_status_labels["bootloader_version"].text() == "1.0"
        assert window.boot_status_labels["mode"].text() == "BOOTLOADER"
        assert window.boot_status_labels["app_valid"].text() == "Yes"
        assert window.boot_status_labels["vector_valid"].text() == "Yes"
        assert window.boot_status_labels["metadata_state"].text() == "VALID"
        assert window.boot_status_labels["metadata_version"].text() == "1.0"
        assert window.boot_status_labels["crc_match"].text() == "Yes"
        assert window.boot_status_labels["recovery_hint"].text() == "Reset To App is allowed."
        assert "APP_STATUS STATUS=OK META=VALID" in window.log_text.toPlainText()
        assert "FLASH_CRC STATUS=OK" in window.log_text.toPlainText()
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_refresh_bootloader_status_no_response_logs_light_message() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.connect_can()
        window.poll_rx()
        window.wait_for_history_item = lambda history, start_count, timeout_ms: None

        window.refresh_bootloader_status()

        log_text = window.log_text.toPlainText()
        assert "No bootloader response. Enter bootloader first." in log_text
        assert "No response for GET_APP_STATUS_SUMMARY" not in log_text
        assert window.boot_status_labels["bootloader_version"].text() == "-"
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_run_flash_self_test_sends_request_and_logs_response() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.connect_can()
        window.poll_rx()
        window.node_spin.setValue(4)

        frame = window.run_flash_self_test(confirm=False)

        assert frame is None
        assert window.driver.tx_frames == []
        assert "Flash self-test disabled" in window.log_text.toPlainText()
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_start_firmware_update_runs_mock_flow(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    app_bin = (
        (0x20001000).to_bytes(4, "little") +
        (0x08004101).to_bytes(4, "little") +
        bytes(range(32))
    )
    app_path = tmp_path / "app.bin"
    app_path.write_bytes(app_bin)

    try:
        window.connect_can()
        window.poll_rx()
        window.node_spin.setValue(4)
        info = window.load_app_bin(str(app_path))

        assert info is not None
        assert info.valid is True

        window.start_firmware_update(confirm=False)

        log_text = window.log_text.toPlainText()
        assert "START_UPDATE OK" in log_text
        assert "ERASE_APP OK" in log_text
        assert "VERIFY_CRC OK" in log_text
        assert "FINISH_UPDATE OK metadata valid" in log_text
        assert "FIRMWARE_UPDATE DONE" in log_text
        assert window.update_progress.value() == 100
        assert window.update_state == "DONE"
        assert window.update_state_label.text() == "DONE"
        assert not window.abort_update_button.isEnabled()
        assert window.reset_to_app_button.isEnabled()
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_abort_update_mid_write_stops_further_chunks(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    app_bin = (
        (0x20001000).to_bytes(4, "little") +
        (0x08004101).to_bytes(4, "little") +
        bytes(range(80))
    )
    app_path = tmp_path / "app.bin"
    app_path.write_bytes(app_bin)

    original_wait = window.wait_for_history_item

    def abort_after_third_chunk(history: list, start_count: int, timeout_ms: int) -> object | None:
        response = original_wait(history, start_count, timeout_ms)
        if (
            history is window.controller.write_chunk_response_history and
            len(history) >= 3 and
            not window.update_abort_requested
        ):
            window.abort_update()
        return response

    try:
        window.connect_can()
        window.poll_rx()
        window.load_app_bin(str(app_path))
        window.wait_for_history_item = abort_after_third_chunk

        window.start_firmware_update(confirm=False)

        log_text = window.log_text.toPlainText()
        write_sequences = [
            int.from_bytes(frame.data[1:3], "little")
            for frame in window.driver.tx_frames
            if frame.data and frame.data[0] == 0x32
        ]

        assert write_sequences == [0, 1, 2]
        assert any(frame.data and frame.data[0] == 0x35 for frame in window.driver.tx_frames)
        assert "Firmware update aborted by user." in log_text
        assert "Firmware update stopped after user abort." in log_text
        assert "ERROR firmware update stopped" not in log_text
        assert window.update_state == "ABORTED"
        assert window.start_update_button.isEnabled()
        assert not window.abort_update_button.isEnabled()
        assert not window.reset_to_app_button.isEnabled()
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_late_write_bad_state_after_abort_is_ignored(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    app_bin = (
        (0x20001000).to_bytes(4, "little") +
        (0x08004101).to_bytes(4, "little") +
        bytes(range(24))
    )
    app_path = tmp_path / "app.bin"
    app_path.write_bytes(app_bin)
    original_send_write_chunk = window.controller.send_write_chunk
    abort_sent = False

    def send_late_chunk_after_abort(sequence: int, payload: bytes):
        nonlocal abort_sent
        if sequence == 1 and not abort_sent:
            abort_sent = True
            window.abort_update()
        return original_send_write_chunk(sequence, payload)

    try:
        window.connect_can()
        window.poll_rx()
        window.load_app_bin(str(app_path))
        window.controller.send_write_chunk = send_late_chunk_after_abort

        window.start_firmware_update(confirm=False)

        log_text = window.log_text.toPlainText()
        assert "Firmware update aborted by user." in log_text
        assert "Late WRITE_CHUNK response ignored after abort." in log_text
        assert "ERROR firmware update stopped" not in log_text
        assert window.update_state == "ABORTED"
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_force_bad_crc_stops_before_finish_and_disables_reset(tmp_path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

    app_bin = (
        (0x20001000).to_bytes(4, "little") +
        (0x08004101).to_bytes(4, "little") +
        bytes(range(32))
    )
    app_path = tmp_path / "app.bin"
    app_path.write_bytes(app_bin)

    try:
        window.connect_can()
        window.poll_rx()
        window.load_app_bin(str(app_path))
        window.force_bad_crc_check.setChecked(True)

        window.start_firmware_update(confirm=False)

        log_text = window.log_text.toPlainText()
        sent_commands = [frame.data[0] for frame in window.driver.tx_frames if frame.data]
        assert 0x33 in sent_commands
        assert 0x34 not in sent_commands
        assert "Force Bad CRC enabled" in log_text
        assert "VERIFY_CRC failed: CRC_MISMATCH" in log_text
        assert "FINISH_UPDATE OK metadata valid" not in log_text
        assert window.update_state == "FAILED"
        assert window.start_update_button.isEnabled()
        assert not window.reset_to_app_button.isEnabled()
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_stop_after_chunks_stops_without_abort_for_power_loss_test(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    app_bin = (
        (0x20001000).to_bytes(4, "little") +
        (0x08004101).to_bytes(4, "little") +
        bytes(range(80))
    )
    app_path = tmp_path / "app.bin"
    app_path.write_bytes(app_bin)

    try:
        window.connect_can()
        window.poll_rx()
        window.load_app_bin(str(app_path))
        window.stop_after_chunks_spin.setValue(3)

        window.start_firmware_update(confirm=False)

        log_text = window.log_text.toPlainText()
        write_sequences = [
            int.from_bytes(frame.data[1:3], "little")
            for frame in window.driver.tx_frames
            if frame.data and frame.data[0] == 0x32
        ]
        sent_commands = [frame.data[0] for frame in window.driver.tx_frames if frame.data]

        assert write_sequences == [0, 1, 2]
        assert 0x35 not in sent_commands
        assert 0x33 not in sent_commands
        assert 0x34 not in sent_commands
        assert "Advanced stop after 3 chunks reached" in log_text
        assert "No ABORT_UPDATE sent" in log_text
        assert window.update_state == "FAILED"
        assert window.start_update_button.isEnabled()
        assert not window.reset_to_app_button.isEnabled()
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_invalid_app_bin_blocks_update(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    app_path = tmp_path / "bad.bin"
    app_path.write_bytes(b"too small")

    try:
        window.connect_can()
        window.poll_rx()
        info = window.load_app_bin(str(app_path))

        assert info is not None
        assert info.valid is False
        assert not window.start_update_button.isEnabled()
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_disconnect_clears_start_button_active_state() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.connect_can()
        window.start_periodic()

        window.disconnect_can()

        assert not window.periodic_timer.isActive()
        assert window.start_button.property("activeState") is False
        assert window.start_button.styleSheet() == ""
    finally:
        window.periodic_timer.stop()
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_failsafe_auto_stop_clears_start_button_active_state() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.connect_can()
        window.start_periodic()
        window.group_checks[5].setChecked(True)

        window.controller.last_status = BoardStatus(
            do_mask=0x00,
            feedback_mask=0x0000,
            fault_mask=0x00,
            global_status=0x05,
            can_online=True,
            any_fault=False,
            failsafe_active=True,
        )
        window.update_status_labels()

        assert not window.periodic_timer.isActive()
        assert window.start_button.property("activeState") is False
        assert window.start_button.styleSheet() == ""
    finally:
        window.periodic_timer.stop()
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_one_shot_buttons_do_not_get_toggle_active_state() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.connect_can()
        window.start_periodic()

        one_shot_buttons = [
            window.send_button,
            window.stop_button,
            window.off_button,
            window.clear_fault_button,
            window.bootloader_button,
            window.boot_info_button,
            window.flash_layout_button,
            window.flash_self_test_button,
            window.clear_log_button,
            window.diag_read_selected_button,
            window.diag_read_all_button,
            window.diag_reset_all_button,
            window.diag_clear_display_button,
        ]

        assert window.start_button.property("activeState") is True
        assert all(button.property("activeState") is not True for button in one_shot_buttons)
    finally:
        window.periodic_timer.stop()
        window.rx_timer.stop()
        window.close()
        app.processEvents()


@pytest.mark.parametrize(
    ("feedback_mask", "expected_group4"),
    [
        (0x0FC0, "P=ON / N=ON"),
        (0x0F80, "P=OFF / N=ON"),
        (0x0F40, "P=ON / N=OFF"),
        (0x0F00, "P=OFF / N=OFF"),
    ],
)
def test_group_feedback_pn_ui_uses_raw_feedback_mask(feedback_mask: int, expected_group4: str) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.controller.last_status = BoardStatus(
            do_mask=0x00,
            feedback_mask=feedback_mask,
            fault_mask=0x08,
            global_status=0x03,
            can_online=True,
            any_fault=True,
            failsafe_active=False,
        )
        window.update_status_labels()

        assert window.group_status_labels[3]["do"].text() == "OFF"
        assert window.group_status_labels[3]["fault"].text() == "Yes"
        assert window.group_status_labels[3]["feedback"].text() == expected_group4
        assert window.group_status_labels[4]["feedback"].text() == "P=ON / N=ON"
        assert window.group_status_labels[5]["feedback"].text() == "P=ON / N=ON"
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_diagnostic_read_selected_sends_correct_frame() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.connect_can()
        window.poll_rx()

        window.diag_scope_combo.setCurrentIndex(window.diag_scope_combo.findData(DIAG_GROUP_GLOBAL))
        window.diag_counter_combo.setCurrentIndex(window.diag_counter_combo.findData(0x24))
        frame = window.read_selected_diagnostic_counter()

        assert frame is not None
        assert frame.can_id == 0x530
        assert frame.data == bytes([0x01, 0x24, 0xFF, 0, 0, 0, 0, 0])
        assert window.driver.tx_frames[-1].data == frame.data
        assert "TX DIAG ID=0x530" in window.log_text.toPlainText()
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_diagnostic_response_updates_group_counter_cell() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.connect_can()
        window.poll_rx()
        window.group_checks[0].setChecked(True)
        window.send_once()

        window.diag_scope_combo.setCurrentIndex(window.diag_scope_combo.findData(0))
        window.diag_counter_combo.setCurrentIndex(window.diag_counter_combo.findData(0x01))
        window.read_selected_diagnostic_counter()

        assert window.diag_group_items[(0, 0x01)].text() == "1"
        assert window.diag_info_labels["last_status"].text() == "OK"
        assert "VALUE=1 STATUS=OK" in window.log_text.toPlainText()
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_diagnostic_reset_all_sends_frame_and_clears_display() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.connect_can()
        window.poll_rx()
        window.diag_group_items[(0, 0x01)].setText("12")

        frame = window.reset_all_diagnostics(confirm=False)

        assert frame is not None
        assert frame.can_id == 0x530
        assert frame.data == bytes([0x02, 0xA5, 0x5A, 0, 0, 0, 0, 0])
        assert window.diag_group_items[(0, 0x01)].text() == "0"
        assert window.diag_info_labels["last_status"].text() == "OK"
    finally:
        window.rx_timer.stop()
        window.close()
        app.processEvents()


def test_diagnostic_auto_refresh_starts_and_disconnect_stops() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    try:
        window.connect_can()
        window.poll_rx()

        window.diag_auto_check.setChecked(True)

        assert window.diag_auto_timer.isActive()
        assert window.diag_request_queue

        window.disconnect_can()

        assert not window.diag_auto_timer.isActive()
        assert not window.diag_queue_timer.isActive()
        assert not window.diag_auto_check.isChecked()
    finally:
        window.diag_auto_timer.stop()
        window.diag_queue_timer.stop()
        window.rx_timer.stop()
        window.close()
        app.processEvents()
