#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
PIP_BIN="${VENV_DIR}/bin/pip"

log() {
  echo "[install-macos] $1"
}

require_command() {
  local cmd="$1"
  local hint="$2"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "$hint"
    exit 1
  fi
}

ensure_brew_formula() {
  local formula="$1"
  local check_cmd="$2"
  if command -v "$check_cmd" >/dev/null 2>&1; then
    log "$formula already installed."
    return
  fi
  log "Installing $formula..."
  brew install "$formula"
}

ensure_brew_cask() {
  local cask="$1"
  local check_cmd="$2"
  if command -v "$check_cmd" >/dev/null 2>&1; then
    log "$cask already installed."
    return
  fi
  log "Installing $cask..."
  brew install --cask "$cask"
}

log "project root: ${ROOT_DIR}"

if ! command -v brew >/dev/null 2>&1; then
  cat <<'EOF'
Homebrew not found.
Please install Homebrew first:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
EOF
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  log "python3 already installed: $(python3 --version 2>&1)"
else
  log "Installing python..."
  brew install python
fi

ensure_brew_cask "firefox" "firefox"
ensure_brew_formula "geckodriver" "geckodriver"
ensure_brew_formula "tesseract" "tesseract"

if [[ ! -d "${VENV_DIR}" ]]; then
  log "Creating virtualenv..."
  python3 -m venv "${VENV_DIR}"
else
  log ".venv already exists."
fi

require_command "${PYTHON_BIN}" "virtualenv python missing at ${PYTHON_BIN}"
require_command "${PIP_BIN}" "virtualenv pip missing at ${PIP_BIN}"

log "Upgrading pip..."
"${PYTHON_BIN}" -m pip install --upgrade pip

log "Installing Python dependencies..."
"${PIP_BIN}" install -r "${ROOT_DIR}/requirements.txt"

log "All dependencies are ready."
log "Next step: ./start.sh"
