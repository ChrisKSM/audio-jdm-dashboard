#!/usr/bin/env python3
"""로컬 실행 헬퍼 — port 8200, reload."""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    os.chdir(ROOT)
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8200",
        "--reload",
    ]
    print("Starting Audio JDM Dashboard at http://127.0.0.1:8200")
    subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
