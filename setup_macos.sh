#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
APP_NAME="Visionary Navigator.app"
DIST_APP_PATH="${ROOT_DIR}/dist/${APP_NAME}"
TARGET_APP_PATH="/Applications/${APP_NAME}"

echo "[1/6] Cleaning previous build artifacts..."
rm -rf "${ROOT_DIR}/build" "${ROOT_DIR}/dist"
find "${ROOT_DIR}" -type d -name "__pycache__" -prune -exec rm -rf {} +

echo "[2/6] Preparing virtual environment..."
if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

echo "[3/6] Installing dependencies..."
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r "${ROOT_DIR}/requirements.txt"
"${VENV_DIR}/bin/python" -m pip install pyinstaller

echo "[4/6] Building macOS app bundle..."
"${VENV_DIR}/bin/python" "${ROOT_DIR}/build.py" --os macos

if [[ ! -d "${DIST_APP_PATH}" ]]; then
  echo "Build finished, but app bundle not found: ${DIST_APP_PATH}"
  exit 1
fi

echo "[5/6] Installing app into /Applications..."
if rm -rf "${TARGET_APP_PATH}" 2>/dev/null && cp -R "${DIST_APP_PATH}" "${TARGET_APP_PATH}" 2>/dev/null; then
  echo "Installed without sudo."
else
  echo "Admin permission required for /Applications."
  sudo rm -rf "${TARGET_APP_PATH}"
  sudo cp -R "${DIST_APP_PATH}" "${TARGET_APP_PATH}"
fi

echo "[6/6] Done."
echo "Installed app: ${TARGET_APP_PATH}"
echo "You can launch Visionary Navigator from Applications."
