#!/usr/bin/env python3
"""CLI and Photoshop JSON worker entry point. Use .venv/bin/python."""
import os
import subprocess
import sys
from pathlib import Path

from manga_ai.cli import main
from manga_ai.io import write_json


def _run_guarded_worker(argv: list[str]) -> int:
    try:
        req_idx = argv.index("--request")
        res_idx = argv.index("--response")
        req_path = Path(argv[req_idx + 1])
        res_path = Path(argv[res_idx + 1])
    except (ValueError, IndexError):
        return main(argv)

    env = os.environ.copy()
    env["MTA_WORKER_INNER"] = "1"
    cancel_path = req_path.parent / "cancel"
    last_rc = 1
    for attempt in range(2):
        proc = subprocess.run([sys.executable, __file__, *argv], env=env)
        last_rc = proc.returncode
        if res_path.exists() or cancel_path.exists():
            return last_rc
    if not res_path.exists():
        write_json(res_path, {
            "ok": False,
            "error": f"Worker process terminated unexpectedly (exit code {last_rc})",
            "type": "RuntimeError",
        })
    return last_rc


if __name__ == "__main__":
    if (
        os.environ.get("MTA_WORKER_INNER") != "1"
        and "--request" in sys.argv[1:]
        and "--response" in sys.argv[1:]
    ):
        raise SystemExit(_run_guarded_worker(sys.argv[1:]))
    raise SystemExit(main())
