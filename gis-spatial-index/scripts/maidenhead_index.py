#!/usr/bin/env python3
"""Maidenhead グリッドロケーター変換スクリプト - 緯度経度 ↔ グリッドロケーターの相互変換・近傍取得・GeoJSON出力"""
from __future__ import annotations

import argparse
import csv
import json
import sys

# CSVカラム名の自動検出用（大文字小文字を区別しない）
LAT_NAMES = {"lat", "latitude", "y", "緯度"}
LON_NAMES = {"lon", "lng", "longitude", "x", "経度"}
LOCATOR_NAMES = {"locator", "maidenhead", "grid", "グリッドロケーター", "code"}

# 各レベルの経度・緯度方向のセルサイズ（度単位）
# Level 1: 20deg lon x 10deg lat, Level 2: 2deg x 1deg, ...
LEVEL_SIZES = [
    (20.0, 10.0),           # Level 1 (Field): 2 uppercase letters
    (2.0, 1.0),             # Level 2 (Square): 2 digits
    (5.0 / 60, 2.5 / 60),  # Level 3 (Subsquare): 2 lowercase letters
    (0.5 / 60, 0.25 / 60), # Level 4 (Extended Square): 2 digits
    (0.5 / 60 / 24, 0.25 / 60 / 24),  # Level 5 (Extended Subsquare): 2 lowercase letters
]

# 各レベルの分割数（経度・緯度とも同じ）
# 文字レベル(1,3,5)は18分割(A-R or a-x)、数字レベル(2,4)は10分割(0-9)
LEVEL_DIVISIONS = [18, 10, 24, 10, 24]


def encode(lat: float, lon: float, precision: int = 3) -> dict:
    """緯度経度からMaidenheadグリッドロケーターにエンコードする。

    precision: 1-5 でロケーター文字数 2,4,6,8,10 に対応。
    """
    if precision < 1 or precision > 5:
        raise ValueError(f"precision は 1〜5 で指定してください（指定値: {precision}）")
    if lat < -90 or lat > 90:
        raise ValueError("緯度は -90〜90 の範囲で指定してください。")
    if lon < -180 or lon > 180:
        raise ValueError("経度は -180〜180 の範囲で指定してください。")

    # 原点を南西端(-90, -180)にシフト
    adj_lon = lon + 180.0
    adj_lat = lat + 90.0

    # 境界値の処理: ちょうど上限に達した場合は直前のセルに収める
    if adj_lon >= 360.0:
        adj_lon = 360.0 - 1e-12
    if adj_lat >= 180.0:
        adj_lat = 180.0 - 1e-12

    locator = ""
    for level in range(precision):
        div = LEVEL_DIVISIONS[level]
        lon_size = LEVEL_SIZES[level][0]
        lat_size = LEVEL_SIZES[level][1]

        lon_idx = int(adj_lon / lon_size)
        lat_idx = int(adj_lat / lat_size)

        # インデックスの上限クランプ（浮動小数点誤差対策）
        lon_idx = min(lon_idx, div - 1)
        lat_idx = min(lat_idx, div - 1)

        if level in (0, 2, 4):
            # 文字レベル: Level 1 は大文字、Level 3,5 は小文字
            base = ord("A") if level == 0 else ord("a")
            locator += chr(base + lon_idx)
            locator += chr(base + lat_idx)
        else:
            # 数字レベル
            locator += str(lon_idx)
            locator += str(lat_idx)

        adj_lon -= lon_idx * lon_size
        adj_lat -= lat_idx * lat_size

    # セルのサイズ・バウンディングボックス・中心を計算
    cell_lon_size = LEVEL_SIZES[precision - 1][0]
    cell_lat_size = LEVEL_SIZES[precision - 1][1]
    sw = _decode_sw(locator)

    return {
        "locator": locator,
        "precision": precision,
        "center": {
            "lat": round(sw["lat"] + cell_lat_size / 2, 6),
            "lon": round(sw["lon"] + cell_lon_size / 2, 6),
        },
        "bbox": [
            round(sw["lon"], 6),
            round(sw["lat"], 6),
            round(sw["lon"] + cell_lon_size, 6),
            round(sw["lat"] + cell_lat_size, 6),
        ],
        "size": {
            "lon_degrees": round(cell_lon_size, 5),
            "lat_degrees": round(cell_lat_size, 5),
        },
        "input": {"lat": lat, "lon": lon},
    }


