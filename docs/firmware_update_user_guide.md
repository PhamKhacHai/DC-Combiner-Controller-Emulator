# Firmware Update User Guide

Tài liệu này hướng dẫn update application firmware qua CAN bằng Controller Emulator.

## Điều kiện trước khi update

Cần có:

- Board đã có bootloader.
- USB-CAN-B hoạt động.
- Driver USB-CAN-B đã cài trên Windows.
- `ControlCAN.dll` được tool tìm thấy hoặc đã cấu hình bằng `USB_CAN_BACKEND_DLL`.
- Nếu dùng `USB-CAN-B Bridge` với DLL 32-bit: `USB_CAN_BACKEND_PYTHON32` trỏ tới Python 32-bit backend.
- CAN bitrate `500000`.
- Node ID đúng theo DIP switch/firmware.
- App `.bin` đúng, là relocated application tại `0x08004000`.
- Output/load ở trạng thái an toàn.

Controller Emulator chỉ update application firmware qua CAN. Tool không update bootloader qua CAN.

## Khi nào dùng J-Link/ST-Link, khi nào dùng CAN

```text
Bootloader thay đổi -> dùng J-Link/ST-Link theo quy trình firmware.
Board trắng hoàn toàn -> dùng J-Link/ST-Link theo quy trình firmware.
Bootloader hỏng hoặc không vào được CAN bootloader -> dùng J-Link/ST-Link.
Chỉ application thay đổi -> dùng CAN update.
```

Nếu bootloader vẫn nhận CAN và app invalid sau update fail, ưu tiên update lại qua CAN thay vì full erase bằng J-Link/ST-Link.

## Quy trình update chuẩn

1. Connect bằng `USB-CAN-B Bridge`.
2. Nếu app đang chạy, bấm `Enter Bootloader`.
3. Bấm `Get Boot Info`.
4. Bấm `Get Flash Layout`.
5. Bấm `Select App .bin`.
6. Chọn file application `.bin` tương ứng trên máy của bạn.
7. Bấm `Start Firmware Update`.
8. Chờ `WRITE` progress 100%.
9. Chờ `VERIFY_CRC OK`.
10. Chờ `FINISH_UPDATE OK`.
11. Bấm `Refresh Bootloader Status`.
12. Nếu `App Valid = Yes` và `CRC Match = Yes`, bấm `Reset To App`.
13. Kiểm tra app chạy lại bằng status `0x510` và heartbeat `0x520`.

Ví dụ file app `.bin` sau khi build firmware có thể là:

```text
build\Debug\DC_Combiner_MCU_IO_FW.bin
```

Đây là đường dẫn tương đối trong firmware repo của người dùng, không phải path cố định trên máy phát triển.

Kết quả mong đợi:

```text
START_UPDATE OK
ERASE_APP OK
WRITE progress=100%
VERIFY_CRC OK
FINISH_UPDATE OK
META=VALID
APP_VALID=1
CRC_MATCH=1
RESET_TO_APP OK
```

## File nào được chọn

Đúng:

```text
Application .bin
Ví dụ: DC_Combiner_MCU_IO_FW.bin
```

Sai:

```text
Bootloader .bin
*.hex
*.elf
*.map
```

Không chọn `DC_Combiner_MCU_IO_FW_Bootloader.bin` trong Controller Emulator. CAN update hiện tại chỉ ghi application region, không ghi bootloader region.

Tool validate app `.bin` trước khi gửi `START_UPDATE`:

- File size phải lớn hơn 8 byte.
- File size không vượt application region 47 KB.
- Initial SP phải nằm trong SRAM.
- Reset handler phải có Thumb bit.
- Reset handler phải nằm trong vùng app Flash `0x08004000..0x0800FBFF`.

Nếu file invalid, tool log lỗi và không gửi `START_UPDATE`.

## Refresh Bootloader Status

Sau update hoặc sau lỗi, bấm `Refresh Bootloader Status` để đọc:

- Bootloader Version.
- Mode.
- App Valid.
- Vector Valid.
- Metadata State.
- Metadata Version.
- App Size.
- Max App Size.
- Stored CRC32.
- Computed CRC32.
- CRC Match.
- Info Source.
- Session State.
- Recovery Hint.

Ý nghĩa recovery:

| Trạng thái | Ý nghĩa | Hành động |
| --- | --- | --- |
| `META=VALID`, `APP_VALID=1`, `CRC_MATCH=1` | App hợp lệ | Có thể `Reset To App` |
| `META=IN_PROGRESS` | Update bị gián đoạn | Update lại từ đầu |
| `META=INVALID` | Abort/fail làm app invalid | Update lại từ đầu |
| `CRC_MATCH=0` | Stored CRC khác Flash CRC | Không reset app, update lại |
| `APP_VALID=0` | App không hợp lệ | Không reset app |

## Sau update lỗi làm gì

### `CRC_MISMATCH`

- Kiểm tra có tick `Force Bad CRC` không.
- Nếu đang test bad CRC thì đây là kết quả đúng.
- Bỏ tick `Force Bad CRC` khi muốn update thật.
- Update lại từ đầu.
- Không bấm `Reset To App`.

### `ABORT_UPDATE`

- Abort giữa update làm metadata thành `INVALID`.
- `APP_VALID=0`.
- Update lại từ đầu.
- Không bấm `Reset To App`.

### `IN_PROGRESS`

- Thường do `Stop After N Chunks`, reset hoặc power cycle giữa update.
- Bootloader không jump app.
- Update lại từ đầu.

### `APP_VALID=0`

- Tool sẽ block `Reset To App`.
- Đây là behavior đúng.
- Cần update lại hoặc nạp bằng J-Link/ST-Link nếu bootloader không còn nhận CAN.

## Advanced/Test options

### `Stop After N Chunks`

Dùng để mô phỏng power loss/reset giữa update. Tool dừng gửi chunk sau N chunks và không gửi `ABORT_UPDATE`.

Flow test:

```text
Set Stop After N Chunks
Start Firmware Update
Tool dừng sau N chunks
Reset/power-cycle board
Refresh Bootloader Status
```

Kỳ vọng:

```text
META=IN_PROGRESS
APP_VALID=0
MODE=BOOTLOADER
```

### `Force Bad CRC`

Dùng để test CRC mismatch.

Kỳ vọng:

```text
CRC_MISMATCH
Không FINISH_UPDATE
APP_VALID=0
```

### `Abort Update`

Dùng để hủy update đang chạy.

Kỳ vọng:

```text
ABORT_UPDATE OK
META=INVALID
APP_VALID=0
```

### `Refresh Bootloader Status`

Dùng để đọc metadata/app status sau update OK, abort, power loss hoặc CRC mismatch.

Ví dụ recovery:

```text
META=VALID APP_VALID=1 CRC_MATCH=1 -> có thể Reset To App
META=IN_PROGRESS APP_VALID=0 -> update lại từ đầu
META=INVALID APP_VALID=0 -> update lại từ đầu
```

## Không nên làm

- Không chọn bootloader `.bin`.
- Không chọn `.hex`.
- Không chọn `.elf`.
- Không chọn `.map`.
- Không bấm `Reset To App` khi `APP_VALID=0`.
- Không rút nguồn trong lúc bootloader đang ghi metadata nếu không phải test.
- Không chạy periodic output command trong lúc update firmware.
- Không dùng CAN update cho board trắng hoặc bootloader hỏng.
