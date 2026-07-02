from __future__ import annotations

import sys
import time
from datetime import datetime

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from bridge_can_driver import BridgeCanDriver
from can_driver import MockCanDriver
from controller import ControllerSimulator
from models import (
    AppBinInfo,
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
)
from protocol import (
    BOOTLOADER_REQUEST_ID_BASE,
    BOOTLOADER_RESPONSE_ID_BASE,
    BOOTLOADER_RESP_ABORT_UPDATE,
    BOOTLOADER_RESP_FINISH_UPDATE,
    BOOTLOADER_RESP_RESET_TO_APP,
    BOOTLOADER_UPDATE_STATUS_OK,
    CAN_BITRATE,
    DIAG_GROUP_GLOBAL,
    DIAG_REQUEST_ID_BASE,
    DIAG_RESPONSE_ID_BASE,
    DIAG_STATUS_OK,
    GLOBAL_DIAG_COUNTERS,
    GROUP_COUNT,
    GROUP_DIAG_COUNTERS,
    NODE_ID_MAX,
    bootloader_update_response_name,
    counter_id_to_name,
    decode_bootloader_erase_app_frame,
    decode_bootloader_flash_layout_frame,
    decode_bootloader_flash_self_test_frame,
    decode_bootloader_info_frame,
    decode_bootloader_simple_update_frame,
    decode_bootloader_start_update_frame,
    decode_bootloader_verify_crc_frame,
    decode_bootloader_write_chunk_frame,
    decode_diag_response_frame,
    format_can_id,
    format_hex_data,
    group_index_to_name,
    validate_app_bin_data,
)
from usb_can_b_driver import UsbCanBDriver

PERIODIC_ACTIVE_BUTTON_STYLE = """
QPushButton {
    background-color: #2f6fa3;
    color: #ffffff;
    border: 1px solid #255a86;
}
"""


class FirmwareUpdateAborted(RuntimeError):
    pass


