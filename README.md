# DC Combiner Controller Emulator

Project path:

```powershell
F:\Work\Project\Controller Emulator
```

## Run

```powershell
cd "F:\Work\Project\Controller Emulator"
.venv\Scripts\activate
python main.py
```

If the virtual environment does not exist yet:

```powershell
cd "F:\Work\Project\Controller Emulator"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Test

```powershell
cd "F:\Work\Project\Controller Emulator"
.venv\Scripts\activate
pytest
```

## Mock Mode

- Select Driver mode = Mock.
- Press Connect.
- Tick one or more groups.
- Press Send Once.
- Check the TX/RX log and decoded status.
- Press Start Periodic to repeat the current command mask.

Mock mode does not need USB-CAN-B hardware. It generates status and heartbeat frames so the UI can be tested immediately.

## Driver Modes

The UI has three driver modes:

1. `Mock`
   - No hardware required.
   - Used to test UI, command masks, status decode, heartbeat decode, and logs.

2. `USB-CAN-B Direct`
   - The UI Python process loads `ControlCAN.dll` directly.
   - Python and DLL bitness must match.
   - On this PC, the third-party x64 DLL loads but `VCI_OpenDevice` returns `0`, so Direct mode is not the recommended path right now.

3. `USB-CAN-B Bridge`
   - The UI remains on 64-bit Python and PySide6.
   - A separate backend process runs on Python 32-bit.
   - The backend loads the official 32-bit DLL at `C:\Program Files (x86)\USB_CAN TOOL\ControlCAN.dll`.
   - This is the recommended path for this PC because the original USB CAN Tool can connect with the official 32-bit driver stack.

## Clear Log

The Clear Log button clears only the visible TX/RX log.

It does not disconnect CAN, stop periodic TX, reset status, change checkboxes, or send any CAN frame. New TX/RX frames appear in the log again after clearing.

## Requested Vs Actual Status

The group checkboxes are user requests, not proof that a group is physically ON.

The Status section shows actual board state from status frames:

- `Requested`: current checkbox request.
- `DO`: actual output bit from `DO Mask`.
- `Feedback P/N`: actual P/N feedback bits from `Feedback Mask`.
- `Fault`: actual group fault bit from `Fault Mask`.

If a status frame reports a fault bit for a requested group, the UI automatically clears that group's checkbox and updates the Command Mask. If periodic TX is running, the next periodic command uses the new mask and no longer requests the faulted group.

If a status frame reports fail-safe/CAN timeout, the UI clears all requested group checkboxes, updates the Command Mask to `0x00`, and stops periodic TX if it is running. This does not mark group Fault as `Yes`; the Fault column still comes only from `Fault Mask`.

If a group is still checked in the UI, the UI first waits until it has seen that group's actual `DO Mask` bit turn ON after the request. If a later status reports that the same `DO Mask` bit dropped OFF while `Fault Mask` is not set, the UI clears that checkbox as a stale request and logs the event. A newly checked box is not cleared just because the latest status still reports DO OFF.

Example:

- User requests Group 4, 5, 6: command mask `0x38`.
- Board reports Group 4 fault: fault mask bit `0x08`.
- UI clears Group 4 request.
- New command mask is `0x30` for Group 5+6.
- Log shows: `Group 4 fault detected from status, auto-unchecked.`

The UI does not auto-clear faults and does not re-enable groups. Clear Fault still sends only `Data[0]=0x00`, `Data[1]=0x01`.

`Send Once` does not keep outputs ON. Use `Start Periodic` when you need the firmware to continue receiving valid commands before its CAN command timeout.

## Logging & Diagnostic Counters

The firmware supports runtime diagnostic counters in RAM. These counters are not stored in Flash/EEPROM and reset when the MCU resets or loses power.

Diagnostic CAN IDs:

- Request: `0x530 + NodeID`
- Response: `0x540 + NodeID`
- Standard 11-bit CAN data frame.
- The PC tool sends diagnostic requests with DLC `8`.
- Firmware accepts request DLC minimum `3` and returns response DLC `8`.

Diagnostic reads do not refresh the CAN command timeout. Use Periodic Command if outputs must stay ON while reading counters.

Use the `Diagnostics` tab:

- Connect in Mock, USB-CAN-B Direct, or USB-CAN-B Bridge mode.
- Click `Read Selected Counter` for one counter.
- Click `Read All Counters` to poll all group and global counters through a paced queue.
- Enable `Auto Refresh` for periodic `Read All Counters` with interval `200..10000 ms`, default `1000 ms`.
- Click `Reset All Counters` to send `02 A5 5A 00 00 00 00 00` after confirmation.
- Click `Clear Diagnostic Display` to clear only the PC display. It does not send CAN and does not reset firmware counters.

Group counters use group index `0..5`:

| Counter ID | Name |
| --- | --- |
| `0x01` | ON Count |
| `0x02` | OFF Count |
| `0x03` | Feedback Mismatch |
| `0x04` | Group Fault |
| `0x05` | ON Timeout Fault |
| `0x06` | Unexpected OFF Fault |
| `0x07` | Fault Clear |

Global counters use group index `0xFF`:

| Counter ID | Name |
| --- | --- |
| `0x20` | CAN Command RX Count |
| `0x21` | CAN TX Count |
| `0x22` | CAN RX Error Count |
| `0x23` | CAN TX Error Count |
| `0x24` | CAN Timeout Count |
| `0x25` | Failsafe Enter Count |
| `0x26` | Diagnostic Request Count |
| `0x27` | Diagnostic Error Count |

Diagnostic status values:

| Status | Meaning |
| --- | --- |
| `0x00` | OK |
| `0x01` | INVALID_COMMAND |
| `0x02` | INVALID_COUNTER_ID |
| `0x03` | INVALID_GROUP |
| `0x04` | BAD_DLC |
| `0x05` | RESET_MAGIC_INVALID |
| `0x06` | INTERNAL_ERROR |

Mock mode also supports diagnostic requests. It keeps runtime counters in RAM, increments simple ON/OFF counters when the mock command mask changes, and resets counters on the diagnostic reset command.

## Real USB-CAN-B Mode

The real USB-CAN-B driver is implemented in `usb_can_b_driver.py` using the documented `ControlCAN.dll` API:

- `VCI_OpenDevice`
- `VCI_InitCAN`
- `VCI_ClearBuffer`
- `VCI_StartCAN`
- `VCI_Transmit`
- `VCI_Receive`
- `VCI_CloseDevice`
- optional `VCI_FindUsbDevice2`

DLL load priority:

1. Explicit DLL path passed to `UsbCanBDriver`.
2. `ControlCAN.dll` in the current working directory.
3. `ControlCAN.dll` beside `main.py`.
4. Vendor install path: `C:\Program Files (x86)\USB_CAN TOOL\ControlCAN.dll`.

Local vendor SDK files found during Phase 3:

- `C:\Program Files (x86)\USB_CAN TOOL\ControlCAN.dll`
- `C:\Program Files (x86)\USB_CAN TOOL\help\Manual\4.USB-CAN Bus Interface Adapter Interface Function Library User Instruction.pdf`

No 64-bit vendor-installed `ControlCAN.dll` was found in the checked locations:

- `C:\Program Files`
- `C:\Program Files (x86)`
- `F:\Work`
- user Downloads

An external 64-bit DLL has been copied for testing:

- Source repository: `https://github.com/JloveU/ControlCAN`
- Repo path: `ControlCANx64/ControlCAN.dll`
- Local path: `F:\Work\Project\Controller Emulator\ControlCAN.dll`
- SHA256: `77EA9C2CF8E28AB3B237B65CEAB7788AFF55552DE1EE2F3A25BD621512D8E025`

