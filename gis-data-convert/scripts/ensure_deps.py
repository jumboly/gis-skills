#!/usr/bin/env python3
"""データ変換スキルに必要な依存パッケージをインストールする。

fiona/GDAL のインストールが失敗する場合は、OS に応じた方法で GDAL を先にインストールしてから再試行する。
  macOS:   brew install gdal
  Linux:   sudo apt install gdal-bin libgdal-dev (Debian/Ubuntu)
  Windows: conda install -c conda-forge gdal
GeoJSON/CSV 間の変換は純 Python でも対応可能。
"""
import platform
import subprocess
import sys
import json


REQUIRED = {
    "fiona": "fiona",
    "geopandas": "geopandas",
    "pyproj": "pyproj",
}

# fiona/GDAL が入らない環境でも最低限動作するためのフォールバック
FALLBACK = {
    "geojson": "geojson",
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
                installed.append(pip_name)
            except subprocess.CalledProcessError:
                failed.append(pip_name)

    # GDAL 系が失敗した場合のフォールバック
    if failed:
        for mod, pip_name in FALLBACK.items():
            try:
                __import__(mod)
            except ImportError:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pip_name, "-q"],
                    stdout=subprocess.DEVNULL,
                )
                installed.append(pip_name)

    result = {"status": "ok" if not failed else "partial", "installed": installed}
    if failed:
        result["failed"] = failed
        # OS に応じたインストール手順を提示
        os_name = platform.system()
        if os_name == "Darwin":
            result["hint"] = "brew install gdal を実行してから再試行してください"
        elif os_name == "Linux":
            result["hint"] = (
                "sudo apt install gdal-bin libgdal-dev (Debian/Ubuntu) "
                "または sudo dnf install gdal gdal-devel (Fedora/RHEL) "
                "を実行してから再試行してください"
            )
        elif os_name == "Windows":
            result["hint"] = (
                "conda install -c conda-forge gdal (推奨) "
                "または OSGeo4W (https://trac.osgeo.org/osgeo4w/) "
                "で GDAL をインストールしてから再試行してください"
            )
        else:
            result["hint"] = "GDAL をシステムにインストールしてから再試行してください"
    print(json.dumps(result))


if __name__ == "__main__":
    ensure()