def _decode_sw(locator: str) -> dict:
    """ロケーター文字列から南西角の緯度経度を返す（内部用）。"""
    locator = locator.strip()
    length = len(locator)

    if length < 2 or length % 2 != 0 or length > 10:
        raise ValueError(
            f"ロケーターは 2,4,6,8,10 文字のいずれかです（入力: {length}文字 '{locator}'）"
        )

    precision = length // 2
    sw_lon = -180.0
    sw_lat = -90.0

    for level in range(precision):
        c_lon = locator[level * 2]
        c_lat = locator[level * 2 + 1]
        lon_size = LEVEL_SIZES[level][0]
        lat_size = LEVEL_SIZES[level][1]

        if level in (0, 2, 4):
            # 文字レベル
            base = "A" if level == 0 else "a"
            lon_idx = ord(c_lon.upper() if level == 0 else c_lon.lower()) - ord(base)
            lat_idx = ord(c_lat.upper() if level == 0 else c_lat.lower()) - ord(base)
            max_idx = LEVEL_DIVISIONS[level] - 1
            if lon_idx < 0 or lon_idx > max_idx or lat_idx < 0 or lat_idx > max_idx:
                valid_range = f"{base}-{chr(ord(base) + max_idx)}"
                raise ValueError(
                    f"レベル{level + 1}の文字が範囲外です: '{c_lon}{c_lat}'（有効範囲: {valid_range}）"
                )
        else:
            # 数字レベル
            if not c_lon.isdigit() or not c_lat.isdigit():
                raise ValueError(
                    f"レベル{level + 1}は数字(0-9)が必要です: '{c_lon}{c_lat}'"
                )
            lon_idx = int(c_lon)
            lat_idx = int(c_lat)

        sw_lon += lon_idx * lon_size
        sw_lat += lat_idx * lat_size

    return {"lat": sw_lat, "lon": sw_lon}


def decode(locator: str) -> dict:
    """Maidenheadグリッドロケーターをデコードして中心座標・バウンディングボックスを返す。"""
    locator = locator.strip()
    precision = len(locator) // 2

    sw = _decode_sw(locator)
    cell_lon_size = LEVEL_SIZES[precision - 1][0]
    cell_lat_size = LEVEL_SIZES[precision - 1][1]

    return {
        "locator": locator,
        "precision": precision,
        "center": {
            "lat": round(sw["lat"] + cell_lat_size / 2, 6),
            "lon": round(sw["lon"] + cell_lon_size / 2, 6),
        },
        "bbox": [
            round(sw["lon"], 6),
            round(sw["lat"], 6),
            round(sw["lon"] + cell_lon_size, 6),
            round(sw["lat"] + cell_lat_size, 6),
        ],
        "size": {
            "lon_degrees": round(cell_lon_size, 5),
            "lat_degrees": round(cell_lat_size, 5),
        },
    }


def _shift_locator(locator: str, dlon: int, dlat: int) -> str | None:
    """ロケーターを経度方向に dlon、緯度方向に dlat セル分シフトする。

    経度は循環（wrap-around）、緯度は範囲外で None を返す。
    """
    locator = locator.strip()
    precision = len(locator) // 2

    # 各レベルのインデックスを抽出
    lon_indices = []
    lat_indices = []
    for level in range(precision):
        c_lon = locator[level * 2]
        c_lat = locator[level * 2 + 1]
        if level in (0, 2, 4):
            base = ord("A") if level == 0 else ord("a")
            lon_indices.append(ord(c_lon.upper() if level == 0 else c_lon.lower()) - base)
            lat_indices.append(ord(c_lat.upper() if level == 0 else c_lat.lower()) - base)
        else:
            lon_indices.append(int(c_lon))
            lat_indices.append(int(c_lat))

    # 最下位レベルにオフセットを加算し、上位へ繰り上げ（繰り下げ）する
    lon_indices[-1] += dlon
    lat_indices[-1] += dlat

    for i in range(precision - 1, 0, -1):
        div = LEVEL_DIVISIONS[i]
        # 経度: 繰り上げ/繰り下げを上位レベルに伝播
        while lon_indices[i] < 0:
            lon_indices[i] += div
            lon_indices[i - 1] -= 1
        while lon_indices[i] >= div:
            lon_indices[i] -= div
            lon_indices[i - 1] += 1
        # 緯度: 同様
        while lat_indices[i] < 0:
            lat_indices[i] += div
            lat_indices[i - 1] -= 1
        while lat_indices[i] >= div:
            lat_indices[i] -= div
            lat_indices[i - 1] += 1

    # 最上位レベル(Field)の処理
    field_div = LEVEL_DIVISIONS[0]  # 18

    # 経度はwrap-around（地球を一周する）
    lon_indices[0] = lon_indices[0] % field_div

    # 緯度は範囲外なら None（極を超えるセルは存在しない）
    if lat_indices[0] < 0 or lat_indices[0] >= field_div:
        return None

    # インデックスからロケーター文字列を再構成
    result = ""
    for level in range(precision):
        if level in (0, 2, 4):
            base = ord("A") if level == 0 else ord("a")
            result += chr(base + lon_indices[level])
            result += chr(base + lat_indices[level])
        else:
            result += str(lon_indices[level])
            result += str(lat_indices[level])

    return result


