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


@dataclass(slots=True)
class BootloaderFlashLayoutResponse:
    response_type: int
    status: int
    status_text: str
    page_kb: int
    boot_kb: int
    app_kb: int
    scratch_page_index: int
    flags: int


@dataclass(slots=True)
class BootloaderFlashSelfTestResponse:
    response_type: int
    status: int
    status_text: str
    stage: int
    stage_text: str
    detail: bytes


@dataclass(slots=True)
class BootloaderAppStatusSummaryResponse:
    response_type: int
    status: int
    status_text: str
    metadata_state: int
    metadata_state_text: str
    app_valid: bool
    vector_valid: bool
    info_source: int
    info_source_text: str
    session_state: int
    session_state_text: str
    flags: int


@dataclass(slots=True)
class BootloaderAppSizeInfoResponse:
    response_type: int
    status: int
    status_text: str
    app_size: int
    max_app_kb: int
    flags: int
    size_available: bool


@dataclass(slots=True)
class BootloaderStoredCrcResponse:
    response_type: int
    status: int
    status_text: str
    stored_crc32: int
    crc_source: int
    crc_source_text: str
    flags: int
    crc_available: bool


@dataclass(slots=True)
class BootloaderComputedCrcResponse:
    response_type: int
    status: int
    status_text: str
    computed_crc32: int
    crc_match: bool
    flags: int
    crc_available: bool


@dataclass(slots=True)
class BootloaderMetadataVersionResponse:
    response_type: int
    status: int
    status_text: str
    metadata_version: int
    magic_ok: bool
    flags: int
    version_available: bool


@dataclass(slots=True)
class BootloaderStartUpdateResponse:
    response_type: int
    status: int
    status_text: str
    stage: int
    stage_text: str
    app_size: int


@dataclass(slots=True)
class BootloaderEraseAppResponse:
    response_type: int
    status: int
    status_text: str
    stage: int
    stage_text: str
    erased_pages: int


@dataclass(slots=True)
class BootloaderWriteChunkResponse:
    response_type: int
    status: int
    status_text: str
    sequence: int
    next_sequence: int
    detail: bytes


@dataclass(slots=True)
class BootloaderVerifyCrcResponse:
    response_type: int
    status: int
    status_text: str
    actual_crc: int


@dataclass(slots=True)
class BootloaderSimpleUpdateResponse:
    response_type: int
    status: int
    status_text: str


@dataclass(slots=True)
class AppBinInfo:
    path: str
    size: int
    crc32: int
    chunk_count: int
    initial_sp: int
    reset_handler: int
    valid: bool
    error: str