This is a third-party GitHub repository, not the local vendor installer. Verify and scan the binary before using it on a production or safety-critical PC.

Important bitness notes on this PC:

- The installed vendor `ControlCAN.dll` is x86.
- The current `.venv` Python is 64-bit.
- A 64-bit Python process cannot load a 32-bit DLL.
- Only Python `3.14-64` is currently registered by the Python launcher.
- PySide6 did not resolve for `win32` with pip, so running the whole UI on 32-bit Python is not a practical path with the current PySide6 stack.
- The copied GitHub `ControlCAN.dll` is 64-bit and can be loaded by the current `.venv` Python.

To use real USB-CAN-B mode, use one of these paths:

- Preferred: get a 64-bit `ControlCAN.dll` from the vendor/Waveshare and place it beside `main.py`.
- Current test option: use the copied third-party 64-bit `ControlCAN.dll` beside `main.py` after you have verified it.
- Alternative architecture: keep the UI on 64-bit Python and run a small 32-bit Python USB-CAN-B backend process that talks to the UI via localhost socket or subprocess stdin/stdout.

If the DLL is missing or bitness does not match, Connect shows a clear error. The driver does not pretend to send real CAN frames.

Settings for the board:

- Bitrate: 500000.
- Node ID: 0..7.
- Standard 11-bit CAN ID only.
- Data frame only, RTR is rejected.
- Command ID is calculated as `0x500 + NodeID`.
- UI direct driver mode name: `USB-CAN-B Direct`.

