# Controller User Guide

Tài liệu này hướng dẫn dùng UI hằng ngày của `DC Combiner Controller Emulator`.

## Mở tool

Repo có thể nằm ở bất kỳ thư mục nào trên máy người dùng.

Nếu đã có môi trường ảo:

```powershell
cd "<thư mục repo Controller Emulator vừa clone>"
.venv\Scripts\activate
python main.py
```

Nếu chưa có môi trường ảo:

```powershell
cd "<thư mục repo Controller Emulator vừa clone>"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Chạy test khi cần:

```powershell
cd "<thư mục repo Controller Emulator vừa clone>"
.venv\Scripts\activate
pytest
```

## Chọn mode

| Mode | Khi dùng |
| --- | --- |
| `Mock` | Test UI không cần board, không cần USB-CAN-B, không cần driver |
| `USB-CAN-B Bridge` | Khuyến nghị khi test board thật qua USB-CAN-B |
| `USB-CAN-B Direct` | Chỉ dùng khi Python hiện tại và `ControlCAN.dll` cùng bitness |

## Kết nối CAN

Trong khung `CAN`:

1. Chọn `Driver mode`.
2. Chọn `Device`.
3. Chọn `Channel`, mặc định thường là `0`.
4. Chọn `Bitrate`, dùng `500000`.
5. Chọn `Node ID`, đúng với DIP switch/firmware.
6. Bấm `Connect`.
7. Kiểm tra log TX/RX và status.

Kỳ vọng sau khi connect board thật:

- Nếu app đang chạy: thấy status `0x510 + NodeID` và heartbeat `0x520 + NodeID`.
- Nếu board đang ở bootloader mode: không thấy `0x510/0x520`, nhưng có thể dùng `Get Boot Info` và nhận response `0x560 + NodeID`.

Không mở vendor CAN tool cùng lúc với Controller Emulator vì có thể chiếm USB-CAN-B device.

## Control tab

### Group checkboxes

Checkbox `Group 1..6` là request từ user. Checkbox không chứng minh output vật lý đã ON.

Bit mapping:

| Group | Bit | Mask |
| --- | ---: | ---: |
| Group 1 | bit0 | `0x01` |
| Group 2 | bit1 | `0x02` |
| Group 3 | bit2 | `0x04` |
| Group 4 | bit3 | `0x08` |
| Group 5 | bit4 | `0x10` |
| Group 6 | bit5 | `0x20` |

Ví dụ:

```text
0x38 = Group 4 + Group 5 + Group 6
```

### Command controls

| Control | Ý nghĩa |
| --- | --- |
| `Command Mask` | Mask hiện tại tool sẽ gửi xuống firmware |
| `Interval` | Chu kỳ gửi periodic command |
| `Send Once` | Gửi một command frame |
| `Start Periodic` | Gửi command lặp lại |
| `Stop Periodic` | Dừng periodic command |
| `Off All` | Gửi mask `0x00`, flags `0x00` |
| `Clear Fault` | Gửi mask `0x00`, flags `0x01` |

Cảnh báo:

```text
Send Once không giữ output ON.
Nếu firmware có command timeout, output có thể tự tắt.
Muốn giữ output ON thì dùng Start Periodic.
```

## Requested vs DO vs Feedback vs Fault

Trong khung `Status`:

| Field | Ý nghĩa |
| --- | --- |
| `Requested` | Request từ checkbox UI |
| `DO` | Output thực tế board báo qua `DO Mask` |
| `Feedback P/N` | Feedback P và N thực tế |
| `Fault` | Fault bit từ firmware |

Behavior UI:

- Nếu status frame báo fault ở group đang request, UI tự bỏ tick group đó.
- Nếu fail-safe/CAN timeout active, UI bỏ tick toàn bộ group, command mask về `0x00` và dừng periodic.
- UI không xem fail-safe là group fault nếu `Fault Mask` không có bit tương ứng.
- UI không tự clear fault; phải bấm `Clear Fault`.
- UI chỉ auto-uncheck stale DO OFF sau khi đã từng thấy DO ON từ lúc user request.

## Logging

`Clear Log` chỉ xóa log hiển thị.

Nút này không:

- Disconnect CAN.
- Stop periodic TX.
- Reset status.
- Đổi checkbox.
- Gửi bất kỳ CAN frame nào.

Sau khi clear log, các frame TX/RX mới sẽ tiếp tục xuất hiện.

## Mock mode

Dùng `Mock` khi:

- Muốn test UI không cần USB-CAN-B.
- Muốn kiểm tra command mask.
- Muốn xem status/heartbeat decode.
- Muốn test diagnostics giả lập.
- Muốn test bootloader update flow giả lập.

Mock mode sinh status frame, heartbeat frame, diagnostic response và bootloader response trong RAM của tool. Mock mode không xác nhận wiring, USB-CAN-B driver hoặc Flash thật trên MCU.

## Quy trình điều khiển output an toàn

1. Connect.
2. Bấm `Off All`.
3. Tick group cần test.
4. Nếu chỉ test một frame, bấm `Send Once`.
5. Nếu cần giữ output ON, bấm `Start Periodic`.
6. Quan sát `DO`, `Feedback P/N`, `Fault`, `Global Status`.
7. Khi xong, bấm `Stop Periodic` rồi `Off All`.

Nếu có fault hoặc fail-safe, không cố bật lại group ngay. Kiểm tra status, feedback và dùng `Clear Fault` đúng rule khi hệ thống đã an toàn.

## Tài liệu liên quan

- [USB-CAN-B setup](usb_can_b_setup.md)
- [Diagnostic user guide](diagnostic_user_guide.md)
- [Firmware update user guide](firmware_update_user_guide.md)
- [Troubleshooting](troubleshooting.md)
