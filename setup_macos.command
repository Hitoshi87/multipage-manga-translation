#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
export HOMEBREW_NO_AUTO_UPDATE=1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
if [[ "$(uname -s)" != Darwin ]]; then
  echo "Bộ cài này dành cho macOS."; exit 1
fi
if [[ "${1:-}" != --install ]]; then
  if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
    "$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/manga_typesetter.py" doctor || true
  fi
  echo "Chỉ kiểm tra. Để cho phép cài dependency: bash \"$PROJECT_DIR/setup_macos.command\" --install"
  exit 0
fi
if ! command -v brew >/dev/null; then
  echo "Chưa có Homebrew. Cài từ https://brew.sh rồi chạy lại."; exit 1
fi
BREW_PREFIX="$(brew --prefix)"
for package in python@3.12 tesseract tesseract-lang; do
  if ! brew list --versions "$package" >/dev/null 2>&1; then brew install "$package"; fi
done
PYTHON_BIN="$BREW_PREFIX/opt/python@3.12/bin/python3.12"
if [[ -e "$PROJECT_DIR/.venv" ]]; then
  if ! "$PROJECT_DIR/.venv/bin/python" -c 'import sys; assert sys.version_info[:2] == (3, 12)' 2>/dev/null; then
    echo "Giữ lại .venv cũ; hãy đổi tên thư mục đó rồi chạy lại bằng Python 3.12."; exit 1
  fi
else
  "$PYTHON_BIN" -m venv "$PROJECT_DIR/.venv"
fi
"$PROJECT_DIR/.venv/bin/python" -m pip install --only-binary=:all: -r "$PROJECT_DIR/requirements.txt"
"$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/manga_typesetter.py" doctor
