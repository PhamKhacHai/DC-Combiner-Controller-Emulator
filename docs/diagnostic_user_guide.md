# Diagnostic User Guide

Tài liệu này hướng dẫn dùng Diagnostics tab trong Controller Emulator.

## Mục đích

Diagnostics tab dùng để đọc runtime counters trong firmware `DC_Combiner_MCU_IO_FW`.

Ghi chú:

- Counters nằm trong RAM.
- Counters reset khi MCU reset hoặc mất nguồn.
- Diagnostic request không thay đổi command/status/heartbeat protocol.
- Diagnostic reads không refresh CAN command timeout.
- Diagnostic reads không bật/tắt output, không clear fault, không thoát fail-safe.

## CAN IDs

```text
Request:  0x530 + NodeID
Response: 0x540 + NodeID
DLC request: 8 từ tool
DLC response: 8
Frame: Standard Data Frame
```

## Cách dùng trong UI

1. Connect bằng `Mock`, `USB-CAN-B Direct` hoặc `USB-CAN-B Bridge`.
2. Vào tab `Diagnostics`.
3. Chọn `Scope`: `Group 1..6` hoặc `Global`.
4. Chọn `Counter`.
5. Bấm `Read Selected Counter` để đọc một counter.
6. Bấm `Read All Counters` để đọc toàn bộ group/global counters bằng queue có pacing.
7. Tick `Auto Refresh` nếu muốn đọc định kỳ.
8. Chọn interval `200..10000 ms`, mặc định `1000 ms`.
9. Bấm `Reset All Counters` nếu muốn reset counter RAM trong firmware.
10. Bấm `Clear Diagnostic Display` nếu chỉ muốn xóa bảng hiển thị trên PC.

`Clear Diagnostic Display` không gửi CAN và không reset counter firmware.

## Lưu ý an toàn

- Diagnostic reads không refresh firmware CAN command timeout.
- Nếu output cần giữ ON trong lúc đọc counter, dùng periodic command.
- Test `Off All` trước khi bật group.
- Không chạy vendor CAN tool cùng lúc với Controller Emulator.
- Kiểm tra CAN_H, CAN_L và GND trước khi test board thật.
- Không dùng diagnostics để điều khiển output.

## Mock mode

`Mock` mode không cần board, không cần USB-CAN-B và không cần driver. Dùng mode này để kiểm tra UI, request/response diagnostic và bảng counter giả lập.

## Real board mode

Khi test board thật, ưu tiên `USB-CAN-B Bridge`. Máy test cần driver USB-CAN-B, `ControlCAN.dll`, wiring đúng và bitrate `500000`.

Chi tiết setup xem [usb_can_b_setup.md](usb_can_b_setup.md).

## Counter list

### Group counters

Dùng group index `0..5`.

| Counter ID | Tên |
| ---: | --- |
| `0x01` | ON Count |
| `0x02` | OFF Count |
| `0x03` | Feedback Mismatch |
| `0x04` | Group Fault |
| `0x05` | ON Timeout Fault |
| `0x06` | Unexpected OFF Fault |
| `0x07` | Fault Clear |

### Global counters

Dùng group index `0xFF`.

| Counter ID | Tên |
| ---: | --- |
| `0x20` | CAN Command RX Count |
| `0x21` | CAN TX Count |
| `0x22` | CAN RX Error Count |
| `0x23` | CAN TX Error Count |
| `0x24` | CAN Timeout Count |
| `0x25` | Failsafe Enter Count |
| `0x26` | Diagnostic Request Count |
| `0x27` | Diagnostic Error Count |

## Diagnostic status

| Status | Ý nghĩa |
| ---: | --- |
| `0x00` | `OK` |
| `0x01` | `INVALID_COMMAND` |
| `0x02` | `INVALID_COUNTER_ID` |
| `0x03` | `INVALID_GROUP` |
| `0x04` | `BAD_DLC` |
| `0x05` | `RESET_MAGIC_INVALID` |
| `0x06` | `INTERNAL_ERROR` |

