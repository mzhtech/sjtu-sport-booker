#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
PIP_BIN="${VENV_DIR}/bin/pip"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-3210}"

echo "[sjtu-sport-booker] project root: ${ROOT_DIR}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Please install Python 3.10+ first."
  exit 1
fi

if ! command -v tesseract >/dev/null 2>&1; then
  echo "tesseract not found."
  echo "macOS: brew install tesseract"
  echo "Ubuntu: sudo apt-get install -y tesseract-ocr"
  exit 1
fi

if ! command -v firefox >/dev/null 2>&1; then
  echo "firefox not found."
  echo "Please install Firefox first."
  exit 1
fi

if ! command -v geckodriver >/dev/null 2>&1; then
  echo "geckodriver not found."
  echo "macOS: brew install geckodriver"
  echo "Ubuntu: sudo apt-get install -y firefox-geckodriver"
  exit 1
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "[sjtu-sport-booker] creating virtualenv..."
  python3 -m venv "${VENV_DIR}"
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "virtualenv python missing at ${PYTHON_BIN}"
  exit 1
fi

echo "[sjtu-sport-booker] installing python dependencies..."
"${PIP_BIN}" install -r "${ROOT_DIR}/requirements.txt"

echo "[sjtu-sport-booker] starting local console at http://${HOST}:${PORT}"
exec "${PYTHON_BIN}" "${ROOT_DIR}/main.py" --serve --host "${HOST}" --port "${PORT}"
