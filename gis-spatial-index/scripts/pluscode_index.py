#!/usr/bin/env python3
"""Plus Code (Open Location Code) 空間インデックススクリプト - エンコード・デコード・境界出力"""
from __future__ import annotations

import argparse
import csv
import json
import sys


def _auto_install():
    for mod, pkg in {"openlocationcode": "openlocationcode"}.items():
        try:
            __import__(mod)
        except ImportError:
            import subprocess, sys
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                stdout=subprocess.DEVNULL,
            )

_auto_install()

from openlocationcode import openlocationcode as olc

# CSV 列名の自動検出用
LAT_NAMES = {"lat", "latitude", "y", "緯度"}
LON_NAMES = {"lon", "lng", "longitude", "x", "経度"}
CODE_NAMES = {"pluscode", "plus_code", "olc", "code", "open_location_code", "プラスコード"}


def _error(msg: str) -> None:
    """エラーメッセージを stderr に JSON 出力して終了する。"""
    print(json.dumps({"error": msg}, ensure_ascii=False), file=sys.stderr)
    sys.exit(1)


def _detect_column(fieldnames: list[str], candidates: set[str]) -> str | None:
    """CSV ヘッダーから候補名に一致する列名を返す。"""
    for name in fieldnames:
        if name.strip().lower() in candidates:
            return name
    return None


def encode_pluscode(lat: float, lon: float, length: int = 10) -> dict:
    """緯度経度を Plus Code にエンコードし、デコード情報も付与して返す。"""
    code = olc.encode(lat, lon, codeLength=length)
    area = olc.decode(code)
    return {
        "code": code,
        "length": length,
        "center": {"lat": area.latitudeCenter, "lon": area.longitudeCenter},
        "bbox": [area.longitudeLo, area.latitudeLo, area.longitudeHi, area.latitudeHi],
        "input": {"lat": lat, "lon": lon},
    }


def decode_pluscode(code: str) -> dict:
    """Plus Code をデコードし、中心座標と bbox を返す。"""
    if not olc.isValid(code):
        raise ValueError(f"無効な Plus Code です: '{code}'")
    if not olc.isFull(code):
        raise ValueError(f"フル形式の Plus Code が必要です（'+' を含む完全なコード）: '{code}'")
    area = olc.decode(code)
    return {
        "code": code,
        "center": {"lat": area.latitudeCenter, "lon": area.longitudeCenter},
        "bbox": [area.longitudeLo, area.latitudeLo, area.longitudeHi, area.latitudeHi],
    }


def boundary_geojson(code: str) -> dict:
    """Plus Code セルの境界を GeoJSON Polygon として返す。"""
    info = decode_pluscode(code)
    west, south, east, north = info["bbox"]
    return {
        "type": "Feature",
        "properties": {
            "code": code,
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


def _batch_process(
    input_path: str,
    output_path: str | None,
    operation: str,
    length: int,
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
                    info = encode_pluscode(lat, lon, length)
                    results.append({
                        "lat": lat,
                        "lon": lon,
                        "pluscode": info["code"],
                        "center_lat": info["center"]["lat"],
                        "center_lon": info["center"]["lon"],
                    })
                except (ValueError, KeyError) as e:
                    results.append({
                        "lat": row.get(lat_col, ""),
                        "lon": row.get(lon_col, ""),
                        "pluscode": None,
                        "error": str(e),
                    })

        elif operation == "decode":
            code_col = _detect_column(fieldnames, CODE_NAMES)
            if not code_col:
                _error(
                    f"CSV に Plus Code 列 {CODE_NAMES} が必要です。"
                    f"検出された列: {fieldnames}"
                )
            results = []
            for row in reader:
                try:
                    code = row[code_col].strip()
                    info = decode_pluscode(code)
                    results.append({
                        "pluscode": code,
                        "lat": info["center"]["lat"],
                        "lon": info["center"]["lon"],
                        "bbox_w": info["bbox"][0],
                        "bbox_s": info["bbox"][1],
                        "bbox_e": info["bbox"][2],
                        "bbox_n": info["bbox"][3],
                    })
                except (ValueError, KeyError) as e:
                    results.append({
                        "pluscode": row.get(code_col, ""),
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
            "results": results,
        }, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Plus Code (Open Location Code) 空間インデックス — エンコード・デコード・境界出力"
    )

    # 座標入力
    parser.add_argument("--lat", type=float, default=None, help="緯度 (WGS84)")
    parser.add_argument("--lon", type=float, default=None, help="経度 (WGS84)")
    parser.add_argument("--length", type=int, default=10, help="Plus Code 長さ（2〜15、デフォルト: 10）")

    # Plus Code 入力
    parser.add_argument("--code", type=str, default=None, help="Plus Code 文字列")

    # 操作フラグ
    parser.add_argument("--boundary", action="store_true", help="セル境界を GeoJSON Polygon で出力")

    # CSV バッチ
    parser.add_argument("--input", type=str, default=None, help="入力 CSV ファイルパス")
    parser.add_argument("--output", type=str, default=None, help="出力 CSV ファイルパス")
    parser.add_argument("--operation", type=str, default=None, help="バッチ操作（encode / decode）")

    args = parser.parse_args()

    try:
        # ---- バッチ CSV 処理 ----
        if args.input:
            if not args.operation:
                _error("--input を指定した場合は --operation (encode/decode) も必要です。")
            _batch_process(args.input, args.output, args.operation, args.length)
            return

        # ---- Plus Code 入力が必要な操作 ----
        if args.code:
            if args.boundary:
                result = boundary_geojson(args.code)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return

            # デフォルト: デコード
            result = decode_pluscode(args.code)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # ---- 緯度経度入力 → エンコード ----
        if args.lat is not None and args.lon is not None:
            if not (-90 <= args.lat <= 90):
                _error("緯度は -90 〜 90 の範囲で指定してください。")
            if not (-180 <= args.lon <= 180):
                _error("経度は -180 〜 180 の範囲で指定してください。")

            result = encode_pluscode(args.lat, args.lon, args.length)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # どの操作にもマッチしなかった場合
        _error(
            "引数が不足しています。--lat/--lon（エンコード）、--code（デコード）、"
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
