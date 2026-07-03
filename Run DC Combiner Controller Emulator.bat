@echo off
setlocal
chcp 65001 >nul

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto run_app

echo Không tìm thấy .venv.
echo Hãy tạo môi trường bằng:
echo.
echo python -m venv .venv
echo .venv\Scripts\activate
echo pip install -r requirements.txt
echo.
pause
exit /b 1

:run_app
".venv\Scripts\python.exe" "main.py"
if errorlevel 1 pause
