#!/usr/bin/env python3
"""Compatibility entry point. Produces reviewed JSON manifests in the new format."""
import sys
from manga_ai.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["scan", *sys.argv[1:]]))
