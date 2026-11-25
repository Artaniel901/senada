@echo off
rem Opens Senada without a console window. Run setup.cmd once first. The Senada shortcut does the same
rem with the Senada icon on the taskbar; this file is the fallback.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Senada belum dipasang. Jalankan setup.cmd dulu.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m senada
