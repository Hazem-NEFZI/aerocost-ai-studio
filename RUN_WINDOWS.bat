@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  set PYTHON=python
) else (
  set PYTHON=py
)
echo Starting AEROCOST AI Engineering Studio...
%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency setup failed. Ensure Python 3.10+ is installed.
  pause
  exit /b 1
)
start "" "http://127.0.0.1:8502"
%PYTHON% backend.py --port 8502
pause
