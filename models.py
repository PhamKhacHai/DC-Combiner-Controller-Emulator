from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CanFrame:
    can_id: int
    data: bytes
    dlc: int
    extended: bool = False
    rtr: bool = False
    timestamp: float = 0.0


@dataclass(slots=True)
class BoardStatus:
    do_mask: int
    feedback_mask: int
    fault_mask: int
    global_status: int
    can_online: bool
    any_fault: bool
    failsafe_active: bool


@dataclass(slots=True)
class HeartbeatStatus:
    fw_version: str
    node_id: int
    global_status: int
    can_online: bool
    any_fault: bool
    failsafe_active: bool
    rx_count_low: int
    tx_error_count_low: int
    sequence: int


@dataclass(slots=True)
class DiagnosticCounterResponse:
    response_type: int
    counter_id: int
    group_index: int
    value: int
    status: int
    status_text: str


@dataclass(slots=True)
class DiagnosticResetResponse:
    response_type: int
    counter_id: int
    group_index: int
    status: int
    status_text: str


@dataclass(slots=True)
class DiagnosticErrorResponse:
    response_type: int
    command: int
    counter_id: int
    group_index: int
    status: int
    status_text: str


@dataclass(slots=True)
class BootloaderInfoResponse:
    response_type: int
    status: int
    status_text: str
    bl_major: int
    bl_minor: int
    app_valid: bool
    boot_mode: int
    boot_mode_text: str