Current direct connection result with the copied x64 DLL:

- DLL load: OK.
- `VCI_OpenDevice(VCI_USBCAN2=4, DeviceIndex=0, Reserved=0)`: returned `0`.
- Because the device did not open, no CAN frames were sent.
- `VCI_FindUsbDevice2`: not exported by the copied x64 DLL.
- `scripts/debug_usb_can_open.py` tried the USB-CAN related types from `ControlCAN.h` with device indexes `0..3`; all returned `0`.

If Connect fails with `VCI_OpenDevice failed with return value 0`, check:

- USB-CAN-B adapter is plugged in.
- Windows driver is installed and the adapter appears in Device Manager.
- No other USB-CAN tool is currently holding the device open.
- Device index is correct. The UI default is `USB-CAN-B Device 0`.
- Device type is still `VCI_USBCAN2 = 4`, confirmed from `ControlCAN.h`.
- Channel index is `0` first; try `1` only if the adapter exposes two channels and channel 0 is not the one wired.

Observed Windows device candidate during debugging:

- Friendly name: `WinUSB Device`
- Class: `CustomUSBDevices`
- Hardware ID: `USB\VID_04D8&PID_0053`
- Service: `WinUSB`
- Manufacturer: `Microchip Technology, Inc.`

This may be the USB-CAN adapter, but Windows does not name it as USB-CAN-B here. If the original USB CAN Tool can connect to this adapter but the copied x64 DLL cannot, the likely cause is DLL/driver incompatibility rather than the CAN protocol layer.

## Debug USB-CAN Open

Run the open-device sweep:

```powershell
cd "F:\Work\Project\Controller Emulator"
.venv\Scripts\activate
python scripts\debug_usb_can_open.py
```

The script:

- Loads the same `ControlCAN.dll` as the UI driver.
- Prints Python and DLL bitness.
- Calls `VCI_FindUsbDevice2` if exported.
- Parses `ControlCAN.h` for USB-CAN related device types.
- Tries `VCI_OpenDevice(type, index, 0)` for index `0..3`.
- Calls `VCI_CloseDevice` immediately if any open succeeds.
- Does not call `VCI_InitCAN`.
- Does not send CAN frames.

Device types currently parsed from `ControlCAN.h`:

- `VCI_USBCAN1 = 3`
- `VCI_USBCAN2 = 4`
- `VCI_USBCAN2A = 4`
- `VCI_CAN232 = 6`
- `VCI_CANLITE = 8`
- `VCI_USBCAN_E_U = 20`
- `VCI_USBCAN_2E_U = 21`
- `VCI_USBCAN_4E_U = 31`
- `VCI_USBCAN_8E_U = 34`

Current result: all tested combinations returned `0`.

## Dependency Check

The x64 DLL loads in Python, so the immediate Windows loader dependency check is passing for this process. To inspect the import table more deeply, use one of:

```powershell
dumpbin /dependents "F:\Work\Project\Controller Emulator\ControlCAN.dll"
```

or open the DLL with `Dependencies.exe`.

On this PC, `dumpbin`, `depends`, and `Dependencies.exe` were not found in PATH during the debug pass.

## Windows Device Checklist

Before trying USB-CAN-B mode:

- Close the original USB CAN Tool and any CAN analyzer app.
- Unplug and replug the USB-CAN-B adapter.
- Open Device Manager and confirm the adapter appears without warning icons.
- Confirm the installed driver name and hardware ID.
- Try running the Python tool as Administrator.
- If the original USB CAN Tool can connect, note the device type/index/channel settings it uses.
- If the original tool is open or already connected, `VCI_OpenDevice` may fail in Python.

## Phase 4 Bridge Mode

Bridge mode keeps the current UI `.venv` unchanged. Install Python 32-bit separately and point the UI to it.

Set Python 32-bit path:

```powershell
setx USB_CAN_BACKEND_PYTHON32 "C:\Path\To\Python32\python.exe"
```

Optional DLL override:

```powershell
setx USB_CAN_BACKEND_DLL "C:\Program Files (x86)\USB_CAN TOOL\ControlCAN.dll"
```

