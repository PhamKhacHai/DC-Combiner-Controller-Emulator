# Troubleshooting

Tài liệu này ghi các lỗi thường gặp khi dùng Controller Emulator trên máy khác hoặc khi test board thật qua USB-CAN-B.

## Không connect được USB-CAN-B

Nguyên nhân thường gặp:

- USB-CAN-B chưa cắm hoặc Windows chưa nhận.
- Driver Windows chưa cài hoặc chưa đúng.
- Vendor CAN tool đang giữ device.
- Chọn sai driver mode.
- Sai `ControlCAN.dll` path.
- Python/DLL bitness không khớp.
- Chưa set `USB_CAN_BACKEND_PYTHON32` khi dùng `USB-CAN-B Bridge` với DLL 32-bit.
- Sai device index hoặc channel.

Cách xử lý:

```text
Đóng vendor CAN tool.
Rút/cắm lại USB-CAN-B.
Kiểm tra Device Manager.
Kiểm tra driver mode.
Kiểm tra bitrate 500000.
Kiểm tra Node ID.
Cấu hình USB_CAN_BACKEND_DLL nếu DLL không nằm ở default path.
Cấu hình USB_CAN_BACKEND_PYTHON32 nếu cần Python 32-bit backend.
Thử device index/channel khác nếu phần cứng có nhiều channel.
```

Script hỗ trợ:

```powershell
cd "<thư mục repo Controller Emulator vừa clone>"
.venv\Scripts\activate
python scripts\check_driver_bitness.py
python scripts\check_backend_32bit.py
```

## `DLL load failed`

Nguyên nhân thường gặp:

- `ControlCAN.dll` không nằm ở path tool đang tìm.
- DLL bị thiếu dependency của vendor driver.
- Python hiện tại và DLL khác bitness.

Cách xử lý:

- Kiểm tra `ControlCAN.dll` từ driver/vendor package.
- Nếu DLL nằm ở chỗ khác, set `USB_CAN_BACKEND_DLL`.
- Nếu DLL là 32-bit, dùng `USB-CAN-B Bridge` và set `USB_CAN_BACKEND_PYTHON32`.
- Cài lại driver/vendor tool nếu DLL thiếu dependency.

## Bridge không chạy

Nguyên nhân thường gặp:

- `USB_CAN_BACKEND_PYTHON32` chưa set hoặc sai.
- Python 32-bit backend chưa cài dependencies cần thiết.
- Backend process crash.
- DLL path sai.
- USB-CAN-B không mở được.

Cách xử lý:

```powershell
cd "<thư mục repo Controller Emulator vừa clone>"
.venv\Scripts\activate
python scripts\check_backend_32bit.py
```

Nếu vẫn lỗi, kiểm tra stderr/log của backend và xác nhận `ControlCAN.dll` đúng bitness.

## Không thấy app status `0x510/0x520`

Nếu vừa update fail/abort/power loss:

- Có thể app invalid.
- Board có thể đang ở bootloader mode.
- Bấm `Refresh Bootloader Status`.
- Nếu `APP_VALID=0`, update lại từ đầu.

Nếu đang app mode mà vẫn không thấy status:

- Kiểm tra CAN_H/CAN_L/GND.
- Kiểm tra bitrate `500000`.
- Kiểm tra Node ID.
- Kiểm tra nguồn board.
- Kiểm tra termination.
- Kiểm tra app có đang chạy không.
- Kiểm tra bootloader có đang giữ board trong bootloader mode không.

Nếu board đang bootloader mode, dùng `Get Boot Info` để kiểm tra response `0x560 + NodeID`.

## Có TX nhưng không có RX

Nguyên nhân thường gặp:

- Bus lỗi.
- CAN_H/CAN_L đảo.
- Thiếu termination hoặc termination bật dư nhiều điểm.
- Sai bitrate.
- Sai Node ID.
- Board chưa cấp nguồn.
- Board đang bootloader mode trong khi bạn chờ status app.

Cách xử lý:

- Kiểm tra wiring CAN_H/CAN_L/GND.
- Kiểm tra termination 120 ohm phù hợp.
- Kiểm tra bitrate `500000`.
- Kiểm tra Node ID theo DIP switch/firmware.
- Thử `Get Boot Info` nếu nghi board đang bootloader mode.
- Dùng diagnostic hoặc boot info để phân biệt app mode và bootloader mode.

## `Refresh Bootloader Status` không có response

Nguyên nhân:

