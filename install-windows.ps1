Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $RootDir ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$PipExe = Join-Path $VenvDir "Scripts\pip.exe"

function Write-Info {
  param([string]$Message)
  Write-Host "[install-windows] $Message"
}

function Command-Exists {
  param([string]$CommandName)
  return $null -ne (Get-Command $CommandName -ErrorAction SilentlyContinue)
}

function Ensure-Winget {
  if (Command-Exists "winget") {
    return
  }

  Write-Host "winget not found. Please install App Installer from Microsoft Store first."
  exit 1
}

function Ensure-WingetPackage {
  param(
    [string]$Id,
    [string]$DisplayName,
    [scriptblock]$Check
  )

  if (& $Check) {
    Write-Info "$DisplayName already installed."
    return
  }

  Write-Info "Installing $DisplayName..."
  winget install --id $Id --exact --accept-package-agreements --accept-source-agreements
}

Write-Info "project root: $RootDir"
Ensure-Winget

Ensure-WingetPackage -Id "Python.Python.3.12" -DisplayName "Python 3" -Check { Command-Exists "python" -or Command-Exists "python3" }
Ensure-WingetPackage -Id "Mozilla.Firefox" -DisplayName "Firefox" -Check { Command-Exists "firefox" }
Ensure-WingetPackage -Id "Mozilla.GeckoDriver" -DisplayName "GeckoDriver" -Check { Command-Exists "geckodriver" }
Ensure-WingetPackage -Id "UB-Mannheim.TesseractOCR" -DisplayName "Tesseract OCR" -Check { Command-Exists "tesseract" }

$PythonCmd = if (Command-Exists "python") { "python" } elseif (Command-Exists "python3") { "python3" } else { $null }
if (-not $PythonCmd) {
  Write-Host "Python is still unavailable in PATH. Please reopen PowerShell and rerun this script."
  exit 1
}

if (-not (Test-Path $VenvDir)) {
  Write-Info "Creating virtualenv..."
  & $PythonCmd -m venv $VenvDir
} else {
  Write-Info ".venv already exists."
}

if (-not (Test-Path $PythonExe)) {
  Write-Host "virtualenv python missing at $PythonExe"
  exit 1
}

if (-not (Test-Path $PipExe)) {
  Write-Host "virtualenv pip missing at $PipExe"
  exit 1
}

Write-Info "Upgrading pip..."
& $PythonExe -m pip install --upgrade pip

Write-Info "Installing Python dependencies..."
& $PipExe install -r (Join-Path $RootDir "requirements.txt")

Write-Info "All dependencies are ready."
Write-Info "Next step: .\\start-windows.bat"
