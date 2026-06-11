#!/usr/bin/env python3
"""PACIFIC CLI — Standalone entry point for packaged executables."""

import sys
import os

# Ensure the bundled package is on the path
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    base_path = sys._MEIPASS
    os.environ.setdefault("PACIFIC_BUNDLED", "1")
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, base_path)

from pacific.cli import cli

if __name__ == "__main__":
    cli()