- Board đang app mode.
- Chưa bấm `Enter Bootloader`.
- Node ID sai.
- CAN wiring/bitrate sai.
- Bootloader không chạy hoặc bootloader hỏng.

Cách xử lý:

```text
Bấm Enter Bootloader trước.
Nếu vẫn không response, kiểm tra CAN wiring, bitrate, Node ID.
Nếu bootloader không còn chạy, dùng J-Link/ST-Link theo quy trình firmware.
```

## `CRC_MISMATCH`

Nguyên nhân:

- Đang tick `Force Bad CRC`.
- Chọn sai app `.bin`.
- Data ghi qua CAN không khớp file.
- Update bị lỗi giữa chừng.

Cách xử lý:

```text
Bỏ tick Force Bad CRC nếu đang update thật.
Chọn đúng application .bin.
Update lại từ đầu.
Không FINISH_UPDATE.
Không Reset To App.
```

Không chọn bootloader `.bin`, `.hex`, `.elf` hoặc `.map` để update qua CAN.

## `BAD_STATE`

Ý nghĩa:

- Gửi command sai state hiện tại.

Ví dụ:

- `ERASE_APP` trước `START_UPDATE`.
- `FINISH_UPDATE` trước `VERIFY_CRC OK`.
- `ABORT_UPDATE` khi update đã finish/idle.
- `RESET_TO_APP` khi app invalid.

Cách xử lý:

- Bấm `Refresh Bootloader Status`.
- Xem `Session State`, `Metadata State`, `App Valid`.
- Nếu app invalid, update lại từ đầu.

## `BAD_SEQUENCE`

Ý nghĩa:

- Chunk sequence sai khi gửi `WRITE_CHUNK`.

Cách xử lý:

```text
Dừng update.
Start Firmware Update lại từ đầu.
Không tiếp tục gửi chunk giữa chừng.
```

## Sau abort/power loss không Reset To App được

Đây là behavior đúng.

Kỳ vọng:

```text
META=INVALID hoặc META=IN_PROGRESS
APP_VALID=0
Reset To App disabled
```

Cách xử lý:

```text
Update lại từ đầu.
Chỉ Reset To App khi App Valid = Yes và CRC Match = Yes.
```

## Nút `Start Firmware Update` bị disabled hoặc bị chặn

Nguyên nhân:

- Chưa connect CAN.
- Chưa chọn file.
- File không phải app `.bin` hợp lệ.
- App `.bin` không relocated tại `0x08004000`.
- Bootloader chưa sẵn sàng.
- Tool đang có update session chạy.

Cách xử lý:

```text
Connect.
Enter Bootloader.
Get Boot Info.
Get Flash Layout.
Select đúng application .bin.
Kiểm tra Validation báo OK.
```

## `Clear Fault` không làm sạch fault

Nguyên nhân:

- Firmware chỉ clear fault khi điều kiện an toàn đạt.
- Feedback vẫn ON hoặc mismatch.
- Fail-safe/CAN timeout chưa được xử lý đúng.

Cách xử lý:

- Bấm `Off All`.
- Kiểm tra feedback về OFF.
- Gửi `Clear Fault`.
- Nếu output cần ON lại, dùng `Start Periodic` sau khi clear thành công.

## Output tự tắt sau `Send Once`

Đây là behavior bình thường nếu firmware có command timeout.

Cách xử lý:

```text
Dùng Start Periodic để giữ command hợp lệ.
Đặt Interval nhỏ hơn timeout firmware, ví dụ 100 ms hoặc 500 ms.
```

## Diagnostic đọc được nhưng output vẫn fail-safe

Diagnostic reads không refresh command timeout và không thoát fail-safe.

Cách xử lý:

- Dùng periodic command nếu cần giữ output ON.
- Dùng OFF all hoặc Clear Fault hợp lệ để xử lý fail-safe theo protocol.

## Board trắng hoặc bootloader hỏng

Controller Emulator không thể nạp bootloader qua CAN khi board trắng hoàn toàn hoặc bootloader hỏng.

Cách xử lý:

- Dùng J-Link/ST-Link theo quy trình firmware.
- Sau khi bootloader đã chạy, có thể dùng CAN update cho application `.bin`.

## Bootloader thay đổi

CAN update hiện tại chỉ update application region, không update bootloader region.

Cách xử lý:

- Nạp bootloader bằng J-Link/ST-Link theo quy trình firmware.
- Không chọn bootloader `.bin` trong Controller Emulator.