class FirmwareUpdateStoppedForTest(RuntimeError):
    pass


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DC Combiner Controller Emulator")
        self.driver = MockCanDriver()
        self.controller = ControllerSimulator(self.driver)

        self.periodic_timer = QTimer(self)
        self.periodic_timer.timeout.connect(self.send_once)

        self.rx_timer = QTimer(self)
        self.rx_timer.timeout.connect(self.poll_rx)
        self.rx_timer.start(50)

        self.diag_queue_timer = QTimer(self)
        self.diag_queue_timer.setInterval(50)
        self.diag_queue_timer.timeout.connect(self.send_next_diagnostic_request)

        self.diag_auto_timer = QTimer(self)
        self.diag_auto_timer.timeout.connect(self.read_all_diagnostic_counters)

        self.group_checks: list[QCheckBox] = []
        self.status_labels: dict[str, QLabel] = {}
        self.group_status_labels: list[dict[str, QLabel]] = []
        self.diag_group_items: dict[tuple[int, int], QTableWidgetItem] = {}
        self.diag_global_items: dict[int, QTableWidgetItem] = {}
        self.diag_info_labels: dict[str, QLabel] = {}
        self.diag_connected_widgets: list[QWidget] = []
        self.diag_request_queue: list[tuple[int, int]] = []
        self.seen_diag_response_count = 0
        self.checkbox_requested_state = [False] * GROUP_COUNT
        self.actual_do_was_on_since_requested = [False] * GROUP_COUNT
        self.selected_app_bin_path = ""
        self.selected_app_bin_data = b""
        self.selected_app_bin_info: AppBinInfo | None = None
        self.update_in_progress = False
        self.update_abort_requested = False
        self.reset_to_app_allowed = True
        self.update_state = "IDLE"

        self._build_ui()
        self.refresh_devices()
        self.update_command_mask()
        self.update_connected_state()
        self._update_periodic_button_state()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        tabs = QTabWidget()
        control_tab = QWidget()
        control_layout = QVBoxLayout(control_tab)
        control_layout.addWidget(self._build_can_section())
        control_layout.addWidget(self._build_command_section())
        control_layout.addWidget(self._build_bootloader_section())
        control_layout.addWidget(self._build_status_section())
        control_layout.addStretch(1)
        tabs.addTab(control_tab, "Control")
        tabs.addTab(self._build_diagnostics_tab(), "Diagnostics")

        layout.addWidget(tabs)
        layout.addWidget(self._build_log_section(), stretch=1)
        self.setCentralWidget(root)
        self.resize(1080, 800)

    def _build_can_section(self) -> QGroupBox:
        box = QGroupBox("CAN")
        layout = QGridLayout(box)

        self.driver_mode = QComboBox()
        self.driver_mode.addItems(["Mock", "USB-CAN-B Direct", "USB-CAN-B Bridge"])
        self.driver_mode.currentTextChanged.connect(self.on_driver_mode_changed)

        self.device_combo = QComboBox()
        self.device_combo.setEditable(True)

        self.refresh_button = QPushButton("Refresh Devices")
        self.refresh_button.clicked.connect(self.refresh_devices)

        self.channel_spin = QSpinBox()
        self.channel_spin.setRange(0, 8)
        self.channel_spin.setValue(0)

        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(10_000, 1_000_000)
        self.bitrate_spin.setSingleStep(10_000)
        self.bitrate_spin.setValue(CAN_BITRATE)

        self.node_spin = QSpinBox()
        self.node_spin.setRange(0, 7)
        self.node_spin.setValue(0)
        self.node_spin.valueChanged.connect(self.on_node_changed)

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_can)
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.disconnect_can)

        layout.addWidget(QLabel("Driver mode"), 0, 0)
        layout.addWidget(self.driver_mode, 0, 1)
        layout.addWidget(QLabel("Device"), 0, 2)
        layout.addWidget(self.device_combo, 0, 3)
        layout.addWidget(self.refresh_button, 0, 4)
        layout.addWidget(QLabel("Channel"), 1, 0)
        layout.addWidget(self.channel_spin, 1, 1)
        layout.addWidget(QLabel("Bitrate"), 1, 2)
        layout.addWidget(self.bitrate_spin, 1, 3)
        layout.addWidget(QLabel("Node ID"), 1, 4)
        layout.addWidget(self.node_spin, 1, 5)
        layout.addWidget(self.connect_button, 2, 4)
        layout.addWidget(self.disconnect_button, 2, 5)
        return box

    def _build_command_section(self) -> QGroupBox:
        box = QGroupBox("Command")
        layout = QGridLayout(box)

        for group_number in range(1, 7):
            checkbox = QCheckBox(f"Group {group_number}")
            checkbox.stateChanged.connect(self.on_groups_changed)
            self.group_checks.append(checkbox)
            layout.addWidget(checkbox, 0, group_number - 1)

        self.command_mask_label = QLabel("0x00")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(50, 5000)
        self.interval_spin.setValue(100)
        self.interval_spin.setSuffix(" ms")

        self.send_button = QPushButton("Send Once")
        self.send_button.setToolTip(
            "Send Once does not keep outputs ON. Firmware will enter fail-safe after command timeout unless periodic command is enabled."
        )
        self.send_button.clicked.connect(self.send_once)
        self.start_button = QPushButton("Start Periodic")
        self.start_button.clicked.connect(self.start_periodic)
        self.stop_button = QPushButton("Stop Periodic")
        self.stop_button.clicked.connect(self.stop_periodic)
        self.off_button = QPushButton("Off All")
        self.off_button.clicked.connect(self.off_all)
        self.clear_fault_button = QPushButton("Clear Fault")
        self.clear_fault_button.clicked.connect(self.clear_fault)

        layout.addWidget(QLabel("Command Mask"), 1, 0)
        layout.addWidget(self.command_mask_label, 1, 1)
        layout.addWidget(QLabel("Interval"), 1, 2)
        layout.addWidget(self.interval_spin, 1, 3)
        layout.addWidget(self.send_button, 2, 0)
        layout.addWidget(self.start_button, 2, 1)
        layout.addWidget(self.stop_button, 2, 2)
        layout.addWidget(self.off_button, 2, 3)
        layout.addWidget(self.clear_fault_button, 2, 4)

        timeout_note = QLabel(
            "Send Once does not keep outputs ON; use Start Periodic to avoid firmware command timeout."
        )
        layout.addWidget(timeout_note, 3, 0, 1, 5)
        return box

    def _build_bootloader_section(self) -> QGroupBox:
        box = QGroupBox("Bootloader")
        layout = QGridLayout(box)

        self.bootloader_button = QPushButton("Enter Bootloader")
        self.bootloader_button.clicked.connect(lambda: self.enter_bootloader())
        self.boot_info_button = QPushButton("Get Boot Info")
        self.boot_info_button.clicked.connect(self.get_boot_info)
        self.flash_layout_button = QPushButton("Get Flash Layout")
        self.flash_layout_button.clicked.connect(self.get_flash_layout)
        self.flash_self_test_button = QPushButton("Run Flash Self-Test")
        self.flash_self_test_button.clicked.connect(lambda: self.run_flash_self_test())
        self.flash_self_test_button.setEnabled(False)
        self.flash_self_test_button.setToolTip(
            "Disabled from Milestone 5 because 0x0800FC00 is now real metadata."
        )

        self.select_app_bin_button = QPushButton("Select App .bin")
        self.select_app_bin_button.clicked.connect(self.select_app_bin)
        self.start_update_button = QPushButton("Start Firmware Update")
        self.start_update_button.clicked.connect(lambda: self.start_firmware_update())
        self.abort_update_button = QPushButton("Abort Update")
        self.abort_update_button.clicked.connect(self.abort_update)
        self.reset_to_app_button = QPushButton("Reset To App")
        self.reset_to_app_button.clicked.connect(self.reset_to_app)

        self.update_state_label = QLabel(self.update_state)
        self.app_bin_path_label = QLabel("-")
        self.app_bin_info_label = QLabel("No app .bin selected")
        self.update_progress = QProgressBar()
        self.update_progress.setRange(0, 100)
        self.update_progress.setValue(0)
        self.stop_after_chunks_spin = QSpinBox()
        self.stop_after_chunks_spin.setRange(0, 65535)
        self.stop_after_chunks_spin.setValue(0)
        self.stop_after_chunks_spin.setSpecialValueText("Disabled")
        self.stop_after_chunks_spin.setSuffix(" chunks")
        self.force_bad_crc_check = QCheckBox("Force Bad CRC")

        layout.addWidget(self.bootloader_button, 0, 0)
        layout.addWidget(self.boot_info_button, 0, 1)
        layout.addWidget(self.flash_layout_button, 0, 2)
        layout.addWidget(self.flash_self_test_button, 0, 3)
        layout.addWidget(self.select_app_bin_button, 1, 0)
        layout.addWidget(self.start_update_button, 1, 1)
        layout.addWidget(self.abort_update_button, 1, 2)
        layout.addWidget(self.reset_to_app_button, 1, 3)
        layout.addWidget(QLabel("File"), 2, 0)
        layout.addWidget(self.app_bin_path_label, 2, 1, 1, 3)
        layout.addWidget(QLabel("Validation"), 3, 0)
        layout.addWidget(self.app_bin_info_label, 3, 1, 1, 3)
        layout.addWidget(self.update_progress, 4, 0, 1, 4)
        layout.addWidget(QLabel("State"), 5, 0)
        layout.addWidget(self.update_state_label, 5, 1, 1, 3)
        layout.addWidget(QLabel("Advanced/Test"), 6, 0)
        layout.addWidget(QLabel("Stop After N Chunks"), 6, 1)
        layout.addWidget(self.stop_after_chunks_spin, 6, 2)
        layout.addWidget(self.force_bad_crc_check, 6, 3)
        return box

    def _build_status_section(self) -> QGroupBox:
        box = QGroupBox("Status")
        layout = QVBoxLayout(box)
        form = QFormLayout()
        fields = [
            ("do_mask", "DO Mask"),
            ("feedback_mask", "Feedback Mask"),
            ("fault_mask", "Fault Mask"),
            ("global_status", "Global Status"),
            ("can_online", "CAN Online"),
            ("any_fault", "Any Fault"),
            ("failsafe_active", "Failsafe Active"),
            ("fw_version", "FW Version"),
            ("heartbeat_sequence", "Heartbeat Sequence"),
        ]
        for key, title in fields:
            label = QLabel("-")
            self.status_labels[key] = label
            form.addRow(title, label)
        layout.addLayout(form)

        group_grid = QGridLayout()
        headers = ["Group", "Requested", "DO", "Feedback P/N", "Fault"]
        for column, title in enumerate(headers):
            group_grid.addWidget(QLabel(title), 0, column)

        for group_index in range(GROUP_COUNT):
            labels = {
                "requested": QLabel("OFF"),
                "do": QLabel("-"),
                "feedback": QLabel("P=- / N=-"),
                "fault": QLabel("-"),
            }
            self.group_status_labels.append(labels)
            row = group_index + 1
            group_grid.addWidget(QLabel(f"Group {row}"), row, 0)
            group_grid.addWidget(labels["requested"], row, 1)
            group_grid.addWidget(labels["do"], row, 2)
            group_grid.addWidget(labels["feedback"], row, 3)
            group_grid.addWidget(labels["fault"], row, 4)

        layout.addLayout(group_grid)
        return box

    def _build_diagnostics_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._build_diagnostic_controls())
        layout.addWidget(self._build_group_diagnostic_table())
        layout.addWidget(self._build_global_diagnostic_table())
        layout.addWidget(self._build_diagnostic_info())
        layout.addStretch(1)
        self.update_diag_counter_options()
        return tab

    def _build_diagnostic_controls(self) -> QGroupBox:
        box = QGroupBox("Logging & Diagnostic")
        layout = QGridLayout(box)

        self.diag_scope_combo = QComboBox()
        for group_index in range(GROUP_COUNT):
            self.diag_scope_combo.addItem(f"Group {group_index + 1}", group_index)
        self.diag_scope_combo.addItem("Global", DIAG_GROUP_GLOBAL)
        self.diag_scope_combo.currentIndexChanged.connect(self.update_diag_counter_options)

        self.diag_counter_combo = QComboBox()

        self.diag_read_selected_button = QPushButton("Read Selected Counter")
        self.diag_read_selected_button.clicked.connect(self.read_selected_diagnostic_counter)
        self.diag_read_all_button = QPushButton("Read All Counters")
        self.diag_read_all_button.clicked.connect(self.read_all_diagnostic_counters)
        self.diag_reset_all_button = QPushButton("Reset All Counters")
        self.diag_reset_all_button.clicked.connect(lambda: self.reset_all_diagnostics())
        self.diag_clear_display_button = QPushButton("Clear Diagnostic Display")
        self.diag_clear_display_button.clicked.connect(self.clear_diagnostic_display)

        self.diag_auto_check = QCheckBox("Auto Refresh")
        self.diag_auto_check.stateChanged.connect(self.on_diag_auto_refresh_changed)
        self.diag_auto_interval_spin = QSpinBox()
        self.diag_auto_interval_spin.setRange(200, 10_000)
        self.diag_auto_interval_spin.setSingleStep(100)
        self.diag_auto_interval_spin.setValue(1000)
        self.diag_auto_interval_spin.setSuffix(" ms")
        self.diag_auto_interval_spin.valueChanged.connect(self.on_diag_auto_interval_changed)

        self.diag_note_label = QLabel("Diagnostic reads do not refresh command timeout.")

        layout.addWidget(QLabel("Scope"), 0, 0)
        layout.addWidget(self.diag_scope_combo, 0, 1)
        layout.addWidget(QLabel("Counter"), 0, 2)
        layout.addWidget(self.diag_counter_combo, 0, 3, 1, 2)
        layout.addWidget(self.diag_read_selected_button, 1, 0)
        layout.addWidget(self.diag_read_all_button, 1, 1)
        layout.addWidget(self.diag_reset_all_button, 1, 2)
        layout.addWidget(self.diag_clear_display_button, 1, 3)
        layout.addWidget(self.diag_auto_check, 2, 0)
        layout.addWidget(self.diag_auto_interval_spin, 2, 1)
        layout.addWidget(self.diag_note_label, 2, 2, 1, 3)

        self.diag_connected_widgets.extend(
            [
                self.diag_read_selected_button,
                self.diag_read_all_button,
                self.diag_reset_all_button,
                self.diag_auto_check,
            ]
        )
        return box

    def _build_group_diagnostic_table(self) -> QGroupBox:
        box = QGroupBox("Group Counters")
        layout = QVBoxLayout(box)

        self.diag_group_table = QTableWidget(GROUP_COUNT, len(GROUP_DIAG_COUNTERS))
        self.diag_group_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.diag_group_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.diag_group_table.setHorizontalHeaderLabels([name for _counter_id, name in GROUP_DIAG_COUNTERS])
        self.diag_group_table.setVerticalHeaderLabels([f"Group {index + 1}" for index in range(GROUP_COUNT)])

        for group_index in range(GROUP_COUNT):
            for column, (counter_id, _name) in enumerate(GROUP_DIAG_COUNTERS):
                item = QTableWidgetItem("-")
                self.diag_group_items[(group_index, counter_id)] = item
                self.diag_group_table.setItem(group_index, column, item)

        layout.addWidget(self.diag_group_table)
        return box

    def _build_global_diagnostic_table(self) -> QGroupBox:
        box = QGroupBox("Global Counters")
        layout = QVBoxLayout(box)

        self.diag_global_table = QTableWidget(len(GLOBAL_DIAG_COUNTERS), 1)
        self.diag_global_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.diag_global_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.diag_global_table.setHorizontalHeaderLabels(["Value"])
        self.diag_global_table.setVerticalHeaderLabels([name for _counter_id, name in GLOBAL_DIAG_COUNTERS])

        for row, (counter_id, _name) in enumerate(GLOBAL_DIAG_COUNTERS):
            item = QTableWidgetItem("-")
            self.diag_global_items[counter_id] = item
            self.diag_global_table.setItem(row, 0, item)

        layout.addWidget(self.diag_global_table)
        return box

    def _build_diagnostic_info(self) -> QGroupBox:
        box = QGroupBox("Diagnostic Info")
        form = QFormLayout(box)
        fields = [
            ("last_request", "Last Request"),
            ("last_response", "Last Response"),
            ("last_status", "Last Status"),
            ("last_update", "Last Update"),
            ("error", "Error"),
        ]
        for key, title in fields:
            label = QLabel("-")
            self.diag_info_labels[key] = label
            form.addRow(title, label)
        return box

    def _build_log_section(self) -> QGroupBox:
        box = QGroupBox("Log")
        layout = QVBoxLayout(box)

        toolbar = QHBoxLayout()
        toolbar.addStretch(1)
        self.clear_log_button = QPushButton("Clear Log")
        self.clear_log_button.clicked.connect(self.clear_log)
        toolbar.addWidget(self.clear_log_button)
        layout.addLayout(toolbar)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        return box

    def on_driver_mode_changed(self) -> None:
        if self.controller.connected:
            self.disconnect_can()
        mode = self.driver_mode.currentText()
        if mode == "Mock":
            self.driver = MockCanDriver()
        elif mode == "USB-CAN-B Direct":
            self.driver = UsbCanBDriver()
        elif mode == "USB-CAN-B Bridge":
            self.driver = BridgeCanDriver()
        else:
            raise ValueError(f"Unsupported driver mode: {mode}")
        self.controller = ControllerSimulator(self.driver)
        self.controller.set_node_id(self.node_spin.value())
        self.seen_diag_response_count = 0
        self.diag_request_queue.clear()
        self.diag_queue_timer.stop()
        self.reset_request_tracking()
        self.set_update_state("IDLE")
        self.refresh_devices()

    def refresh_devices(self) -> None:
        current = self.device_combo.currentText()
        self.device_combo.clear()
        self.device_combo.addItems(self.driver.list_devices())
        if current:
            self.device_combo.setCurrentText(current)

    def on_node_changed(self, node_id: int) -> None:
        self.controller.set_node_id(node_id)
        self.update_command_mask()

    def on_groups_changed(self, _state: int | None = None) -> None:
        self.update_request_tracking_from_checkboxes()
        self.controller.set_selected_groups(self.selected_groups())
        self.update_command_mask()
        self.update_group_status_labels(self.controller.last_status)

    def selected_groups(self) -> list[int]:
        return [index + 1 for index, checkbox in enumerate(self.group_checks) if checkbox.isChecked()]

    def update_command_mask(self) -> None:
        self.command_mask_label.setText(f"0x{self.controller.get_command_mask():02X}")

    def connect_can(self) -> None:
        try:
            self.controller.connect(
                self.device_combo.currentText(),
                self.channel_spin.value(),
                self.bitrate_spin.value(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Connect failed", str(exc))
            self.log_message(f"ERROR {exc}")
            return

        self.log_message(
            f"Connected mode={self.driver_mode.currentText()} device={self.device_combo.currentText()} "
            f"channel={self.channel_spin.value()} bitrate={self.bitrate_spin.value()}"
        )
        self.set_update_state("IDLE")
        self.controller.last_diag_response = None
        self.controller.diag_response_history.clear()
        self.controller.last_boot_info_response = None
        self.controller.boot_info_response_history.clear()
        self.controller.last_flash_layout_response = None
        self.controller.flash_layout_response_history.clear()
        self.controller.last_flash_self_test_response = None
        self.controller.flash_self_test_response_history.clear()
        self.controller.last_start_update_response = None
        self.controller.start_update_response_history.clear()
        self.controller.last_erase_app_response = None
        self.controller.erase_app_response_history.clear()
        self.controller.last_write_chunk_response = None
        self.controller.write_chunk_response_history.clear()
        self.controller.last_verify_crc_response = None
        self.controller.verify_crc_response_history.clear()
        self.controller.last_simple_update_response = None
        self.controller.simple_update_response_history.clear()
        self.seen_diag_response_count = 0
        self.reset_request_tracking()
        self.update_connected_state()

    def disconnect_can(self) -> None:
        self.stop_periodic()
        self.stop_diagnostic_auto_refresh()
        self.diag_request_queue.clear()
        self.diag_queue_timer.stop()
        self.controller.disconnect()
        self.log_message("Disconnected")
        self.set_update_state("IDLE")
        self.update_connected_state()

    def update_connected_state(self) -> None:
        connected = self.controller.connected
        self.connect_button.setEnabled(not connected)
        self.disconnect_button.setEnabled(connected)
        self.bootloader_button.setEnabled(connected and not self.update_in_progress)
        self.boot_info_button.setEnabled(connected and not self.update_in_progress)
        self.flash_layout_button.setEnabled(connected and not self.update_in_progress)
        self.flash_self_test_button.setEnabled(False)
        self.select_app_bin_button.setEnabled(not self.update_in_progress)
        self.start_update_button.setEnabled(
            connected and
            not self.update_in_progress and
            self.selected_app_bin_info is not None and
            self.selected_app_bin_info.valid
        )
        self.abort_update_button.setEnabled(
            connected and self.update_in_progress and not self.update_abort_requested
        )
        self.reset_to_app_button.setEnabled(
            connected and not self.update_in_progress and self.reset_to_app_allowed
        )
        self.stop_after_chunks_spin.setEnabled(not self.update_in_progress)
        self.force_bad_crc_check.setEnabled(not self.update_in_progress)
        for widget in self.diag_connected_widgets:
            widget.setEnabled(connected)
        if not connected and self.diag_auto_check.isChecked():
            self.diag_auto_check.blockSignals(True)
            self.diag_auto_check.setChecked(False)
            self.diag_auto_check.blockSignals(False)

    def set_update_state(self, state: str) -> None:
        self.update_state = state
        if hasattr(self, "update_state_label"):
            self.update_state_label.setText(state)

    def start_periodic(self) -> None:
        if not self.ensure_connected():
            self._update_periodic_button_state()
            return
        self.periodic_timer.start(self.interval_spin.value())
        self.log_message(f"Periodic TX started interval={self.interval_spin.value()} ms")
        self._update_periodic_button_state()

    def stop_periodic(self) -> None:
        if self.periodic_timer.isActive():
            self.periodic_timer.stop()
            self.log_message("Periodic TX stopped")
        self._update_periodic_button_state()

    def _set_button_active_state(self, button: QPushButton, active: bool) -> None:
        button.setProperty("activeState", active)
        button.setStyleSheet(PERIODIC_ACTIVE_BUTTON_STYLE if active else "")
        button.style().unpolish(button)
        button.style().polish(button)
        button.update()

    def _update_periodic_button_state(self) -> None:
        self._set_button_active_state(self.start_button, self.periodic_timer.isActive())

    def send_once(self) -> None:
        if not self.ensure_connected():
            return
        try:
            frame = self.controller.send_once()
        except Exception as exc:
            QMessageBox.warning(self, "Send failed", str(exc))
            self.log_message(f"ERROR {exc}")
            return
        self.log_frame("TX", frame)
        self.poll_rx()

    def off_all(self) -> None:
        if not self.ensure_connected():
            return
        for checkbox in self.group_checks:
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(False)
        self.controller.set_selected_groups([])
        self.reset_request_tracking()
        self.update_command_mask()
        try:
            frame = self.controller.off_all()
        except Exception as exc:
            QMessageBox.warning(self, "Off All failed", str(exc))
            self.log_message(f"ERROR {exc}")
            return
        self.log_frame("TX", frame)
        self.poll_rx()

    def clear_fault(self) -> None:
        if not self.ensure_connected():
            return
        try:
            frame = self.controller.clear_fault()
        except Exception as exc:
            QMessageBox.warning(self, "Clear Fault failed", str(exc))
            self.log_message(f"ERROR {exc}")
            return
        self.log_frame("TX", frame)
        self.poll_rx()

    def enter_bootloader(self, confirm: bool = True) -> CanFrame | None:
        if not self.ensure_connected():
            return None

        if confirm:
            answer = QMessageBox.question(
                self,
                "Enter bootloader mode",
                "Enter bootloader mode?\nAll outputs will be turned OFF and the application will reset.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return None

        self.stop_periodic()
        self.diag_request_queue.clear()
        self.diag_queue_timer.stop()
        self.stop_diagnostic_auto_refresh()

        try:
            frame = self.controller.send_enter_bootloader()
        except Exception as exc:
            QMessageBox.warning(self, "Enter bootloader failed", str(exc))
            self.log_message(f"ERROR {exc}")
            return None

        self.log_frame("TX", frame)
        self.set_update_state("BOOTLOADER_MODE")
        return frame

    def get_boot_info(self) -> CanFrame | None:
        if not self.ensure_connected():
            return None

        before = len(self.controller.boot_info_response_history)
        try:
            frame = self.controller.send_get_boot_info()
        except Exception as exc:
            QMessageBox.warning(self, "Get boot info failed", str(exc))
            self.log_message(f"ERROR {exc}")
            return None

        self.log_frame("TX", frame)
        self.poll_rx()
        if len(self.controller.boot_info_response_history) > before:
            response = self.controller.boot_info_response_history[-1]
            if response.boot_mode_text == "BOOTLOADER":
                self.set_update_state("BOOTLOADER_MODE")
        return frame

    def get_flash_layout(self) -> CanFrame | None:
        if not self.ensure_connected():
            return None

        try:
            frame = self.controller.send_get_flash_layout()
        except Exception as exc:
            QMessageBox.warning(self, "Get flash layout failed", str(exc))
            self.log_message(f"ERROR {exc}")
            return None

        self.log_frame("TX", frame)
        self.poll_rx()
        return frame

    def run_flash_self_test(self, confirm: bool = True) -> CanFrame | None:
        _ = confirm
        self.log_message("Flash self-test disabled: metadata page 0x0800FC00 is used by firmware update.")
        return None

    def select_app_bin(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Select relocated application .bin",
            "",
            "Binary files (*.bin);;All files (*)",
        )
        if path:
            self.load_app_bin(path)

    def load_app_bin(self, path: str) -> AppBinInfo | None:
        try:
            data = open(path, "rb").read()
        except OSError as exc:
            QMessageBox.warning(self, "Read app .bin failed", str(exc))
            self.log_message(f"ERROR {exc}")
            return None

        info = validate_app_bin_data(data, path)
        self.selected_app_bin_path = path
        self.selected_app_bin_data = data
        self.selected_app_bin_info = info
        self.update_app_bin_labels()
        self.update_connected_state()

        if info.valid:
            self.log_message(
                f"APP_BIN OK size={info.size} CRC32=0x{info.crc32:08X} chunks={info.chunk_count}"
            )
        else:
            self.log_message(f"APP_BIN INVALID {info.error}")
        return info

    def update_app_bin_labels(self) -> None:
        info = self.selected_app_bin_info
        if info is None:
            self.app_bin_path_label.setText("-")
            self.app_bin_info_label.setText("No app .bin selected")
            return

        self.app_bin_path_label.setText(info.path)
        if info.valid:
            self.app_bin_info_label.setText(
                f"OK size={info.size} CRC32=0x{info.crc32:08X} "
                f"SP=0x{info.initial_sp:08X} RESET=0x{info.reset_handler:08X} "
                f"chunks={info.chunk_count}"
            )
        else:
            self.app_bin_info_label.setText(
                f"INVALID size={info.size} CRC32=0x{info.crc32:08X}: {info.error}"
            )

    def wait_for_history_item(self, history: list, start_count: int, timeout_ms: int) -> object | None:
        deadline = time.monotonic() + (timeout_ms / 1000.0)
        while time.monotonic() < deadline:
            self.poll_rx()
            if len(history) > start_count:
                return history[-1]
            QApplication.processEvents()
            time.sleep(0.005)
        return None

    def ensure_bootloader_ready(self) -> bool:
        before = len(self.controller.boot_info_response_history)
        try:
            frame = self.controller.send_get_boot_info()
        except Exception as exc:
            self.log_message(f"ERROR {exc}")
            return False

        self.log_frame("TX", frame)
        response = self.wait_for_history_item(self.controller.boot_info_response_history, before, 2000)
        if not isinstance(response, BootloaderInfoResponse):
            self.log_message("ERROR Bootloader did not respond to GET_BOOT_INFO. Press Enter Bootloader first.")
            return False

        if response.boot_mode_text != "BOOTLOADER":
            self.log_message("ERROR Board is not in bootloader mode.")
            return False

        self.set_update_state("BOOTLOADER_MODE")
        return True

    def require_update_ok(self, stage_name: str, response: object, expected_crc: int | None = None) -> None:
        status = getattr(response, "status", None)
        status_text = getattr(response, "status_text", "UNKNOWN")
        if status != BOOTLOADER_UPDATE_STATUS_OK:
            detail = ""
            if isinstance(response, BootloaderWriteChunkResponse):
                detail = f" seq={response.sequence} next_seq={response.next_sequence}"
            elif isinstance(response, BootloaderVerifyCrcResponse):
                detail = f" actual=0x{response.actual_crc:08X}"
                if expected_crc is not None:
                    detail += f" expected=0x{expected_crc:08X}"
            raise RuntimeError(f"{stage_name} failed: {status_text}{detail}")

    def start_firmware_update(self, confirm: bool = True) -> None:
        if not self.ensure_connected():
            return

        info = self.selected_app_bin_info
        if info is None or not info.valid:
            QMessageBox.warning(self, "Invalid app .bin", "Select a valid relocated application .bin first.")
            self.log_message("ERROR invalid app .bin; START_UPDATE not sent.")
            return

        if confirm:
            answer = QMessageBox.question(
                self,
                "Start CAN firmware update",
                "Start CAN firmware update?\n"
                "This will erase and rewrite the application region.\n"
                "All outputs must remain OFF.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self.stop_periodic()
        self.diag_request_queue.clear()
        self.diag_queue_timer.stop()
        self.stop_diagnostic_auto_refresh()

        if not self.ensure_bootloader_ready():
            QMessageBox.warning(self, "Bootloader not ready", "Press Enter Bootloader first, then retry.")
            return

        self.update_in_progress = True
        self.update_abort_requested = False
        self.reset_to_app_allowed = False
        self.set_update_state("UPDATING")
        self.update_connected_state()
        self.update_progress.setValue(0)

        try:
            self.run_update_sequence(info, self.selected_app_bin_data)
            self.update_progress.setValue(100)
            self.reset_to_app_allowed = True
            self.set_update_state("DONE")
            self.log_message("FIRMWARE_UPDATE DONE. Use Reset To App or reset/power cycle the board.")
        except FirmwareUpdateAborted:
            self.reset_to_app_allowed = False
            self.set_update_state("ABORTED")
            self.log_message("Firmware update stopped after user abort.")
        except FirmwareUpdateStoppedForTest as exc:
            self.reset_to_app_allowed = False
            self.set_update_state("FAILED")
            self.log_message(str(exc))
        except Exception as exc:
            self.reset_to_app_allowed = False
            self.set_update_state("FAILED")
            self.log_message(f"ERROR firmware update stopped: {exc}")
            QMessageBox.warning(self, "Firmware update stopped", str(exc))
        finally:
            self.update_in_progress = False
            self.update_connected_state()

    def stop_if_abort_requested(self, stage_name: str) -> None:
        if self.update_abort_requested:
            self.log_message(f"{stage_name} stopped because abort was requested.")
            raise FirmwareUpdateAborted("Firmware update aborted by user.")

    def run_update_sequence(self, info: AppBinInfo, data: bytes) -> None:
        stop_after_chunks = self.stop_after_chunks_spin.value()
        self.stop_if_abort_requested("START_UPDATE")
        before = len(self.controller.start_update_response_history)
        frame = self.controller.send_start_update(info.size, 0)
        self.log_frame("TX", frame)
        response = self.wait_for_history_item(self.controller.start_update_response_history, before, 1500)
        if not isinstance(response, BootloaderStartUpdateResponse):
            raise TimeoutError("START_UPDATE timeout")
        self.stop_if_abort_requested("START_UPDATE")
        self.require_update_ok("START_UPDATE", response)
        self.log_message(f"START_UPDATE OK size={response.app_size}")

        self.stop_if_abort_requested("ERASE_APP")
        before = len(self.controller.erase_app_response_history)
        frame = self.controller.send_erase_app()
        self.log_frame("TX", frame)
        response = self.wait_for_history_item(self.controller.erase_app_response_history, before, 8000)
        if not isinstance(response, BootloaderEraseAppResponse):
            raise TimeoutError("ERASE_APP timeout")
        self.stop_if_abort_requested("ERASE_APP")
        self.require_update_ok("ERASE_APP", response)
        self.log_message(f"ERASE_APP OK pages={response.erased_pages}")

        for sequence, offset in enumerate(range(0, info.size, 4)):
            self.stop_if_abort_requested(f"WRITE_CHUNK seq={sequence}")
            payload = data[offset:offset + 4]
            before = len(self.controller.write_chunk_response_history)
            frame = self.controller.send_write_chunk(sequence, payload)
            if sequence < 3 or sequence + 1 == info.chunk_count or (sequence % 256) == 0:
                self.log_frame("TX", frame)
            response = self.wait_for_history_item(self.controller.write_chunk_response_history, before, 1500)
            if not isinstance(response, BootloaderWriteChunkResponse):
                raise TimeoutError(f"WRITE_CHUNK seq={sequence} timeout")
            if self.update_abort_requested:
                if response.status != BOOTLOADER_UPDATE_STATUS_OK:
                    self.log_message("Late WRITE_CHUNK response ignored after abort.")
                raise FirmwareUpdateAborted("Firmware update aborted by user.")
            self.require_update_ok(f"WRITE_CHUNK seq={sequence}", response)
            if response.next_sequence != sequence + 1:
                raise RuntimeError(
                    f"WRITE_CHUNK seq={sequence} bad next_seq={response.next_sequence}"
                )

            progress = int(((sequence + 1) * 100) / info.chunk_count)
            self.update_progress.setValue(progress)
            if sequence == 0 or sequence + 1 == info.chunk_count or (sequence % 256) == 0:
                self.log_message(f"WRITE seq={sequence} OK progress={progress}%")
            if stop_after_chunks > 0 and (sequence + 1) >= stop_after_chunks:
                raise FirmwareUpdateStoppedForTest(
                    f"Advanced stop after {stop_after_chunks} chunks reached. "
                    "No ABORT_UPDATE sent; reset/power-cycle the board to test recovery."
                )

        self.stop_if_abort_requested("VERIFY_CRC")
        before = len(self.controller.verify_crc_response_history)
        verify_crc = info.crc32
        if self.force_bad_crc_check.isChecked():
            verify_crc ^= 0x00000001
            self.log_message(
                f"Force Bad CRC enabled: real=0x{info.crc32:08X} sent=0x{verify_crc:08X}"
            )
        frame = self.controller.send_verify_crc(verify_crc)
        self.log_frame("TX", frame)
        response = self.wait_for_history_item(self.controller.verify_crc_response_history, before, 5000)
        if not isinstance(response, BootloaderVerifyCrcResponse):
            raise TimeoutError("VERIFY_CRC timeout")
        self.stop_if_abort_requested("VERIFY_CRC")
        self.require_update_ok("VERIFY_CRC", response, expected_crc=verify_crc)
        if response.actual_crc != info.crc32:
            raise RuntimeError(
                f"VERIFY_CRC actual=0x{response.actual_crc:08X} expected=0x{info.crc32:08X}"
            )
        self.log_message(f"VERIFY_CRC OK crc=0x{response.actual_crc:08X}")

        self.stop_if_abort_requested("FINISH_UPDATE")
        before = len(self.controller.simple_update_response_history)
        frame = self.controller.send_finish_update()
        self.log_frame("TX", frame)
        response = self.wait_for_history_item(self.controller.simple_update_response_history, before, 3000)
        if not isinstance(response, BootloaderSimpleUpdateResponse):
            raise TimeoutError("FINISH_UPDATE timeout")
        if response.response_type != BOOTLOADER_RESP_FINISH_UPDATE:
            raise RuntimeError("Unexpected response while waiting FINISH_UPDATE")
        self.stop_if_abort_requested("FINISH_UPDATE")
        self.require_update_ok("FINISH_UPDATE", response)
        self.log_message("FINISH_UPDATE OK metadata valid")

    def abort_update(self) -> CanFrame | None:
        if not self.ensure_connected():
            return None

        if not self.update_in_progress:
            self.log_message("Abort Update ignored: no active firmware update session.")
            return None

        self.update_abort_requested = True
        self.update_connected_state()

        before = len(self.controller.simple_update_response_history)
        try:
            frame = self.controller.send_abort_update()
        except Exception as exc:
            QMessageBox.warning(self, "Abort update failed", str(exc))
            self.log_message(f"ERROR {exc}")
            return None

        self.log_frame("TX", frame)
        response = self.wait_for_history_item(self.controller.simple_update_response_history, before, 1000)
        if isinstance(response, BootloaderSimpleUpdateResponse) and response.response_type == BOOTLOADER_RESP_ABORT_UPDATE:
            if response.status == BOOTLOADER_UPDATE_STATUS_OK:
                self.reset_to_app_allowed = False
                self.set_update_state("ABORTED")
                self.log_message("Firmware update aborted by user.")
            else:
                self.log_message(f"ABORT_UPDATE {response.status_text}")
        self.update_connected_state()
        return frame

    def reset_to_app(self) -> CanFrame | None:
        if not self.ensure_connected():
            return None

        if not self.reset_to_app_allowed:
            QMessageBox.warning(
                self,
                "Reset to app disabled",
                "Application is not known valid after abort or failed update.",
            )
            self.log_message("RESET_TO_APP blocked: app is not known valid.")
            return None

        before = len(self.controller.simple_update_response_history)
        try:
            frame = self.controller.send_reset_to_app()
        except Exception as exc:
            QMessageBox.warning(self, "Reset to app failed", str(exc))
            self.log_message(f"ERROR {exc}")
            return None

        self.log_frame("TX", frame)
        response = self.wait_for_history_item(self.controller.simple_update_response_history, before, 1000)
        if isinstance(response, BootloaderSimpleUpdateResponse) and response.response_type == BOOTLOADER_RESP_RESET_TO_APP:
            if response.status == BOOTLOADER_UPDATE_STATUS_OK:
                self.log_message("RESET_TO_APP OK")
                self.set_update_state("IDLE")
            else:
                self.log_message(f"RESET_TO_APP {response.status_text}")
        return frame

    def clear_log(self) -> None:
        self.log_text.clear()

    def update_diag_counter_options(self, _index: int | None = None) -> None:
        if not hasattr(self, "diag_counter_combo"):
            return

        group_index = self.diag_scope_combo.currentData()
        definitions = GLOBAL_DIAG_COUNTERS if group_index == DIAG_GROUP_GLOBAL else GROUP_DIAG_COUNTERS

        self.diag_counter_combo.blockSignals(True)
        self.diag_counter_combo.clear()
        for counter_id, name in definitions:
            self.diag_counter_combo.addItem(f"0x{counter_id:02X} - {name}", counter_id)
        self.diag_counter_combo.blockSignals(False)

    def read_selected_diagnostic_counter(self, _checked: bool | None = None) -> CanFrame | None:
        if not self.ensure_connected():
            return None

        counter_id = self.diag_counter_combo.currentData()
        group_index = self.diag_scope_combo.currentData()
        if counter_id is None or group_index is None:
            return None

        return self.send_diagnostic_read_request(int(counter_id), int(group_index))

    def read_all_diagnostic_counters(self, _checked: bool | None = None) -> None:
        if not self.ensure_connected():
            return
        if self.diag_queue_timer.isActive():
            return

        self.diag_request_queue = [
            (counter_id, group_index)
            for group_index in range(GROUP_COUNT)
            for counter_id, _name in GROUP_DIAG_COUNTERS
        ]
        self.diag_request_queue.extend((counter_id, DIAG_GROUP_GLOBAL) for counter_id, _name in GLOBAL_DIAG_COUNTERS)
        self.send_next_diagnostic_request()
        if self.diag_request_queue:
            self.diag_queue_timer.start()

    def send_next_diagnostic_request(self) -> None:
        if not (self.controller.connected and self.driver.is_open()):
            self.diag_request_queue.clear()
            self.diag_queue_timer.stop()
            return

        if not self.diag_request_queue:
            self.diag_queue_timer.stop()
            return

        counter_id, group_index = self.diag_request_queue.pop(0)
        self.send_diagnostic_read_request(counter_id, group_index)
        if not self.diag_request_queue:
            self.diag_queue_timer.stop()

    def send_diagnostic_read_request(self, counter_id: int, group_index: int) -> CanFrame | None:
        try:
            frame = self.controller.send_diag_read_counter(counter_id, group_index)
        except Exception as exc:
            QMessageBox.warning(self, "Diagnostic read failed", str(exc))
            self.log_message(f"ERROR {exc}")
            self.diag_info_labels["error"].setText(str(exc))
            return None

        self.diag_info_labels["last_request"].setText(
            f"READ {counter_id_to_name(counter_id)} / {group_index_to_name(group_index)}"
        )
        self.log_frame("TX", frame)
        self.poll_rx()
        return frame

    def reset_all_diagnostics(self, confirm: bool = True) -> CanFrame | None:
        if not self.ensure_connected():
            return None

        if confirm:
            answer = QMessageBox.question(
                self,
                "Reset diagnostic counters",
                "Reset all runtime diagnostic counters? This cannot be undone until events happen again.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return None

        try:
            frame = self.controller.send_diag_reset_all()
        except Exception as exc:
            QMessageBox.warning(self, "Diagnostic reset failed", str(exc))
            self.log_message(f"ERROR {exc}")
            self.diag_info_labels["error"].setText(str(exc))
            return None

        self.diag_info_labels["last_request"].setText("RESET_ALL_COUNTERS")
        self.log_frame("TX", frame)
        self.poll_rx()
        return frame

    def clear_diagnostic_display(self, _checked: bool | None = None) -> None:
        self.set_all_diagnostic_cells("-")
        for label in self.diag_info_labels.values():
            label.setText("-")

    def on_diag_auto_refresh_changed(self, _state: int | None = None) -> None:
        if self.diag_auto_check.isChecked():
            if not self.ensure_connected():
                self.diag_auto_check.blockSignals(True)
                self.diag_auto_check.setChecked(False)
                self.diag_auto_check.blockSignals(False)
                return
            self.diag_auto_timer.start(self.diag_auto_interval_spin.value())
            self.log_message(f"Diagnostic auto refresh started interval={self.diag_auto_interval_spin.value()} ms")
            self.read_all_diagnostic_counters()
        else:
            self.stop_diagnostic_auto_refresh()

    def on_diag_auto_interval_changed(self, _value: int | None = None) -> None:
        if self.diag_auto_timer.isActive():
            self.diag_auto_timer.start(self.diag_auto_interval_spin.value())

    def stop_diagnostic_auto_refresh(self) -> None:
        if self.diag_auto_timer.isActive():
            self.diag_auto_timer.stop()
            self.log_message("Diagnostic auto refresh stopped")

    def ensure_connected(self) -> bool:
        if self.controller.connected and self.driver.is_open():
            return True
        QMessageBox.warning(self, "CAN not connected", "Please connect CAN before sending commands.")
        return False

    def reset_request_tracking(self) -> None:
        self.checkbox_requested_state = [checkbox.isChecked() for checkbox in self.group_checks]
        self.actual_do_was_on_since_requested = [False] * GROUP_COUNT

    def update_request_tracking_from_checkboxes(self) -> None:
        for group_index, checkbox in enumerate(self.group_checks):
            requested = checkbox.isChecked()
            was_requested = self.checkbox_requested_state[group_index]
            if not requested or (requested and not was_requested):
                self.actual_do_was_on_since_requested[group_index] = False
            self.checkbox_requested_state[group_index] = requested

    def poll_rx(self) -> None:
        for frame in self.controller.poll_rx():
            self.log_frame("RX", frame)
        self.process_new_diagnostic_responses()
        self.update_status_labels()

    def process_new_diagnostic_responses(self) -> None:
        history = self.controller.diag_response_history
        while self.seen_diag_response_count < len(history):
            response = history[self.seen_diag_response_count]
            self.seen_diag_response_count += 1
            self.handle_diagnostic_response(response)

    def handle_diagnostic_response(
        self,
        response: DiagnosticCounterResponse | DiagnosticResetResponse | DiagnosticErrorResponse,
    ) -> None:
        now_text = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.diag_info_labels["last_update"].setText(now_text)
        self.diag_info_labels["last_status"].setText(response.status_text)

        if isinstance(response, DiagnosticCounterResponse):
            description = (
                f"{counter_id_to_name(response.counter_id)} / "
                f"{group_index_to_name(response.group_index)} = {response.value}"
            )
            self.diag_info_labels["last_response"].setText(description)
            if response.status == DIAG_STATUS_OK:
                self.set_diagnostic_counter_cell(response.counter_id, response.group_index, str(response.value))
                self.diag_info_labels["error"].setText("-")
            else:
                self.diag_info_labels["error"].setText(
                    f"{response.status_text}: {counter_id_to_name(response.counter_id)} / "
                    f"{group_index_to_name(response.group_index)}"
                )
            return

        if isinstance(response, DiagnosticResetResponse):
            self.diag_info_labels["last_response"].setText(f"RESET_ALL_COUNTERS {response.status_text}")
            if response.status == DIAG_STATUS_OK:
                self.set_all_diagnostic_cells("0")
                self.diag_info_labels["error"].setText("-")
            else:
                self.diag_info_labels["error"].setText(response.status_text)
            return

        self.diag_info_labels["last_response"].setText(
            f"ERROR command=0x{response.command:02X} "
            f"{counter_id_to_name(response.counter_id)} / {group_index_to_name(response.group_index)}"
        )
        self.diag_info_labels["error"].setText(response.status_text)

    def set_diagnostic_counter_cell(self, counter_id: int, group_index: int, value: str) -> None:
        if group_index == DIAG_GROUP_GLOBAL:
            item = self.diag_global_items.get(counter_id)
        else:
            item = self.diag_group_items.get((group_index, counter_id))

        if item is not None:
            item.setText(value)

    def set_all_diagnostic_cells(self, value: str) -> None:
        for item in self.diag_group_items.values():
            item.setText(value)
        for item in self.diag_global_items.values():
            item.setText(value)

    def update_status_labels(self) -> None:
        status = self.controller.last_status
        heartbeat = self.controller.last_heartbeat

        if status is not None:
            self.sync_requested_groups_from_status(status)
            self.status_labels["do_mask"].setText(f"0x{status.do_mask:02X}")
            self.status_labels["feedback_mask"].setText(f"0x{status.feedback_mask:04X}")
            self.status_labels["fault_mask"].setText(f"0x{status.fault_mask:02X}")
            self.status_labels["global_status"].setText(f"0x{status.global_status:02X}")
            self.status_labels["can_online"].setText("Yes" if status.can_online else "No")
            self.status_labels["any_fault"].setText("Yes" if status.any_fault else "No")
            self.status_labels["failsafe_active"].setText("Yes" if status.failsafe_active else "No")

        if heartbeat is not None:
            self.status_labels["fw_version"].setText(heartbeat.fw_version)
            self.status_labels["heartbeat_sequence"].setText(str(heartbeat.sequence))

        self.update_group_status_labels(status)

    def sync_requested_groups_from_status(self, status: BoardStatus) -> None:
        if status.failsafe_active:
            self.auto_uncheck_all_for_failsafe()
            return

        self.auto_uncheck_faulted_groups(status)
        self.auto_uncheck_stale_do_off_groups(status)

    def auto_uncheck_all_for_failsafe(self) -> None:
        changed = False
        for checkbox in self.group_checks:
            if checkbox.isChecked():
                checkbox.blockSignals(True)
                checkbox.setChecked(False)
                checkbox.blockSignals(False)
                changed = True

        if changed:
            self.controller.set_selected_groups([])
            self.update_command_mask()
            self.reset_request_tracking()
            self.log_message("Failsafe/CAN timeout detected, all requested groups auto-unchecked.")

        if self.periodic_timer.isActive():
            self.periodic_timer.stop()
            self.log_message("Periodic TX stopped because failsafe/CAN timeout was detected.")
            self._update_periodic_button_state()

    def auto_uncheck_faulted_groups(self, status: BoardStatus) -> None:
        changed = False
        for group_index, checkbox in enumerate(self.group_checks):
            group_number = group_index + 1
            group_bit = 1 << group_index
            if (status.fault_mask & group_bit) and checkbox.isChecked():
                checkbox.blockSignals(True)
                checkbox.setChecked(False)
                checkbox.blockSignals(False)
                self.checkbox_requested_state[group_index] = False
                self.actual_do_was_on_since_requested[group_index] = False
                self.log_message(f"Group {group_number} fault detected, auto-unchecked.")
                changed = True

        if changed:
            self.controller.set_selected_groups(self.selected_groups())
            self.update_command_mask()

    def auto_uncheck_stale_do_off_groups(self, status: BoardStatus) -> None:
        changed = False

        for group_index, checkbox in enumerate(self.group_checks):
            group_number = group_index + 1
            group_bit = 1 << group_index
            requested = checkbox.isChecked()
            do_on = bool(status.do_mask & group_bit)
            fault = bool(status.fault_mask & group_bit)

            if not requested:
                self.actual_do_was_on_since_requested[group_index] = False
                continue

            if do_on:
                self.actual_do_was_on_since_requested[group_index] = True
                continue

            if not fault and self.actual_do_was_on_since_requested[group_index]:
                checkbox.blockSignals(True)
                checkbox.setChecked(False)
                checkbox.blockSignals(False)
                self.checkbox_requested_state[group_index] = False
                self.actual_do_was_on_since_requested[group_index] = False
                self.log_message(f"Group {group_number} actual DO dropped OFF while requested ON, auto-unchecked.")
                changed = True

        if changed:
            self.controller.set_selected_groups(self.selected_groups())
            self.update_command_mask()

    def update_group_status_labels(self, status: BoardStatus | None) -> None:
        for group_index, labels in enumerate(self.group_status_labels):
            group_bit = 1 << group_index
            requested = self.group_checks[group_index].isChecked()
            labels["requested"].setText("ON" if requested else "OFF")

            if status is None:
                labels["do"].setText("-")
                labels["feedback"].setText("P=- / N=-")
                labels["fault"].setText("-")
                labels["fault"].setStyleSheet("")
                continue

            do_on = bool(status.do_mask & group_bit)
            feedback_p = bool(status.feedback_mask & (1 << (group_index * 2)))
            feedback_n = bool(status.feedback_mask & (1 << (group_index * 2 + 1)))
            fault = bool(status.fault_mask & group_bit)

            labels["do"].setText("ON" if do_on else "OFF")
            labels["feedback"].setText(
                f"P={'ON' if feedback_p else 'OFF'} / N={'ON' if feedback_n else 'OFF'}"
            )
            labels["fault"].setText("Yes" if fault else "No")
            labels["fault"].setStyleSheet("color: #b00020; font-weight: 600;" if fault else "")

    def log_frame(self, direction: str, frame: CanFrame) -> None:
        boot_label = " BOOT" if self.is_bootloader_frame(frame.can_id) else ""
        diag_label = " DIAG" if not boot_label and self.is_diagnostic_frame(frame.can_id) else ""
        suffix = ""
        if boot_label:
            suffix = self.format_bootloader_log_suffix(direction, frame)
        elif diag_label:
            suffix = self.format_diagnostic_log_suffix(direction, frame)
        self.log_message(
            f"{direction}{boot_label}{diag_label} ID={format_can_id(frame.can_id)} DLC={frame.dlc} "
            f"DATA={format_hex_data(frame.data)}{suffix}"
        )

    def is_bootloader_frame(self, can_id: int) -> bool:
        request_min = BOOTLOADER_REQUEST_ID_BASE
        request_max = BOOTLOADER_REQUEST_ID_BASE + NODE_ID_MAX
        response_min = BOOTLOADER_RESPONSE_ID_BASE
        response_max = BOOTLOADER_RESPONSE_ID_BASE + NODE_ID_MAX
        return request_min <= can_id <= request_max or response_min <= can_id <= response_max

    def is_diagnostic_frame(self, can_id: int) -> bool:
        request_min = DIAG_REQUEST_ID_BASE
        request_max = DIAG_REQUEST_ID_BASE + NODE_ID_MAX
        response_min = DIAG_RESPONSE_ID_BASE
        response_max = DIAG_RESPONSE_ID_BASE + NODE_ID_MAX
        return request_min <= can_id <= request_max or response_min <= can_id <= response_max

    def format_bootloader_log_suffix(self, direction: str, frame: CanFrame) -> str:
        if direction != "RX":
            return ""

        response = decode_bootloader_info_frame(frame, self.controller.node_id)
        if isinstance(response, BootloaderInfoResponse):
            suffix = (
                f" BL={response.bl_major}.{response.bl_minor} "
                f"APP_VALID={1 if response.app_valid else 0} MODE={response.boot_mode_text}"
            )
            if response.status_text != "OK":
                suffix += f" STATUS={response.status_text}"
            return suffix

        flash_layout = decode_bootloader_flash_layout_frame(frame, self.controller.node_id)
        if isinstance(flash_layout, BootloaderFlashLayoutResponse):
            return (
                f" PAGE={flash_layout.page_kb}KB BOOT={flash_layout.boot_kb}KB "
                f"APP={flash_layout.app_kb}KB SCRATCH_PAGE={flash_layout.scratch_page_index}"
            )

        flash_self_test = decode_bootloader_flash_self_test_frame(frame, self.controller.node_id)
        if isinstance(flash_self_test, BootloaderFlashSelfTestResponse):
            if flash_self_test.status_text == "OK":
                return " FLASH_TEST=OK"
            return (
                f" FLASH_TEST=FAIL STATUS={flash_self_test.status_text} "
                f"STAGE={flash_self_test.stage_text} DETAIL={format_hex_data(flash_self_test.detail)}"
            )

        start_update = decode_bootloader_start_update_frame(frame, self.controller.node_id)
        if isinstance(start_update, BootloaderStartUpdateResponse):
            return (
                f" START_UPDATE STATUS={start_update.status_text} "
                f"STAGE={start_update.stage_text} SIZE={start_update.app_size}"
            )

        erase_app = decode_bootloader_erase_app_frame(frame, self.controller.node_id)
        if isinstance(erase_app, BootloaderEraseAppResponse):
            return (
                f" ERASE_APP STATUS={erase_app.status_text} "
                f"STAGE={erase_app.stage_text} PAGES={erase_app.erased_pages}"
            )

        write_chunk = decode_bootloader_write_chunk_frame(frame, self.controller.node_id)
        if isinstance(write_chunk, BootloaderWriteChunkResponse):
            return (
                f" WRITE_CHUNK STATUS={write_chunk.status_text} "
                f"SEQ={write_chunk.sequence} NEXT={write_chunk.next_sequence}"
            )

        verify_crc = decode_bootloader_verify_crc_frame(frame, self.controller.node_id)
        if isinstance(verify_crc, BootloaderVerifyCrcResponse):
            return f" VERIFY_CRC STATUS={verify_crc.status_text} CRC=0x{verify_crc.actual_crc:08X}"

        simple_update = decode_bootloader_simple_update_frame(frame, self.controller.node_id)
        if isinstance(simple_update, BootloaderSimpleUpdateResponse):
            return (
                f" {bootloader_update_response_name(simple_update.response_type)} "
                f"STATUS={simple_update.status_text}"
            )
        return ""

    def format_diagnostic_log_suffix(self, direction: str, frame: CanFrame) -> str:
        if direction != "RX":
            return ""

        response = decode_diag_response_frame(frame, self.controller.node_id)
        if isinstance(response, DiagnosticCounterResponse):
            return f" VALUE={response.value} STATUS={response.status_text}"
        if isinstance(response, DiagnosticResetResponse):
            return f" STATUS={response.status_text}"
        if isinstance(response, DiagnosticErrorResponse):
            return f" COMMAND=0x{response.command:02X} STATUS={response.status_text}"
        return ""

    def log_message(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_text.appendPlainText(f"[{timestamp}] {message}")


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
