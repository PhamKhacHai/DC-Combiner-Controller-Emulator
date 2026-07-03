# DC Combiner Controller Emulator

## Mục đích

`DC Combiner Controller Emulator` là PC tool dùng để test firmware `DC_Combiner_MCU_IO_FW` qua CAN. Repo này có thể clone ở bất kỳ thư mục nào trên máy người dùng; không cần đặt đúng theo đường dẫn máy phát triển.

Tool hỗ trợ:

- Gửi command điều khiển Group 1..6.
- Đọc status frame `0x510 + NodeID`.
- Đọc heartbeat frame `0x520 + NodeID`.
- Đọc diagnostic counters qua `0x530/0x540 + NodeID`.
- Vào bootloader qua CAN.
- Update application firmware qua CAN.
- Refresh bootloader/app/metadata status.
- Test lỗi update như abort, bad CRC và power loss mô phỏng.

## Chạy trên máy khác sau khi clone

### 1. Chạy `Mock` mode

`Mock` mode là cách nhanh nhất để kiểm tra UI, button, log và protocol giả lập.

`Mock` mode:

- Không cần board.
- Không cần USB-CAN-B.
- Không cần driver USB-CAN-B.
- Chỉ cần Python và dependencies của project.

Lệnh mẫu:

```powershell
git clone <repo-url>
cd "<thư mục repo Controller Emulator vừa clone>"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Sau khi mở UI:

```text
Driver mode: Mock
Connect
```

### 2. Test board thật qua USB-CAN-B

Muốn test board thật thì chỉ clone repo là chưa đủ. Máy đó còn cần driver, phần mềm và phần cứng bên ngoài repo:

- Board DC Combiner đã được cấp nguồn.
- Firmware/bootloader đã được nạp đúng.
- USB-CAN-B hardware.
- Driver USB-CAN-B đã được cài trên Windows.
- Vendor tool hoặc driver package đi kèm USB-CAN-B.
- `ControlCAN.dll` từ driver/vendor package.
- Python environment để chạy Controller Emulator.
- Nếu dùng `USB-CAN-B Bridge` và DLL là 32-bit thì cần Python 32-bit backend.
- CAN_H/CAN_L/GND đấu đúng.
- Bitrate `500000`.
- Node ID đúng với DIP switch/firmware.
- Không mở vendor CAN tool đồng thời với Controller Emulator vì có thể chiếm USB-CAN-B device.

Flow ngắn:

1. Clone repo Controller Emulator.
2. Tạo `.venv` và cài `requirements.txt`.
3. Cài driver USB-CAN-B trên Windows.
4. Kiểm tra `ControlCAN.dll`.
5. Cấu hình `USB_CAN_BACKEND_DLL` nếu DLL không nằm ở default path.
6. Cấu hình `USB_CAN_BACKEND_PYTHON32` nếu dùng `USB-CAN-B Bridge` với DLL 32-bit.
7. Đấu CAN_H/CAN_L/GND đúng.
8. Chạy `python main.py`.
9. Chọn `Driver mode: USB-CAN-B Bridge`.
10. Chọn bitrate `500000`.
11. Chọn đúng Node ID.
12. Bấm `Connect`.
13. Kiểm tra có RX status `0x510 + NodeID` và heartbeat `0x520 + NodeID`.

Chi tiết setup driver xem [docs/usb_can_b_setup.md](docs/usb_can_b_setup.md).

## Cách chạy tool

Nếu đã có `.venv`:

```powershell
cd "<thư mục repo Controller Emulator vừa clone>"
.venv\Scripts\activate
python main.py
```

Nếu chưa có `.venv`:

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

## Cấu hình CAN

```text
Bitrate: 500000
Node ID: 0..7
CAN ID: Standard 11-bit
Frame: Data frame, không dùng RTR
```

Lưu ý phần cứng:

- USB-CAN-B nối vào CAN_H/CAN_L của bus.
- Không nối CAN_H/CAN_L trực tiếp vào PA11/PA12 của MCU.
- PA11/PA12 là CAN_RX/CAN_TX giữa MCU và CAN transceiver.
- Bus CAN cần wiring CAN_H, CAN_L, GND và termination phù hợp.

## Các chế độ driver

### `Mock`

- Không cần phần cứng.
- Không cần USB-CAN-B.
- Không cần driver USB-CAN-B.
- Dùng để test UI, command mask, status decode, heartbeat, diagnostic và bootloader update giả lập.
- Nên dùng trước khi chuyển sang board thật.

### `USB-CAN-B Direct`

- Python process của UI load `ControlCAN.dll` trực tiếp.
- Python và DLL phải cùng bitness.
- Chỉ dùng khi Python hiện tại và `ControlCAN.dll` cùng 32-bit hoặc cùng 64-bit.

### `USB-CAN-B Bridge`

- Đây là mode khuyến nghị khi test board thật, đặc biệt khi vendor DLL là 32-bit.
- UI có thể chạy bằng Python thường của người dùng.
- Backend process có thể dùng Python 32-bit riêng để load 32-bit `ControlCAN.dll`.
- Cần cấu hình `USB_CAN_BACKEND_PYTHON32` nếu máy không tự tìm được Python 32-bit backend.

`ControlCAN.dll` thường gặp ở:

```text
C:\Program Files (x86)\USB_CAN TOOL\ControlCAN.dll
```

Đây chỉ là path phổ biến, không phải path bắt buộc. Nếu DLL nằm ở chỗ khác, cấu hình `USB_CAN_BACKEND_DLL`.

Ví dụ PowerShell:

```powershell
$env:USB_CAN_BACKEND_DLL="C:\path\to\ControlCAN.dll"
$env:USB_CAN_BACKEND_PYTHON32="C:\Path\To\Python32\python.exe"
```

`.env.example` chỉ là file mẫu tham khảo. Nếu tool không tự đọc `.env`, hãy set biến môi trường bằng PowerShell hoặc Windows Environment Variables.

## Điều khiển group/output

Checkbox Group 1..6 là request từ user. `Command Mask` là bit mask tool gửi xuống firmware.

Bit mapping:

| Bit | Group |
| ---: | --- |
| bit0 | Group 1 |
| bit1 | Group 2 |
| bit2 | Group 3 |
| bit3 | Group 4 |
| bit4 | Group 5 |
| bit5 | Group 6 |

Ví dụ:

```text
0x38 = Group 4 + Group 5 + Group 6
```

Các nút chính:

- `Send Once`: gửi một frame command, không giữ output ON lâu.
- `Start Periodic`: gửi command lặp lại, dùng khi muốn output duy trì ON.
- `Stop Periodic`: dừng gửi periodic.
- `Off All`: yêu cầu tắt toàn bộ group.
- `Clear Fault`: gửi Clear Fault theo protocol hiện tại.

Cảnh báo:

```text
Send Once không giữ output ON.
Nếu firmware có command timeout, output có thể tắt lại.
Muốn giữ output ON thì dùng Start Periodic.
```

## Requested vs Actual Status

UI phân biệt rõ request của user và trạng thái board báo về:

- `Requested`: trạng thái user đang request trên UI.
- `DO`: output thực tế board báo về qua `DO Mask`.
- `Feedback P/N`: feedback thực tế từ board.
- `Fault`: fault bit từ firmware.

Behavior hiện tại:

- Nếu firmware báo fault ở group đang request, UI tự bỏ tick group đó và cập nhật `Command Mask`.
- Nếu fail-safe/CAN timeout active, UI bỏ tick toàn bộ group, đưa command mask về `0x00` và dừng periodic.
- Fail-safe không tự làm `Fault = Yes`; cột `Fault` chỉ theo `Fault Mask`.
- UI không tự clear fault; `Clear Fault` vẫn là command riêng.
- Checkbox không phải bằng chứng output đã ON; phải nhìn status/DO/feedback.

## Diagnostics

Diagnostics tab dùng để đọc runtime counters trong firmware.

```text
Request ID:  0x530 + NodeID
Response ID: 0x540 + NodeID
```

Ghi chú:

- Counters nằm trong RAM.
- Counters reset khi MCU reset hoặc mất nguồn.
- Diagnostic reads không refresh command timeout.
- Nếu output cần giữ ON khi đọc diagnostics, dùng periodic command.

Chi tiết xem [docs/diagnostic_user_guide.md](docs/diagnostic_user_guide.md).

## Bootloader và cập nhật firmware qua CAN

Controller Emulator chỉ update application firmware qua CAN.

File đúng để update là application `.bin` tương ứng trên máy của bạn. Ví dụ sau khi build firmware có thể là:

```text
build\Debug\DC_Combiner_MCU_IO_FW.bin
```

Không chọn:

- Bootloader `.bin`.
- `.hex`.
- `.elf`.
- `.map`.

CAN update hiện tại chỉ update application region, không update bootloader. Nếu bootloader thay đổi hoặc board trắng hoàn toàn thì vẫn cần nạp bằng J-Link/ST-Link theo quy trình firmware.

Flow chuẩn:

```text
Connect USB-CAN-B Bridge
-> Enter Bootloader
-> Get Boot Info
-> Get Flash Layout
-> Select App .bin
-> Start Firmware Update
-> VERIFY_CRC OK
-> FINISH_UPDATE OK
-> Refresh Bootloader Status
-> Reset To App
```

Sau lỗi update:

- `ABORT_UPDATE`: app invalid, update lại từ đầu.
- `CRC_MISMATCH`: không finish, update lại từ đầu.
- `Stop After N Chunks` + reset/power cycle: metadata `IN_PROGRESS`, bootloader không jump app, update lại từ đầu.
- Không bấm `Reset To App` sau update fail/abort.

Chi tiết xem [docs/firmware_update_user_guide.md](docs/firmware_update_user_guide.md) và [docs/bootloader_update_test_plan.md](docs/bootloader_update_test_plan.md).

## Refresh Bootloader Status

Nút `Refresh Bootloader Status` đọc:

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

Ý nghĩa metadata state:

| State | Ý nghĩa |
| --- | --- |
| `VALID` | App hợp lệ, có thể `Reset To App` |
| `IN_PROGRESS` | Update bị gián đoạn hoặc chưa finish, cần update lại |
| `INVALID` | App invalid do abort/fail, cần update lại |
| `BLANK` | Metadata chưa có, thường do nạp bằng J-Link |
| `CORRUPT` | Metadata hỏng |

## Advanced/Test options

- `Stop After N Chunks`: dừng gửi chunk sau N chunks, không gửi abort; dùng để test power loss/reset.
- `Force Bad CRC`: cố tình gửi CRC sai để test `CRC_MISMATCH`.
- `Abort Update`: gửi abort khi update đang chạy.
- `Run Flash Self-Test`: đang disabled vì metadata page `0x0800FC00` đã dùng thật sau Milestone 5.

## Các lỗi thường gặp

Các lỗi thường gặp và cách xử lý nằm trong [docs/troubleshooting.md](docs/troubleshooting.md), gồm:

- Không connect được USB-CAN-B.
- Không thấy app status `0x510/0x520`.
- `Refresh Bootloader Status` không có response.
- `CRC_MISMATCH`.
- `BAD_STATE`.
- `BAD_SEQUENCE`.
- Không reset app được sau abort/power loss.
- `Start Firmware Update` bị disabled.

## Tài liệu liên quan

- [docs/controller_user_guide.md](docs/controller_user_guide.md)
- [docs/firmware_update_user_guide.md](docs/firmware_update_user_guide.md)
- [docs/bootloader_update_test_plan.md](docs/bootloader_update_test_plan.md)
- [docs/diagnostic_user_guide.md](docs/diagnostic_user_guide.md)
- [docs/usb_can_b_setup.md](docs/usb_can_b_setup.md)
- [docs/troubleshooting.md](docs/troubleshooting.md)
