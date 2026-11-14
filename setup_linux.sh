#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ "$(uname -s)" != Linux ]]; then
  echo 'Use setup_macos.command or setup_windows.cmd for this OS.'; exit 1
fi
if ! command -v python3.12 >/dev/null; then
  echo 'Install Python 3.12 and its venv package. See docs/runtime/installation.md.'; exit 1
fi
exec python3.12 "$PROJECT_DIR/setup.py" "$@"