## Expected frames

Đọc `CAN Timeout Count`:

```text
TX 0x530: 01 24 FF 00 00 00 00 00
RX 0x540: 81 24 FF vv vv vv vv 00
```

Trong đó `vv vv vv vv` là counter value `uint32` little-endian.

Reset all counters:

```text
TX 0x530: 02 A5 5A 00 00 00 00 00
RX 0x540: 82 00 FF 00 00 00 00 00
```

Ví dụ lỗi reset magic:

```text
TX 0x530: 02 00 00 00 00 00 00 00
RX 0x540: 82 00 FF 00 00 00 00 05
```

`Data[7] = 0x05` nghĩa là `RESET_MAGIC_INVALID`.

## Test plan diagnostic

### Mock mode

1. Mở `DC Combiner Controller Emulator`.
2. Chọn `Driver mode = Mock`.
3. Bấm `Connect`.
4. Vào tab `Diagnostics`.
5. Bấm `Read All Counters`.
6. Kiểm tra bảng group/global có giá trị số.
7. Bật Group 1 bằng `Send Once`.
8. Đọc `Group 1 / ON Count`.
9. Kỳ vọng giá trị tăng.
10. Bấm `Off All`.
11. Đọc `Group 1 / OFF Count`.
12. Kỳ vọng giá trị tăng.
13. Bấm `Reset All Counters` và confirm.
14. Kiểm tra các counter hiển thị về `0`.

### Bridge mode real board

1. Đóng vendor CAN tool.
2. Nối USB-CAN-B vào CAN bus của board.
3. Chọn `Driver mode = USB-CAN-B Bridge`.
4. Set `Node ID = 0` hoặc đúng DIP switch.
5. Set `Bitrate = 500000`.
6. Bấm `Connect`.
7. Bấm `Off All`.
8. Vào tab `Diagnostics`.
9. Bấm `Read All Counters`.
10. Kiểm tra log có RX frame `0x540 + NodeID`.
11. Nếu cần giữ group ON, bật periodic command.
12. Bật Group 1 với feedback hợp lệ.
13. Đọc `Group 1 / ON Count`.
14. Kỳ vọng tăng ít nhất `1`.
15. Bấm `Off All`.
16. Đọc `Group 1 / OFF Count`.
17. Kỳ vọng tăng ít nhất `1`.
18. Chỉ tạo feedback mismatch hoặc group fault khi bench setup an toàn.
19. Đọc `Feedback Mismatch`, `Group Fault`, `ON Timeout Fault` hoặc `Unexpected OFF Fault`.
20. Kỳ vọng counter liên quan tăng theo event firmware.
21. Dừng periodic và cho command timeout trong trạng thái output an toàn.
22. Đọc `CAN Timeout Count`.
23. Kỳ vọng tăng ít nhất `1`.
24. Bấm `Reset All Counters` và confirm.
25. Đọc lại toàn bộ counters, kiểm tra giá trị reset hoặc chỉ phản ánh event sau reset.

### Direct mode real board

Dùng cùng flow real-board như Bridge mode chỉ sau khi:

- `ControlCAN.dll` load thành công.
- `VCI_OpenDevice` OK.
- `VCI_InitCAN` OK.
- `VCI_StartCAN` OK.

Nếu Direct mode lỗi bitness hoặc `VCI_OpenDevice` trả `0`, chuyển sang `USB-CAN-B Bridge`.

## Diễn giải counter

- `CAN Command RX Count` tăng khi firmware nhận command control hợp lệ ở `0x500 + NodeID`.
- `Diagnostic Request Count` tăng với diagnostic request hợp lệ.
- `Diagnostic Error Count` tăng khi request lỗi command/counter/group/DLC/magic.
- `CAN Timeout Count` tăng khi firmware phát hiện command timeout.
- `Failsafe Enter Count` tăng khi firmware vào fail-safe.

Không dùng giá trị counter như điều kiện safety duy nhất. Luôn đối chiếu status frame, fault mask và trạng thái phần cứng.
