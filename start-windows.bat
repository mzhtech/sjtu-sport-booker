@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "VENV_DIR=%ROOT_DIR%.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "HOST=127.0.0.1"
set "PORT=3210"

if not exist "%PYTHON_EXE%" (
  echo [start-windows] Python virtualenv not found.
  echo [start-windows] Please run install-windows.ps1 first.
  exit /b 1
)

echo [start-windows] starting local console at http://%HOST%:%PORT%
"%PYTHON_EXE%" "%ROOT_DIR%main.py" --serve --host %HOST% --port %PORT%
