# USB-CAN-B Backend

This backend is for Phase 4 bridge mode.

It must be launched with 32-bit Python so it can load the official 32-bit DLL:

```powershell
C:\Program Files (x86)\USB_CAN TOOL\ControlCAN.dll
```

The backend uses JSON lines over stdin/stdout. Debug and traceback output goes to stderr only.

Run a ping check through the UI environment:

```powershell
cd "F:\Work\Project\Controller Emulator"
.venv\Scripts\activate
python scripts\check_backend_32bit.py
```

Set the Python 32-bit path before using bridge mode:

```powershell
setx USB_CAN_BACKEND_PYTHON32 "C:\Path\To\Python32\python.exe"
```
