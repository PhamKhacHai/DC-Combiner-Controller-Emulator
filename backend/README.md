# USB-CAN-B Backend

Backend này phục vụ mode `USB-CAN-B Bridge`.

## Mục đích

`USB-CAN-B Bridge` tách phần load `ControlCAN.dll` ra một backend process riêng. Cách này hữu ích khi UI Controller Emulator chạy bằng Python 64-bit nhưng vendor `ControlCAN.dll` trên máy test là 32-bit.

UI giao tiếp với backend bằng JSON lines qua stdin/stdout. Backend load DLL, mở USB-CAN-B device, gửi frame TX và trả frame RX về UI.

## Khi nào cần dùng backend

Dùng `USB-CAN-B Bridge` khi:

- Test board thật qua USB-CAN-B.
- `ControlCAN.dll` là 32-bit.
- Python đang chạy UI không cùng bitness với DLL.
- `USB-CAN-B Direct` không load được DLL hoặc không mở được device.

Không cần backend khi:

- Chạy `Mock` mode.
- Dùng `USB-CAN-B Direct` với Python và `ControlCAN.dll` cùng bitness.

## `ControlCAN.dll`

Default path thường gặp:

```text
C:\Program Files (x86)\USB_CAN TOOL\ControlCAN.dll
```

Đây chỉ là path phổ biến từ một số bộ driver/vendor tool. Không phải máy nào cũng giống, và không được coi đây là path bắt buộc.

Nếu DLL nằm ở chỗ khác, cấu hình biến môi trường:

```powershell
$env:USB_CAN_BACKEND_DLL="C:\path\to\ControlCAN.dll"
```

Set lâu dài trong Windows Environment Variables:

```text
Variable name:  USB_CAN_BACKEND_DLL
Variable value: C:\path\to\ControlCAN.dll
```

## Python 32-bit backend

Nếu `ControlCAN.dll` là 32-bit, Python 64-bit không load trực tiếp DLL 32-bit được. Khi đó nên dùng một Python 32-bit riêng cho backend.

Đường dẫn Python 32-bit trên mỗi máy khác nhau, vì vậy không hard-code đường dẫn máy phát triển. Cấu hình bằng biến môi trường:

```powershell
$env:USB_CAN_BACKEND_PYTHON32="C:\Path\To\Python32\python.exe"
```

Set lâu dài trong Windows Environment Variables:

```text
Variable name:  USB_CAN_BACKEND_PYTHON32
Variable value: C:\Path\To\Python32\python.exe
```

## Kiểm tra backend

Chạy từ repo Controller Emulator đã clone:

```powershell
cd "<thư mục repo Controller Emulator vừa clone>"
.venv\Scripts\activate
python scripts\check_backend_32bit.py
```

Nếu `USB_CAN_BACKEND_PYTHON32` chưa set, script sẽ báo rõ. Khi backend đã sẵn sàng, chọn `Driver mode = USB-CAN-B Bridge` trong UI để connect board thật.

## Giao tiếp backend

- UI gửi JSON lines vào stdin của backend.
- Backend trả JSON lines qua stdout.
- Log debug và traceback chỉ ghi ra stderr.
- Backend không gửi CAN frame nếu `open`, `init` và `start` chưa thành công.

## Lưu ý `.env.example`

`.env.example` trong repo chỉ là file mẫu tham khảo cho các biến môi trường. Nếu tool không tự đọc `.env`, hãy set biến môi trường bằng PowerShell hoặc Windows Environment Variables. Không commit file `.env` thật vì có thể chứa path cá nhân.
