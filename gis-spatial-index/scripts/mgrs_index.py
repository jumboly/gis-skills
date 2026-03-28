#!/usr/bin/env python3
"""MGRS (Military Grid Reference System) 空間インデックススクリプト - エンコード・デコード・境界ポリゴン"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys


def _auto_install():
    for mod, pkg in {"mgrs": "mgrs"}.items():
        try:
            __import__(mod)
        except ImportError:
            import subprocess, sys
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                stdout=subprocess.DEVNULL,
            )

_auto_install()

import mgrs  # noqa: E402

# 各精度レベルのグリッドサイズ（メートル）
MGRS_GRID_SIZES = {
    0: 100000,  # 100 km
    1: 10000,   # 10 km
    2: 1000,    # 1 km
    3: 100,     # 100 m
    4: 10,      # 10 m
    5: 1,       # 1 m
}

# CSV 列名の自動検出用
LAT_NAMES = {"lat", "latitude", "y", "緯度"}
LON_NAMES = {"lon", "lng", "longitude", "x", "経度"}
MGRS_NAMES = {"mgrs", "military_grid", "MGRS", "code", "グリッド座標"}

# MGRS 文字列から精度を判定する正規表現
# 形式: zone(1-2桁数字) + band(1文字) + grid_id(2文字) + easting(0-5桁) + northing(0-5桁)
_MGRS_RE = re.compile(r"^(\d{1,2})([A-Z])([A-Z]{2})(\d*)$")


def _parse_mgrs_precision(mgrs_str: str) -> int:
    """MGRS 文字列から精度レベル（0-5）を判定する。

    数値部分の桁数を2で割った値が精度。grid_id の後に数字がなければ精度0。
    """
    m = _MGRS_RE.match(mgrs_str.strip().upper())
    if not m:
        raise ValueError(f"不正な MGRS 文字列です: '{mgrs_str}'")
    digits = m.group(4)
    if len(digits) % 2 != 0:
        raise ValueError(f"MGRS の数値部分が奇数桁です: '{digits}'（偶数桁が必要）")
    return len(digits) // 2


def _grid_offsets(lat: float, grid_size_m: float) -> tuple[float, float]:
    """グリッドサイズ(m)を緯度・経度方向の度数に近似変換する。

    緯度1度 ≒ 111320m は場所によらず概ね一定だが、
    経度1度の距離は緯度に依存するため cos(lat) で補正する。
    """
    lat_offset = grid_size_m / 111320.0
    lon_offset = grid_size_m / (111320.0 * math.cos(math.radians(lat)))
    return lat_offset, lon_offset


def encode(lat: float, lon: float, precision: int = 5) -> dict:
    """緯度経度を MGRS 文字列にエンコードし、付帯情報を返す。"""
    m = mgrs.MGRS()
    mgrs_str = m.toMGRS(lat, lon, MGRSPrecision=precision)
    grid_size_m = MGRS_GRID_SIZES[precision]

    # SW コーナーを取得して中心を計算
    sw_lat, sw_lon = m.toLatLon(mgrs_str)
    lat_off, lon_off = _grid_offsets(sw_lat, grid_size_m)
    center_lat = sw_lat + lat_off / 2
    center_lon = sw_lon + lon_off / 2

    return {
        "mgrs": mgrs_str,
        "precision": precision,
        "grid_size_m": grid_size_m,
        "center": {"lat": round(center_lat, 8), "lon": round(center_lon, 8)},
        "bbox": [
            round(sw_lon, 8),
            round(sw_lat, 8),
            round(sw_lon + lon_off, 8),
            round(sw_lat + lat_off, 8),
        ],
        "input": {"lat": lat, "lon": lon},
    }


def decode(mgrs_str: str) -> dict:
    """MGRS 文字列をデコードし、中心座標と bbox を返す。"""
    mgrs_str = mgrs_str.strip().upper()
    precision = _parse_mgrs_precision(mgrs_str)
    grid_size_m = MGRS_GRID_SIZES[precision]

    m = mgrs.MGRS()
    sw_lat, sw_lon = m.toLatLon(mgrs_str)
    lat_off, lon_off = _grid_offsets(sw_lat, grid_size_m)
    center_lat = sw_lat + lat_off / 2
    center_lon = sw_lon + lon_off / 2

    return {
        "mgrs": mgrs_str,
        "precision": precision,
        "grid_size_m": grid_size_m,
        "center": {"lat": round(center_lat, 8), "lon": round(center_lon, 8)},
        "bbox": [
            round(sw_lon, 8),
            round(sw_lat, 8),
            round(sw_lon + lon_off, 8),
            round(sw_lat + lat_off, 8),
        ],
    }


def boundary_geojson(mgrs_str: str) -> dict:
    """MGRS セルの境界を GeoJSON Polygon として返す。"""
    info = decode(mgrs_str)
    west, south, east, north = info["bbox"]
    return {
        "type": "Feature",
        "properties": {
            "mgrs": info["mgrs"],
            "precision": info["precision"],
            "grid_size_m": info["grid_size_m"],
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south],
            ]],
        },
    }


def _detect_column(fieldnames: list[str], candidates: set[str]) -> str | None:
    """CSV ヘッダーから候補名に一致する列名を返す。"""
    for name in fieldnames:
        if name.strip().lower() in candidates:
            return name
    return None


def _batch_process(
    input_path: str,
    output_path: str | None,
    operation: str,
    precision: int,
) -> None:
    """CSV バッチ処理: encode または decode を一括実行する。"""
    with open(input_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])

        if operation == "encode":
            lat_col = _detect_column(fieldnames, LAT_NAMES)
            lon_col = _detect_column(fieldnames, LON_NAMES)
            if not lat_col or not lon_col:
                _error(
                    f"CSV に緯度列 {LAT_NAMES} と経度列 {LON_NAMES} が必要です。"
                    f"検出された列: {fieldnames}"
                )
            results = []
            for row in reader:
                try:
                    lat = float(row[lat_col])
                    lon = float(row[lon_col])
                    info = encode(lat, lon, precision)
                    results.append({
                        "lat": lat,
                        "lon": lon,
                        "mgrs": info["mgrs"],
                        "precision": precision,
                        "center_lat": info["center"]["lat"],
                        "center_lon": info["center"]["lon"],
                    })
                except (ValueError, KeyError) as e:
                    results.append({
                        "lat": row.get(lat_col, ""),
                        "lon": row.get(lon_col, ""),
                        "mgrs": None,
                        "error": str(e),
                    })

        elif operation == "decode":
            # MGRS 列の検出は大文字小文字を区別せず行う
            mgrs_col = _detect_column(fieldnames, {n.lower() for n in MGRS_NAMES})
            if not mgrs_col:
                _error(
                    f"CSV に MGRS 列 {MGRS_NAMES} が必要です。"
                    f"検出された列: {fieldnames}"
                )
            results = []
            for row in reader:
                try:
                    code = row[mgrs_col].strip()
                    info = decode(code)
                    results.append({
                        "mgrs": info["mgrs"],
                        "lat": info["center"]["lat"],
                        "lon": info["center"]["lon"],
                        "bbox_w": info["bbox"][0],
                        "bbox_s": info["bbox"][1],
                        "bbox_e": info["bbox"][2],
                        "bbox_n": info["bbox"][3],
                    })
                except (ValueError, KeyError) as e:
                    results.append({
                        "mgrs": row.get(mgrs_col, ""),
                        "lat": None,
                        "lon": None,
                        "error": str(e),
                    })
        else:
            _error(f"--operation は 'encode' または 'decode' を指定してください（指定値: {operation}）")

    if output_path:
        if results:
            out_fields = [k for k in results[0].keys() if k != "error"]
            with open(output_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(results)
            print(json.dumps({
                "status": "success",
                "operation": operation,
                "output_file": output_path,
                "count": len(results),
                "errors": sum(1 for r in results if r.get("error")),
            }, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({
                "status": "success",
                "operation": operation,
                "output_file": output_path,
                "count": 0,
            }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({
            "status": "success",
            "operation": operation,
            "results": results,
        }, ensure_ascii=False, indent=2))


def _error(msg: str) -> None:
    """エラーメッセージを stderr に JSON 出力して終了する。"""
    print(json.dumps({"error": msg}, ensure_ascii=False), file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="MGRS 空間インデックス -- エンコード・デコード・境界ポリゴン出力"
    )

    parser.add_argument("--lat", type=float, default=None, help="緯度 (WGS84)")
    parser.add_argument("--lon", type=float, default=None, help="経度 (WGS84)")
    parser.add_argument("--precision", type=int, default=5, help="MGRS 精度（0=100km, 1=10km, 2=1km, 3=100m, 4=10m, 5=1m）")
    parser.add_argument("--mgrs", type=str, default=None, help="MGRS 文字列")
    parser.add_argument("--boundary", action="store_true", help="セル境界を GeoJSON Polygon で出力")
    parser.add_argument("--input", type=str, default=None, help="入力 CSV ファイルパス")
    parser.add_argument("--output", type=str, default=None, help="出力 CSV ファイルパス")
    parser.add_argument("--operation", type=str, default=None, help="バッチ操作（encode / decode）")

    args = parser.parse_args()

    try:
        # ---- バッチ CSV 処理 ----
        if args.input:
            if not args.operation:
                _error("--input を指定した場合は --operation (encode/decode) も必要です。")
            _batch_process(args.input, args.output, args.operation, args.precision)
            return

        # ---- MGRS 入力が必要な操作 ----
        if args.mgrs:
            if args.boundary:
                result = boundary_geojson(args.mgrs)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return

            # デフォルト: デコード
            result = decode(args.mgrs)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # ---- 緯度経度入力 → エンコード ----
        if args.lat is not None and args.lon is not None:
            if not (-90 <= args.lat <= 90):
                _error("緯度は -90 ~ 90 の範囲で指定してください。")
            if not (-180 <= args.lon <= 180):
                _error("経度は -180 ~ 180 の範囲で指定してください。")
            if not (0 <= args.precision <= 5):
                _error("精度は 0~5 の範囲で指定してください。")

            result = encode(args.lat, args.lon, args.precision)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        _error(
            "引数が不足しています。--lat/--lon（エンコード）、--mgrs（デコード）、"
            "--input（バッチ）のいずれかを指定してください。"
        )

    except ValueError as e:
        _error(str(e))
    except FileNotFoundError as e:
        _error(f"ファイルが見つかりません: {e}")
    except Exception as e:
        _error(f"処理中にエラーが発生しました: {e}")


if __name__ == "__main__":
    main()
