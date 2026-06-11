#!/usr/bin/env python3
"""
Project launcher — run from the repo root.

Examples:
    python main.py --part 5
    python3 main.py
"""
import runpy
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC))

if __name__ == "__main__":
    runpy.run_path(str(SRC / "main.py"), run_name="__main__")
