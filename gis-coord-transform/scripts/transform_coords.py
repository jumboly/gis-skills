#!/usr/bin/env python3
"""座標変換スクリプト - pyproj を使ったバッチ座標変換"""
from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys


def _auto_install():
    """未インストールの依存パッケージを自動インストールする"""
    for mod, pkg in {"pyproj": "pyproj"}.items():
        try:
            __import__(mod)
        except ImportError:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                stdout=subprocess.DEVNULL,
            )


_auto_install()

from pyproj import Transformer


# 緯度・経度カラム名の自動検出用マッピング
LAT_NAMES = {"lat", "latitude", "y", "緯度"}
LON_NAMES = {"lon", "lng", "longitude", "x", "経度"}


def detect_columns(header: list[str]) -> tuple[int, int]:
    """CSVヘッダーから緯度・経度カラムのインデックスを自動検出する"""
    lower = [h.strip().lower() for h in header]
    lat_idx = lon_idx = None
    for i, name in enumerate(lower):
        if name in LAT_NAMES:
            lat_idx = i
        elif name in LON_NAMES:
            lon_idx = i
    if lat_idx is None or lon_idx is None:
        raise ValueError(
            f"緯度・経度カラムを検出できません。ヘッダー: {header}\n"
            f"対応カラム名 - 緯度: {LAT_NAMES}, 経度: {LON_NAMES}"
        )
    return lat_idx, lon_idx


def transform_points(
    from_epsg: int, to_epsg: int, points: list[tuple[float, float]]
) -> list[dict]:
    """座標リストを変換し、結果を辞書リストで返す"""
    # always_xy=True: 入出力を常に (x=経度, y=緯度) の順にする
    transformer = Transformer.from_crs(
        f"EPSG:{from_epsg}", f"EPSG:{to_epsg}", always_xy=True
    )
    results = []
    for lon, lat in points:
        x, y = transformer.transform(lon, lat)
        results.append({"input_lon": lon, "input_lat": lat, "output_x": x, "output_y": y})
    return results


def parse_inline(value: str) -> list[tuple[float, float]]:
    """インライン入力 "lat,lon" をパースする（経度,緯度の順のタプルを返す）"""
    parts = value.split(",")
    if len(parts) != 2:
        raise ValueError(f"インライン座標は 'lat,lon' 形式で指定してください: {value}")
    lat, lon = float(parts[0].strip()), float(parts[1].strip())
    return [(lon, lat)]


def read_csv_points(filepath: str) -> tuple[list[str], list[tuple[float, float]]]:
    """CSVファイルから座標を読み取る"""
    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        lat_idx, lon_idx = detect_columns(header)
        points = []
        for row in reader:
            if not row or all(c.strip() == "" for c in row):
                continue
            lat = float(row[lat_idx].strip())
            lon = float(row[lon_idx].strip())
            points.append((lon, lat))
    return header, points


def main():
    parser = argparse.ArgumentParser(
        description="pyproj を使ったバッチ座標変換"
    )
    parser.add_argument(
        "--from-epsg", type=int, required=True, help="変換元の EPSG コード"
    )
    parser.add_argument(
        "--to-epsg", type=int, required=True, help="変換先の EPSG コード"
    )
    parser.add_argument(
        "--input", required=True,
        help="CSVファイルパス、またはインライン座標 'lat,lon'"
    )
    parser.add_argument(
        "--output", default=None, help="出力CSVファイルパス（省略時は標準出力にJSON）"
    )
    args = parser.parse_args()

    try:
        # インライン入力かファイル入力かを判定
        if "," in args.input and not args.input.endswith(".csv"):
            points = parse_inline(args.input)
        else:
            _, points = read_csv_points(args.input)

        results = transform_points(args.from_epsg, args.to_epsg, points)

        if args.output:
            with open(args.output, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["input_lon", "input_lat", "output_x", "output_y"]
                )
                writer.writeheader()
                writer.writerows(results)
            output_msg = {"status": "ok", "output_file": args.output, "count": len(results)}
            print(json.dumps(output_msg, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(results, ensure_ascii=False, indent=2))

    except FileNotFoundError:
        print(json.dumps({"error": f"ファイルが見つかりません: {args.input}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"変換中にエラーが発生しました: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
