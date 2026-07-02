import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

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
