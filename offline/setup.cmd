@echo off
rem One-time setup: a Python environment next to the app (nothing is installed on C:).
rem Needs Python 3.12 (py launcher) and an internet connection; models are downloaded later from the app.
cd /d "%~dp0"
set "PIP_CACHE_DIR=%~dp0.pip-cache"
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv || python -m venv .venv || goto :fail
)
".venv\Scripts\python.exe" -m pip install --upgrade pip || goto :fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail
rmdir /s /q ".pip-cache" 2>nul
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\shortcut.ps1" || echo Shortcut tidak dibuat; aplikasi tetap bisa dibuka lewat Senada.cmd.
echo Selesai. Buka shortcut Senada di Desktop atau Start. Unduh model di tab Model saat pertama kali.
pause
exit /b 0
:fail
echo Pemasangan gagal. Lihat pesan di atas.
pause
exit /b 1