Check backend prerequisites:

```powershell
cd "F:\Work\Project\Controller Emulator"
.venv\Scripts\activate
python scripts\check_backend_32bit.py
```

Current result before Python 32-bit is configured:

```text
Backend script exists=True
Official DLL exists=True
USB_CAN_BACKEND_PYTHON32 is not set.
```

Backend protocol:

- UI sends JSON lines to backend stdin.
- Backend sends JSON lines on stdout only.
- Backend writes debug and traceback text to stderr only.
- Backend does not send CAN frames unless `open/init/start` all succeed.

Bridge files:

- `bridge_protocol.py`
- `bridge_can_driver.py`
- `backend/usb_can_backend.py`
- `backend/README.md`
- `scripts/check_backend_32bit.py`
- `scripts/test_bridge_driver.py`

Run UI bridge mode:

```powershell
cd "F:\Work\Project\Controller Emulator"
.venv\Scripts\activate
python main.py
```

Then select:

```text
Driver mode = USB-CAN-B Bridge
```

Manual bridge smoke test:

```powershell
python scripts\test_bridge_driver.py --python32 "C:\Path\To\Python32\python.exe" --node-id 0 --channel 0 --bitrate 500000
```

To send Group 1 after OFF ALL:

```powershell
python scripts\test_bridge_driver.py --python32 "C:\Path\To\Python32\python.exe" --node-id 0 --send-group1
```

Safety notes:

- Close the original USB CAN Tool before using bridge mode.
- Do not let two apps hold the USB-CAN-B adapter at the same time.
- Test OFF ALL first.
- Only test Group ON after CAN_H/CAN_L/GND wiring and load safety are confirmed.

## Bitness Check

Check Python and DLL architecture:

```powershell
cd "F:\Work\Project\Controller Emulator"
.venv\Scripts\activate
python scripts\check_driver_bitness.py
```

Check a specific DLL:

```powershell
python scripts\check_driver_bitness.py --dll "C:\Path\To\ControlCAN.dll"
```

Manual Python bitness check:

```powershell
python -c "import struct, sys; print(sys.executable); print(struct.calcsize('P') * 8)"
```

Expected result for real USB-CAN-B mode: Python architecture and DLL architecture must match.

## Manual USB-CAN-B Smoke Test

Only run this when CAN_H, CAN_L, and GND are wired correctly and the DLL/Python bitness matches.

OFF ALL test:

```powershell
cd "F:\Work\Project\Controller Emulator"
.venv\Scripts\activate
python scripts\test_usb_can_b_send.py --node-id 0 --channel 0 --bitrate 500000
```

OFF ALL, then Group 1:

```powershell
python scripts\test_usb_can_b_send.py --node-id 0 --send-group1
```

This script is for manual hardware testing only. It is not part of pytest.

## Command Mask

- Group 1 = `0x01`
- Group 2 = `0x02`
- Group 3 = `0x04`
- Group 4 = `0x08`
- Group 5 = `0x10`
- Group 6 = `0x20`
- Group 3+4 = `0x0C`
- Group 4+6 = `0x28`
- Group 5+6 = `0x30`
- All = `0x3F`
- Off All = `Data[0]=0x00`, `Data[1]=0x00`
- Clear Fault = `Data[0]=0x00`, `Data[1]=0x01`

## Periodic Command

The firmware has a CAN command timeout. Use periodic TX, typically 100 ms or 500 ms, when keeping groups ON.

When periodic TX is running, the `Start Periodic` button uses a muted active style. It returns to the normal style after `Stop Periodic`, disconnect, or fail-safe/CAN timeout auto-stop.

## Firmware Protocol Summary

- CAN bitrate: 500000.
- Standard 11-bit CAN ID.
- Data frame only.
- Extended frame: not used.
- RTR: not used.
- Command ID: `0x500 + NodeID`.
- Status ID: `0x510 + NodeID`.
- Heartbeat ID: `0x520 + NodeID`.
- Diagnostic request ID: `0x530 + NodeID`.
- Diagnostic response ID: `0x540 + NodeID`.
- Status payload: `DO mask`, `feedback low`, `feedback high`, `fault mask`, `global status`, reserved bytes.
- Heartbeat payload: firmware version, Node ID, global status, RX counter low byte, TX error count low byte, sequence.
- Diagnostic read request: `01 counter_id group_index 00 00 00 00 00`.
- Diagnostic reset request: `02 A5 5A 00 00 00 00 00`.