def neighbors(locator: str) -> dict:
    """8方向の隣接グリッドロケーターを返す。"""
    # (dlon, dlat) の8方向定義
    directions = {
        "n":  (0, 1),
        "ne": (1, 1),
        "e":  (1, 0),
        "se": (1, -1),
        "s":  (0, -1),
        "sw": (-1, -1),
        "w":  (-1, 0),
        "nw": (-1, 1),
    }

    result = {}
    for name, (dlon, dlat) in directions.items():
        shifted = _shift_locator(locator, dlon, dlat)
        result[name] = shifted  # None if out of range (polar)

    return {
        "locator": locator.strip(),
        "neighbors": result,
    }


def boundary_geojson(locator: str) -> dict:
    """グリッドセルのGeoJSON Polygonを返す（RFC 7946準拠: WGS84）。"""
    info = decode(locator)
    west, south, east, north = info["bbox"]

    return {
        "type": "Feature",
        "properties": {
            "locator": info["locator"],
            "precision": info["precision"],
            "center_lat": info["center"]["lat"],
            "center_lon": info["center"]["lon"],
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


def _find_column(fieldnames: list[str], candidates: set[str]) -> str | None:
    """CSVヘッダーから候補名に一致するカラムを探す（大文字小文字を区別しない）。"""
    for name in fieldnames:
        if name.strip().lower() in candidates:
            return name
    return None


def _batch_encode(input_path: str, output_path: str | None, precision: int) -> None:
    """CSV一括エンコード: 緯度経度列 → ロケーター"""
    with open(input_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        lat_col = _find_column(fieldnames, LAT_NAMES)
        lon_col = _find_column(fieldnames, LON_NAMES)

        if not lat_col or not lon_col:
            print(
                json.dumps(
                    {"error": f"CSVに緯度・経度列が見つかりません。対応カラム名: {LAT_NAMES}, {LON_NAMES}"},
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            sys.exit(1)

        results = []
        errors = 0
        for row in reader:
            try:
                lat = float(row[lat_col])
                lon = float(row[lon_col])
                enc = encode(lat, lon, precision)
                results.append({
                    "lat": lat,
                    "lon": lon,
                    "locator": enc["locator"],
                    "center_lat": enc["center"]["lat"],
                    "center_lon": enc["center"]["lon"],
                })
            except (ValueError, KeyError) as e:
                results.append({
                    "lat": row.get(lat_col),
                    "lon": row.get(lon_col),
                    "locator": None,
                    "center_lat": None,
                    "center_lon": None,
                    "error": str(e),
                })
                errors += 1

    if output_path:
        out_fields = ["lat", "lon", "locator", "center_lat", "center_lon"]
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)
        print(json.dumps({
            "status": "success",
            "operation": "encode",
            "output_file": output_path,
            "count": len(results),
            "errors": errors,
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({
            "status": "success",
            "operation": "encode",
            "results": results,
            "count": len(results),
            "errors": errors,
        }, ensure_ascii=False, indent=2))


def _batch_decode(input_path: str, output_path: str | None) -> None:
    """CSV一括デコード: ロケーター列 → 緯度経度"""
    with open(input_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        loc_col = _find_column(fieldnames, LOCATOR_NAMES)

        if not loc_col:
            print(
                json.dumps(
                    {"error": f"CSVにロケーター列が見つかりません。対応カラム名: {LOCATOR_NAMES}"},
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            sys.exit(1)

        results = []
        errors = 0
        for row in reader:
            try:
                loc = row[loc_col].strip()
                if not loc:
                    raise ValueError("ロケーターが空です")
                dec = decode(loc)
                results.append({
                    "locator": loc,
                    "center_lat": dec["center"]["lat"],
                    "center_lon": dec["center"]["lon"],
                    "bbox_west": dec["bbox"][0],
                    "bbox_south": dec["bbox"][1],
                    "bbox_east": dec["bbox"][2],
                    "bbox_north": dec["bbox"][3],
                })
            except (ValueError, KeyError) as e:
                results.append({
                    "locator": row.get(loc_col),
                    "center_lat": None,
                    "center_lon": None,
                    "bbox_west": None,
                    "bbox_south": None,
                    "bbox_east": None,
                    "bbox_north": None,
                    "error": str(e),
                })
                errors += 1

    if output_path:
        out_fields = ["locator", "center_lat", "center_lon",
                      "bbox_west", "bbox_south", "bbox_east", "bbox_north"]
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)
        print(json.dumps({
            "status": "success",
            "operation": "decode",
            "output_file": output_path,
            "count": len(results),
            "errors": errors,
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({
            "status": "success",
            "operation": "decode",
            "results": results,
            "count": len(results),
            "errors": errors,
        }, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Maidenhead グリッドロケーター ↔ 緯度経度の相互変換・近傍取得・GeoJSON出力"
    )

    # 単体操作用
    parser.add_argument("--lat", type=float, default=None, help="緯度 (WGS84)")
    parser.add_argument("--lon", type=float, default=None, help="経度 (WGS84)")
    parser.add_argument(
        "--precision", type=int, default=3,
        help="ロケーター精度 1-5 → 2,4,6,8,10文字（デフォルト: 3 → 6文字）"
    )
    parser.add_argument("--locator", type=str, default=None, help="グリッドロケーター（例: PM95qk）")
    parser.add_argument("--neighbors", action="store_true", help="8方向の隣接グリッドを取得")
    parser.add_argument("--boundary", action="store_true", help="GeoJSON Polygon を出力")

    # バッチ処理用
    parser.add_argument("--input", type=str, default=None, help="入力CSVファイルパス")
    parser.add_argument("--output", type=str, default=None, help="出力CSVファイルパス（省略時はJSON標準出力）")
    parser.add_argument(
        "--operation", type=str, choices=["encode", "decode"], default=None,
        help="バッチ操作: encode（緯度経度→ロケーター）/ decode（ロケーター→緯度経度）"
    )

    args = parser.parse_args()

    has_latlon = args.lat is not None and args.lon is not None
    has_locator = args.locator is not None
    has_batch = args.input is not None

    # バッチモード
    if has_batch:
        if not args.operation:
            print(
                json.dumps(
                    {"error": "--input 使用時は --operation (encode/decode) を指定してください。"},
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            if args.operation == "encode":
                _batch_encode(args.input, args.output, args.precision)
            else:
                _batch_decode(args.input, args.output)
        except FileNotFoundError:
            print(
                json.dumps({"error": f"ファイルが見つかりません: {args.input}"}, ensure_ascii=False),
                file=sys.stderr,
            )
            sys.exit(1)
        except Exception as e:
            print(
                json.dumps({"error": f"バッチ処理中にエラーが発生しました: {e}"}, ensure_ascii=False),
                file=sys.stderr,
            )
            sys.exit(1)
        return

    # 単体モード: 引数の排他チェック
    if has_latlon and has_locator:
        print(
            json.dumps(
                {"error": "--lat/--lon と --locator は同時に指定できません。"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    if not has_latlon and not has_locator:
        print(
            json.dumps(
                {"error": "--lat/--lon または --locator を指定してください。"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        if has_latlon:
            # エンコード
            result = encode(args.lat, args.lon, args.precision)
            print(json.dumps(result, ensure_ascii=False, indent=2))

        elif has_locator:
            if args.neighbors:
                # 近傍取得
                result = neighbors(args.locator)
                print(json.dumps(result, ensure_ascii=False, indent=2))
            elif args.boundary:
                # GeoJSON出力
                result = boundary_geojson(args.locator)
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                # デコード
                result = decode(args.locator)
                print(json.dumps(result, ensure_ascii=False, indent=2))

    except ValueError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(
            json.dumps({"error": f"変換中にエラーが発生しました: {e}"}, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
