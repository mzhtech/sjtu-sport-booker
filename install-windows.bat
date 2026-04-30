@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "SCRIPT_PATH=%ROOT_DIR%install-windows.ps1"

if not exist "%POWERSHELL_EXE%" (
  echo [install-windows] PowerShell not found.
  exit /b 1
)

if not exist "%SCRIPT_PATH%" (
  echo [install-windows] install-windows.ps1 not found.
  exit /b 1
)

echo [install-windows] launching PowerShell installer...
"%POWERSHELL_EXE%" -ExecutionPolicy Bypass -File "%SCRIPT_PATH%"
