# USB-CAN-B Setup

## Mục đích

Tài liệu này hướng dẫn cài đặt USB-CAN-B và các thành phần liên quan để Controller Emulator giao tiếp với board thật qua CAN. Repo Controller Emulator có thể clone ở bất kỳ thư mục nào; các đường dẫn trong tài liệu chỉ là placeholder hoặc ví dụ cấu hình.

## Những thứ cần chuẩn bị

- Máy Windows.
- Python để chạy Controller Emulator.
- USB-CAN-B hardware.
- Driver/vendor tool của USB-CAN-B.
- `ControlCAN.dll`.
- Board DC Combiner đã có firmware/bootloader.
- Dây CAN_H, CAN_L, GND.
- Nguồn cấp board.
- Nếu dùng `USB-CAN-B Bridge` với DLL 32-bit: Python 32-bit backend.

## Cài driver USB-CAN-B

1. Tải driver/vendor tool đúng với USB-CAN-B từ package công ty cung cấp hoặc trang vendor.
2. Cài driver trên Windows.
3. Cắm USB-CAN-B vào máy.
4. Mở Device Manager để kiểm tra thiết bị đã nhận.
5. Nếu vendor có tool test CAN, có thể mở thử để kiểm tra device.
6. Sau khi test bằng vendor tool xong, đóng vendor tool trước khi mở Controller Emulator.

Không mở vendor tool và Controller Emulator cùng lúc vì một tool có thể giữ device làm tool còn lại không connect được.

## `ControlCAN.dll`

Default path thường gặp:

```text
C:\Program Files (x86)\USB_CAN TOOL\ControlCAN.dll
```

Lưu ý quan trọng:

- Đây chỉ là path phổ biến.
- Không phải máy nào cũng giống.
- Không được coi đây là path bắt buộc.
- Nếu DLL nằm ở chỗ khác, người dùng cần cấu hình biến môi trường `USB_CAN_BACKEND_DLL`.

Ví dụ PowerShell cho phiên terminal hiện tại:

```powershell
$env:USB_CAN_BACKEND_DLL="C:\path\to\ControlCAN.dll"
```

Set lâu dài trong Windows:

```text
System Properties
-> Environment Variables
-> New...

Variable name:
USB_CAN_BACKEND_DLL

Variable value:
C:\path\to\ControlCAN.dll
```

## Python 32-bit backend cho `USB-CAN-B Bridge`

UI Controller Emulator có thể chạy bằng Python thường của user. Nhưng nếu `ControlCAN.dll` là 32-bit, Python 64-bit không load trực tiếp DLL 32-bit được.

Khi đó nên dùng `USB-CAN-B Bridge`. Bridge mode có thể cần một Python 32-bit riêng để load DLL 32-bit.

Đường dẫn Python 32-bit trên mỗi máy khác nhau, không được hard-code theo máy phát triển. Người dùng cấu hình bằng biến môi trường `USB_CAN_BACKEND_PYTHON32`.

Ví dụ PowerShell:

```powershell
$env:USB_CAN_BACKEND_PYTHON32="C:\Path\To\Python32\python.exe"
```

Set lâu dài trong Windows Environment Variables:

```text
Variable name:
USB_CAN_BACKEND_PYTHON32

Variable value:
C:\Path\To\Python32\python.exe
```

Kiểm tra backend:

```powershell
cd "<thư mục repo Controller Emulator vừa clone>"
.venv\Scripts\activate
python scripts\check_backend_32bit.py
```

## Giải thích các driver mode

| Mode | Ý nghĩa | Khi dùng |
| --- | --- | --- |
| `Mock` | Không cần phần cứng, không cần USB-CAN-B, không cần driver | Test UI/protocol giả lập |
| `USB-CAN-B Bridge` | UI nói chuyện với backend riêng để load `ControlCAN.dll` | Khuyến nghị khi test board thật, đặc biệt khi cần Python 32-bit backend |
| `USB-CAN-B Direct` | UI load `ControlCAN.dll` trực tiếp | Chỉ dùng khi Python hiện tại và DLL cùng bitness |

## Đấu dây CAN

