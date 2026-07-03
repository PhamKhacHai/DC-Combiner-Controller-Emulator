# Bootloader Update Test Plan

Tài liệu này mô tả các test liên quan bootloader và update firmware qua CAN.

## Chuẩn bị chung

- Dùng `USB-CAN-B Bridge` cho board thật.
- Máy test đã cài driver USB-CAN-B và cấu hình `ControlCAN.dll`.
- Bitrate `500000`.
- Node ID đúng theo DIP.
- Board đã có bootloader.
- Chọn đúng application `.bin`.
- Không chọn bootloader `.bin`, `.hex`, `.elf` hoặc `.map`.
- Đưa output/load về trạng thái an toàn trước khi test.

Ví dụ file application `.bin` sau khi build firmware có thể là:

```text
build\Debug\DC_Combiner_MCU_IO_FW.bin
```

Đây là đường dẫn tương đối trong firmware repo của người dùng, không phải path cố định trên máy phát triển.

## Normal update

Cách test:

```text
Connect
Enter Bootloader
Get Boot Info
Get Flash Layout
Select App .bin
Start Firmware Update
Refresh Bootloader Status
Reset To App
```

Kỳ vọng:

```text
VERIFY_CRC OK
FINISH_UPDATE OK
META=VALID
APP_VALID=1
CRC_MATCH=1
Reset To App OK
App chạy lại 0x510/0x520
```

## Abort giữa update

Cách test:

```text
Start Firmware Update
-> Abort ở khoảng 20-30%
-> Refresh Bootloader Status
```

Kỳ vọng:

```text
ABORT_UPDATE OK
META=INVALID
APP_VALID=0
Reset To App disabled
Update lại từ đầu OK
```

Ghi chú:

- Abort chỉ hợp lệ khi update session đang active.
- Abort sau idle/finish có thể trả `BAD_STATE`, đây là behavior đúng.

## Stop After N Chunks / Power loss

Cách test:

```text
Stop After N Chunks = 500
Start Firmware Update
Tool dừng
Reset/power-cycle board
Refresh Bootloader Status
```

Kỳ vọng:

```text
META=IN_PROGRESS
APP_VALID=0
MODE=BOOTLOADER
Update lại từ đầu OK
```

Ghi chú:

- Tool không gửi `ABORT_UPDATE` trong test này.
- Đây là mô phỏng update bị gián đoạn.
- Session state trong RAM có thể về `IDLE` sau reset; metadata `IN_PROGRESS` mới là dấu hiệu quan trọng.

## Force Bad CRC

Cách test:

```text
Tick Force Bad CRC
Start Firmware Update
```

Kỳ vọng:

```text
CRC_MISMATCH
Không FINISH_UPDATE
APP_VALID=0
Update lại từ đầu OK
```

Ghi chú:

- Tool log CRC thật và CRC đã gửi.
- Khi bỏ tick `Force Bad CRC`, normal update phải pass lại.

## Invalid file

Cách test:

- Chọn file không phải application `.bin`.
- Chọn bootloader `.bin`, `.hex`, `.elf`, `.map` hoặc file `.bin` không có vector hợp lệ.

Kỳ vọng:

```text
Validation báo INVALID
Start Firmware Update không gửi START_UPDATE
Không erase app
```

## App mode no response

Cách test:

```text
Khi app đang chạy
Bấm Refresh Bootloader Status
```

Kỳ vọng:

```text
Log: No bootloader response. Enter bootloader first.
UI không crash.
Không thay đổi command/output.
```

## Reset To App sau fail

Cách test:

```text
Tạo META=IN_PROGRESS hoặc META=INVALID
Bấm Refresh Bootloader Status
Bấm Reset To App
```

Kỳ vọng:

```text
Reset To App bị block
Log: RESET_TO_APP blocked: app is not known valid.
```

## Mock mode coverage

Mock mode có thể dùng để smoke test UI:

- Normal update giả lập.
- `Force Bad CRC`.
- `Abort Update`.
- `Refresh Bootloader Status`.
- App `.bin` validation.

Mock mode không xác nhận wiring, USB-CAN-B driver hoặc Flash thật trên MCU.
