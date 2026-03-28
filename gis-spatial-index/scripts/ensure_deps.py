#!/usr/bin/env python3
"""空間インデックススキルに必要な依存パッケージをインストールする。"""
import subprocess
import sys
import json

REQUIRED = {
    "h3": "h3>=4.0",
    "openlocationcode": "openlocationcode",
    "mgrs": "mgrs",
}


def ensure():
    installed = []
    failed = []
    for mod, pip_name in REQUIRED.items():
        try:
            __import__(mod)
        except ImportError:
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pip_name, "-q"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                # インストール後に実際にインポートできるか検証
                __import__(mod)
                installed.append(pip_name)
            except (subprocess.CalledProcessError, ImportError):
                failed.append(pip_name)

    result = {"status": "ok" if not failed else "partial", "installed": installed}
    if failed:
        result["failed"] = failed
        result["hint"] = f"pip install {' '.join(failed)} を手動で実行してください"
    print(json.dumps(result))


if __name__ == "__main__":
    ensure()
