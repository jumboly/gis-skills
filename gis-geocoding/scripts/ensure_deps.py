#!/usr/bin/env python3
"""ジオコーディングスキルに必要な依存パッケージをインストールする。"""
import subprocess
import sys
import json

REQUIRED = {
    "geopy": "geopy",
    "requests": "requests",
}


def ensure():
    installed = []
    for mod, pip_name in REQUIRED.items():
        try:
            __import__(mod)
        except ImportError:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pip_name, "-q"],
                stdout=subprocess.DEVNULL,
            )
            installed.append(pip_name)
    print(json.dumps({"status": "ok", "installed": installed}))


if __name__ == "__main__":
    ensure()
