@echo off
rem Opens Cicada Offline without a console window. Run setup.cmd once first.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Cicada Offline belum dipasang. Jalankan setup.cmd dulu.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m cicada_offline