- USB-CAN-B CAN_H nối vào CAN_H của bus.
- USB-CAN-B CAN_L nối vào CAN_L của bus.
- GND nên nối chung nếu hệ thống yêu cầu hoặc nếu bus không có ground reference ổn định.
- Không nối CAN_H/CAN_L trực tiếp vào PA11/PA12 của STM32.
- PA11 là CAN_RX và PA12 là CAN_TX giữa MCU và CAN transceiver, không phải chân CAN_H/CAN_L.
- Cần có CAN transceiver giữa MCU và bus CAN.
- Kiểm tra termination 120 ohm ở hai đầu bus nếu cần.
- Nếu USB-CAN-B có switch termination R1/R2 thì chỉ bật termination khi thiết bị nằm ở đầu bus, không bật dư nhiều điểm trên cùng bus.

## Cấu hình trong UI khi test board thật

Giá trị thường dùng:

```text
Driver mode: USB-CAN-B Bridge
Bitrate: 500000
Device index: thường là 0
Channel: dùng channel đang đấu dây
Node ID: đúng với DIP switch/firmware
```

Sau khi `Connect`, kỳ vọng:

- Nếu app đang chạy: thấy `0x510 + NodeID` status và `0x520 + NodeID` heartbeat.
- Nếu board đang ở bootloader mode: không thấy `0x510/0x520`, nhưng có thể dùng `Get Boot Info` để nhận response `0x560 + NodeID`.
- Nếu không có frame nào: kiểm tra driver, DLL, wiring, bitrate, Node ID, nguồn board và termination.

## Kiểm tra bitness

Quy tắc:

```text
Python 64-bit chỉ load được DLL 64-bit.
Python 32-bit chỉ load được DLL 32-bit.
```

Kiểm tra Python hiện tại:

```powershell
python -c "import struct, sys; print(sys.executable); print(struct.calcsize('P') * 8)"
```

Kiểm tra driver/DLL từ repo Controller Emulator đã clone:

```powershell
cd "<thư mục repo Controller Emulator vừa clone>"
.venv\Scripts\activate
python scripts\check_driver_bitness.py
```

Kiểm tra DLL cụ thể:

```powershell
python scripts\check_driver_bitness.py --dll "C:\path\to\ControlCAN.dll"
```

## Manual bridge smoke test

Chỉ chạy khi wiring và tải đã an toàn.

```powershell
python scripts\test_bridge_driver.py --python32 "C:\Path\To\Python32\python.exe" --node-id 0 --channel 0 --bitrate 500000
```

Gửi Group 1 sau OFF ALL:

```powershell
python scripts\test_bridge_driver.py --python32 "C:\Path\To\Python32\python.exe" --node-id 0 --send-group1
```

## Bảng lỗi thường gặp

| Hiện tượng | Nguyên nhân có thể | Cách xử lý |
| --- | --- | --- |
| Không connect được USB-CAN-B | Driver chưa cài, DLL sai path, device bị vendor tool giữ, sai device index/channel | Cài driver, kiểm tra Device Manager, đóng vendor tool, cấu hình `USB_CAN_BACKEND_DLL`, thử device/channel khác |
| `DLL load failed` | Sai path DLL hoặc sai bitness | Kiểm tra `ControlCAN.dll`, dùng `USB-CAN-B Bridge`, cấu hình `USB_CAN_BACKEND_DLL` |
| Bridge không chạy | Chưa cấu hình Python 32-bit backend hoặc path sai | Cài Python 32-bit nếu cần, set `USB_CAN_BACKEND_PYTHON32`, chạy `scripts\check_backend_32bit.py` |
| Không thấy `0x510/0x520` | Sai bitrate, sai Node ID, board đang bootloader mode, dây CAN sai, board chưa cấp nguồn | Kiểm tra bitrate `500000`, Node ID, CAN_H/CAN_L/GND, nguồn board, thử `Get Boot Info` |
| Có TX nhưng không có RX | Bus lỗi, CAN_H/CAN_L đảo, thiếu termination, sai Node ID, board chưa chạy app | Kiểm tra wiring, termination, mode bootloader/app, dùng diagnostic hoặc boot info |

## Cảnh báo DLL

- Third-party DLL cần được kiểm tra/scan trước khi dùng.
- Không khuyến nghị dùng binary không rõ nguồn trong môi trường production hoặc safety-critical.
- Nếu có thể, ưu tiên DLL chính thức từ vendor đúng bitness.
