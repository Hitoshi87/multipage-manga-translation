#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
export HOMEBREW_NO_AUTO_UPDATE=1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
if [[ "$(uname -s)" != Darwin ]]; then
  echo 'Use setup_windows.cmd or setup_linux.sh for this OS.'; exit 1
fi
if [[ " $* " == *" --install "* ]]; then
  if ! command -v brew >/dev/null; then
    echo 'Install Homebrew from https://brew.sh then rerun.'; exit 1
  fi
  for package in python@3.12 tesseract; do
    if ! brew list --versions "$package" >/dev/null 2>&1; then brew install "$package"; fi
  done
fi
PYTHON_BIN="$(command -v python3.12 || true)"
if command -v brew >/dev/null; then
  BREW_PYTHON="$(brew --prefix)/opt/python@3.12/bin/python3.12"
  if [[ -x "$BREW_PYTHON" ]]; then PYTHON_BIN="$BREW_PYTHON"; fi
fi
if [[ -z "$PYTHON_BIN" ]]; then
  echo 'Missing Python 3.12. Run bash setup_macos.command --install'; exit 1
fi
exec "$PYTHON_BIN" "$PROJECT_DIR/setup.py" "$@"
