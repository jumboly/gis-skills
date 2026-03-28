#!/usr/bin/env python3
"""測地系変換スクリプト - pyproj 標準変換および TKY2JGD/PatchJGD パラメータファイル対応"""

import argparse
import csv
import json
import subprocess
import sys


def _auto_install():
    """未インストールの依存パッケージを自動インストールする"""
    for mod, pkg in {"pyproj": "pyproj", "jgdtrans": "jgdtrans"}.items():
        try:
            __import__(mod)
        except ImportError:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                stdout=subprocess.DEVNULL,
            )


_auto_install()

import os
sys.path.insert(0, os.path.dirname(__file__))

from pyproj import Transformer
from transform_coords import detect_columns


def parse_input(input_str: str) -> list[tuple[float, float]]:
    """入力をパースして (lat, lon) のリストを返す"""
    if "," in input_str and not input_str.endswith(".csv"):
        parts = input_str.split(",")
        if len(parts) != 2:
            raise ValueError(f"インライン座標は 'lat,lon' 形式で指定してください: {input_str}")
        return [(float(parts[0].strip()), float(parts[1].strip()))]
    else:
        with open(input_str, encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader)
            lat_idx, lon_idx = detect_columns(header)
            points = []
            for row in reader:
                if not row or all(c.strip() == "" for c in row):
                    continue
                lat = float(row[lat_idx].strip())
                lon = float(row[lon_idx].strip())
                points.append((lat, lon))
        return points


def transform_pyproj(
    points: list[tuple[float, float]], direction: str
) -> list[dict]:
    """pyproj を使って日本測地系(EPSG:4301)→JGD2011(EPSG:6668) の変換を行う"""
    if direction == "forward":
        from_crs, to_crs = "EPSG:4301", "EPSG:6668"
    else:
        from_crs, to_crs = "EPSG:6668", "EPSG:4301"

    # always_xy=True: (経度, 緯度) の順で入出力
    transformer = Transformer.from_crs(from_crs, to_crs, always_xy=True)
    results = []
    for lat, lon in points:
        out_lon, out_lat = transformer.transform(lon, lat)
        results.append({
            "input_lat": lat,
            "input_lon": lon,
            "output_lat": out_lat,
            "output_lon": out_lon,
            "method": "pyproj",
            "direction": direction,
            "from_crs": from_crs,
            "to_crs": to_crs,
        })
    return results


def transform_jgdtrans(
    points: list[tuple[float, float]],
    par_file: str,
    method: str,
    direction: str,
) -> list[dict]:
    """jgdtrans ライブラリを使って TKY2JGD/PatchJGD パラメータファイルで変換する"""
    try:
        import jgdtrans
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "jgdtrans", "-q"],
            stdout=subprocess.DEVNULL,
        )
        import jgdtrans

    # パラメータファイルの種類に応じた読み込み
    with open(par_file) as f:
        if method == "tky2jgd":
            tf = jgdtrans.load(f, format="TKY2JGD")
        else:
            tf = jgdtrans.load(f, format="PatchJGD")

    results = []
    for lat, lon in points:
        point = jgdtrans.Point(latitude=lat, longitude=lon, altitude=0.0)
        if direction == "forward":
            transformed = tf.forward(point)
        else:
            transformed = tf.backward(point)

        results.append({
            "input_lat": lat,
            "input_lon": lon,
            "output_lat": transformed.latitude,
            "output_lon": transformed.longitude,
            "method": method,
            "direction": direction,
            "par_file": par_file,
        })
    return results


def main():
    parser = argparse.ArgumentParser(
        description="測地系変換 - pyproj / TKY2JGD / PatchJGD 対応"
    )
    parser.add_argument(
        "--method",
        choices=["pyproj", "tky2jgd", "patchjgd"],
        required=True,
        help="変換方法 (pyproj: 標準変換, tky2jgd: TKY2JGDパラメータ, patchjgd: PatchJGDパラメータ)",
    )
    parser.add_argument(
        "--par-file",
        default=None,
        help=".par パラメータファイルのパス（tky2jgd/patchjgd 使用時は必須）",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="CSVファイルパス、またはインライン座標 'lat,lon'",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="出力CSVファイルパス（省略時は標準出力にJSON）",
    )
    parser.add_argument(
        "--direction",
        choices=["forward", "backward"],
        default="forward",
        help="変換方向 (forward: 旧→新, backward: 新→旧, デフォルト: forward)",
    )
    args = parser.parse_args()

    # tky2jgd/patchjgd の場合は par-file が必須
    if args.method in ("tky2jgd", "patchjgd") and not args.par_file:
        parser.error(f"--method {args.method} を使用する場合、--par-file は必須です。")

    try:
        points = parse_input(args.input)

        if args.method == "pyproj":
            results = transform_pyproj(points, args.direction)
        else:
            results = transform_jgdtrans(
                points, args.par_file, args.method, args.direction
            )

        if args.output:
            fieldnames = ["input_lat", "input_lon", "output_lat", "output_lon"]
            with open(args.output, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(results)
            output_msg = {"status": "ok", "output_file": args.output, "count": len(results)}
            print(json.dumps(output_msg, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(results, ensure_ascii=False, indent=2))

    except FileNotFoundError as e:
        print(json.dumps({"error": f"ファイルが見つかりません: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"変換中にエラーが発生しました: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
