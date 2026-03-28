#!/usr/bin/env python3
"""空間ID (Spatial ID / ZFXY) 変換スクリプト - 緯度経度+標高 ↔ 3Dボクセル空間IDの相互変換"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys

# Web Mercator の緯度限界
MAX_LATITUDE = 85.05112878

# 仕様上の鉛直方向の総範囲 (メートル)
ALTITUDE_RANGE = 2 ** 25  # 33,554,432 m

# 地球の赤道周長 (メートル)
EARTH_CIRCUMFERENCE = 40_075_016.686


# ---------------------------------------------------------------------------
# タイル座標ヘルパー（水平方向は XYZ タイルと同一）
# ---------------------------------------------------------------------------

def _latlon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """WGS84 → XYZ tile coordinates (Slippy Map Tilenames)"""
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    x = max(0, min(n - 1, x))
    y = max(0, min(n - 1, y))
    return x, y


def _tile_to_bbox(x: int, y: int, zoom: int) -> dict:
    """XYZ tile → bounding box (west, south, east, north)"""
    n = 2 ** zoom
    west = x / n * 360.0 - 180.0
    east = (x + 1) / n * 360.0 - 180.0
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return {"west": west, "south": south, "east": east, "north": north}


def _tile_center(x: int, y: int, zoom: int) -> dict:
    """タイルの中心座標を返す"""
    bbox = _tile_to_bbox(x, y, zoom)
    return {
        "lat": (bbox["north"] + bbox["south"]) / 2.0,
        "lon": (bbox["west"] + bbox["east"]) / 2.0,
    }


# ---------------------------------------------------------------------------
# フロア（高度）ヘルパー
# ---------------------------------------------------------------------------

def _altitude_to_floor(altitude: float, zoom: int) -> int:
    """標高 (m) → フロアインデックス f

    f = floor(altitude * 2^z / 2^25)
    海面(0m)は f=0、地下(負の標高)は負の f を返す。
    """
    return math.floor(altitude * (2 ** zoom) / ALTITUDE_RANGE)


def _floor_to_altitude_range(f: int, zoom: int) -> tuple[float, float]:
    """フロアインデックス → ボクセルの鉛直範囲 (alt_min, alt_max)"""
    voxel_height = ALTITUDE_RANGE / (2 ** zoom)
    alt_min = f * voxel_height
    alt_max = (f + 1) * voxel_height
    return alt_min, alt_max


def _floor_center_altitude(f: int, zoom: int) -> float:
    """フロアインデックス → ボクセル中心の標高"""
    alt_min, alt_max = _floor_to_altitude_range(f, zoom)
    return (alt_min + alt_max) / 2.0


# ---------------------------------------------------------------------------
# ZFXY パーサー / フォーマッター
# ---------------------------------------------------------------------------

def parse_zfxy(zfxy_str: str) -> tuple[int, int, int, int]:
    """ZFXY 文字列 "z/f/x/y" をパースして (z, f, x, y) を返す

    f は負値可（地下ボクセル）。
    """
    parts = zfxy_str.strip().strip("/").split("/")
    if len(parts) != 4:
        raise ValueError(
            f"ZFXY は 'z/f/x/y' の4要素が必要です（入力: '{zfxy_str}'）"
        )
    try:
        z, f, x, y = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
    except ValueError:
        raise ValueError(
            f"ZFXY の各要素は整数でなければなりません（入力: '{zfxy_str}'）"
        )

    if z < 0 or z > 25:
        raise ValueError(f"ズームレベルは 0〜25 の範囲です（入力: z={z}）")
    n = 2 ** z
    if x < 0 or x >= n:
        raise ValueError(f"x は 0〜{n - 1} の範囲です（入力: x={x}）")
    if y < 0 or y >= n:
        raise ValueError(f"y は 0〜{n - 1} の範囲です（入力: y={y}）")

    return z, f, x, y


def format_zfxy(z: int, f: int, x: int, y: int) -> str:
    """(z, f, x, y) → ZFXY 文字列"""
    return f"{z}/{f}/{x}/{y}"


# ---------------------------------------------------------------------------
# コア操作
# ---------------------------------------------------------------------------

def encode(lat: float, lon: float, altitude: float, zoom: int) -> dict:
    """緯度経度 + 標高 → 空間ID (ZFXY) エンコード"""
    lat_clamped = max(-MAX_LATITUDE, min(MAX_LATITUDE, lat))
    x, y = _latlon_to_tile(lat_clamped, lon, zoom)
    f = _altitude_to_floor(altitude, zoom)
    zfxy = format_zfxy(zoom, f, x, y)
    center = _tile_center(x, y, zoom)
    bbox = _tile_to_bbox(x, y, zoom)
    alt_min, alt_max = _floor_to_altitude_range(f, zoom)
    center_alt = _floor_center_altitude(f, zoom)

    return {
        "zfxy": zfxy,
        "zoom": zoom,
        "tile": {"x": x, "y": y, "f": f},
        "center": {"lat": center["lat"], "lon": center["lon"], "altitude": center_alt},
        "bbox_2d": [bbox["west"], bbox["south"], bbox["east"], bbox["north"]],
        "altitude_range": {"min": alt_min, "max": alt_max},
        "input": {"lat": lat, "lon": lon, "altitude": altitude},
    }


def decode(zfxy_str: str) -> dict:
    """空間ID (ZFXY) → 中心座標・3Dバウンディングボックスにデコード"""
    z, f, x, y = parse_zfxy(zfxy_str)
    center = _tile_center(x, y, z)
    bbox = _tile_to_bbox(x, y, z)
    alt_min, alt_max = _floor_to_altitude_range(f, z)
    center_alt = _floor_center_altitude(f, z)

    # ボクセルサイズの計算
    horizontal_m = EARTH_CIRCUMFERENCE / (2 ** z)
    vertical_m = ALTITUDE_RANGE / (2 ** z)

    return {
        "zfxy": format_zfxy(z, f, x, y),
        "zoom": z,
        "tile": {"x": x, "y": y, "f": f},
        "center": {"lat": center["lat"], "lon": center["lon"], "altitude": center_alt},
        "bbox_2d": [bbox["west"], bbox["south"], bbox["east"], bbox["north"]],
        "altitude_range": {"min": alt_min, "max": alt_max},
        "voxel_size": {
            "horizontal_m": round(horizontal_m, 3),
            "vertical_m": round(vertical_m, 3),
        },
    }


def get_neighbors(zfxy_str: str) -> dict:
    """6方向の隣接ボクセル（面共有）を返す

    east/west: x 方向でラップアラウンド
    north/south: y 方向でクランプ（範囲外は None）
    up/down: f 方向（制限なし）
    """
    z, f, x, y = parse_zfxy(zfxy_str)
    n = 2 ** z

    neighbors = {}

    # 東西: x ラップアラウンド
    neighbors["east"] = format_zfxy(z, f, (x + 1) % n, y)
    neighbors["west"] = format_zfxy(z, f, (x - 1) % n, y)

    # 南北: y クランプ
    if y > 0:
        neighbors["north"] = format_zfxy(z, f, x, y - 1)
    else:
        neighbors["north"] = None
    if y < n - 1:
        neighbors["south"] = format_zfxy(z, f, x, y + 1)
    else:
        neighbors["south"] = None

    # 上下: f は制限なし
    neighbors["up"] = format_zfxy(z, f + 1, x, y)
    neighbors["down"] = format_zfxy(z, f - 1, x, y)

    return {
        "zfxy": format_zfxy(z, f, x, y),
        "zoom": z,
        "neighbors": neighbors,
    }


def get_parent(zfxy_str: str) -> dict:
    """親ボクセル（オクツリー: z-1）を返す

    parent = (z-1, f//2, x//2, y//2)
    Python の // は負の f でも正しくフロア除算する。
    """
    z, f, x, y = parse_zfxy(zfxy_str)
    if z == 0:
        raise ValueError("ズームレベル 0 の空間ID に親はありません。")

    pz = z - 1
    pf = f // 2
    px = x // 2
    py = y // 2
    parent_zfxy = format_zfxy(pz, pf, px, py)

    return {
        "zfxy": format_zfxy(z, f, x, y),
        "parent": parent_zfxy,
        "parent_zoom": pz,
        "parent_tile": {"x": px, "y": py, "f": pf},
    }


def get_children(zfxy_str: str) -> dict:
    """子ボクセル8つ（オクツリー: z+1）を返す

    各軸を2分割: (2x+dx, 2y+dy, 2f+df) for dx, dy, df in {0, 1}
    """
    z, f, x, y = parse_zfxy(zfxy_str)
    if z >= 25:
        raise ValueError("ズームレベル 25 の空間ID にはこれ以上の子はありません。")

    cz = z + 1
    children = []
    for df in (0, 1):
        for dy in (0, 1):
            for dx in (0, 1):
                children.append(format_zfxy(cz, 2 * f + df, 2 * x + dx, 2 * y + dy))

    return {
        "zfxy": format_zfxy(z, f, x, y),
        "children_zoom": cz,
        "children": children,
    }


def to_geojson(zfxy_str: str) -> dict:
    """空間ID → GeoJSON Feature（2D境界ポリゴン + 高度プロパティ）"""
    z, f, x, y = parse_zfxy(zfxy_str)
    bbox = _tile_to_bbox(x, y, z)
    w, s, e, n = bbox["west"], bbox["south"], bbox["east"], bbox["north"]
    alt_min, alt_max = _floor_to_altitude_range(f, z)

    return {
        "type": "Feature",
        "properties": {
            "zfxy": format_zfxy(z, f, x, y),
            "zoom": z,
            "tile_x": x,
            "tile_y": y,
            "floor": f,
            "altitude_min": alt_min,
            "altitude_max": alt_max,
            "altitude_center": _floor_center_altitude(f, z),
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [w, s],
                [e, s],
                [e, n],
                [w, n],
                [w, s],
            ]],
        },
    }


def zoom_table() -> dict:
    """ズームレベル別の水平・垂直解像度テーブル"""
    rows = []
    for z in range(26):
        n = 2 ** z
        horizontal_m = EARTH_CIRCUMFERENCE / n
        vertical_m = ALTITUDE_RANGE / n
        rows.append({
            "zoom": z,
            "horizontal_m": round(horizontal_m, 3),
            "vertical_m": round(vertical_m, 3),
            "tiles_per_axis": n,
        })
    return {"zoom_table": rows}


# ---------------------------------------------------------------------------
# CSV バッチ処理
# ---------------------------------------------------------------------------

LAT_NAMES = {"lat", "latitude", "y", "緯度"}
LON_NAMES = {"lon", "lng", "longitude", "x", "経度"}
ALT_NAMES = {"alt", "altitude", "elevation", "height", "z", "標高", "高度"}
ZFXY_NAMES = {"zfxy", "spatial_id", "空間id", "code"}


def _detect_column(fieldnames: list[str], candidates: set[str]) -> str | None:
    """CSV ヘッダーから候補名に一致するカラムを探す（大文字小文字無視）"""
    lower_map = {f.lower().strip(): f for f in fieldnames}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return None


def _batch_encode(input_path: str, output_path: str | None, zoom: int) -> None:
    """CSV 一括エンコード: 緯度経度+標高列 → 空間ID"""
    results = []
    with open(input_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        lat_col = _detect_column(fieldnames, LAT_NAMES)
        lon_col = _detect_column(fieldnames, LON_NAMES)
        alt_col = _detect_column(fieldnames, ALT_NAMES)
        if lat_col is None or lon_col is None:
            _error(f"CSV に緯度・経度列が見つかりません。検出可能な列名: {LAT_NAMES}, {LON_NAMES}")

        for row in reader:
            try:
                lat = float(row[lat_col])
                lon = float(row[lon_col])
                altitude = float(row[alt_col]) if alt_col and row.get(alt_col) else 0.0
                enc = encode(lat, lon, altitude, zoom)
                results.append({
                    "lat": lat,
                    "lon": lon,
                    "altitude": altitude,
                    "zfxy": enc["zfxy"],
                    "zoom": zoom,
                    "tile_x": enc["tile"]["x"],
                    "tile_y": enc["tile"]["y"],
                    "floor": enc["tile"]["f"],
                })
            except (ValueError, KeyError) as e:
                results.append({
                    "lat": row.get(lat_col, ""),
                    "lon": row.get(lon_col, ""),
                    "altitude": row.get(alt_col, "") if alt_col else "",
                    "zfxy": None,
                    "zoom": zoom,
                    "tile_x": None,
                    "tile_y": None,
                    "floor": None,
                    "error": str(e),
                })

    if output_path:
        out_fields = ["lat", "lon", "altitude", "zfxy", "zoom", "tile_x", "tile_y", "floor"]
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)
        print(json.dumps({
            "status": "success",
            "output_file": output_path,
            "count": len(results),
            "failed": sum(1 for r in results if r["zfxy"] is None),
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": "success", "results": results}, ensure_ascii=False, indent=2))


def _batch_decode(input_path: str, output_path: str | None) -> None:
    """CSV 一括デコード: 空間ID列 → 緯度経度・標高"""
    results = []
    with open(input_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        zfxy_col = _detect_column(fieldnames, ZFXY_NAMES)
        if zfxy_col is None:
            _error(f"CSV に空間ID列が見つかりません。検出可能な列名: {ZFXY_NAMES}")

        for row in reader:
            try:
                zfxy_str = row[zfxy_col].strip()
                dec = decode(zfxy_str)
                results.append({
                    "zfxy": zfxy_str,
                    "zoom": dec["zoom"],
                    "tile_x": dec["tile"]["x"],
                    "tile_y": dec["tile"]["y"],
                    "floor": dec["tile"]["f"],
                    "center_lat": dec["center"]["lat"],
                    "center_lon": dec["center"]["lon"],
                    "center_alt": dec["center"]["altitude"],
                    "alt_min": dec["altitude_range"]["min"],
                    "alt_max": dec["altitude_range"]["max"],
                })
            except (ValueError, KeyError) as e:
                results.append({
                    "zfxy": row.get(zfxy_col, ""),
                    "zoom": None,
                    "tile_x": None,
                    "tile_y": None,
                    "floor": None,
                    "center_lat": None,
                    "center_lon": None,
                    "center_alt": None,
                    "alt_min": None,
                    "alt_max": None,
                    "error": str(e),
                })

    if output_path:
        out_fields = [
            "zfxy", "zoom", "tile_x", "tile_y", "floor",
            "center_lat", "center_lon", "center_alt", "alt_min", "alt_max",
        ]
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)
        print(json.dumps({
            "status": "success",
            "output_file": output_path,
            "count": len(results),
            "failed": sum(1 for r in results if r["zoom"] is None),
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": "success", "results": results}, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# エラー出力ヘルパー
# ---------------------------------------------------------------------------

def _error(msg: str) -> None:
    """JSON エラーを stderr に出力して終了"""
    print(json.dumps({"error": msg}, ensure_ascii=False), file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="空間ID (Spatial ID / ZFXY) の変換・探索ツール"
    )

    # エンコード: 緯度経度 + 標高
    parser.add_argument("--lat", type=float, default=None, help="緯度 (WGS84)")
    parser.add_argument("--lon", type=float, default=None, help="経度 (WGS84)")
    parser.add_argument("--altitude", type=float, default=0.0,
                        help="標高 (メートル, 海面=0, デフォルト: 0.0)")
    parser.add_argument("--zoom", type=int, default=None, help="ズームレベル (0〜25)")

    # デコード / 操作
    parser.add_argument("--zfxy", type=str, default=None,
                        help="空間ID 文字列 (z/f/x/y, 例: 20/1/931277/412899)")
    parser.add_argument("--neighbors", action="store_true",
                        help="6方向の隣接ボクセルを取得 (東西南北上下)")
    parser.add_argument("--parent", action="store_true",
                        help="親ボクセル (z-1) を取得")
    parser.add_argument("--children", action="store_true",
                        help="子ボクセル 8つ (z+1) を取得")
    parser.add_argument("--boundary", action="store_true",
                        help="GeoJSON Feature を出力 (2D境界 + 高度プロパティ)")

    # 解像度テーブル
    parser.add_argument("--zoom-table", action="store_true",
                        help="ズームレベル別の解像度テーブルを出力")

    # CSV バッチ
    parser.add_argument("--input", type=str, default=None,
                        help="入力 CSV ファイルパス")
    parser.add_argument("--output", type=str, default=None,
                        help="出力 CSV ファイルパス")
    parser.add_argument("--operation", choices=["encode", "decode"], default=None,
                        help="バッチ操作 (encode: 緯度経度→空間ID, decode: 空間ID→緯度経度)")

    args = parser.parse_args()

    # --- バッチモード ---
    if args.input:
        if not args.operation:
            _error("--input 使用時は --operation (encode/decode) を指定してください。")
        if args.operation == "encode":
            if args.zoom is None:
                _error("encode 操作には --zoom が必要です。")
            _batch_encode(args.input, args.output, args.zoom)
            return
        else:
            _batch_decode(args.input, args.output)
            return

    # --- 解像度テーブル ---
    if args.zoom_table:
        print(json.dumps(zoom_table(), ensure_ascii=False, indent=2))
        return

    # --- 単一操作モード ---
    try:
        has_latlon = args.lat is not None and args.lon is not None
        has_zfxy = args.zfxy is not None

        # ZFXY を指定した操作
        if has_zfxy:
            zfxy_str = args.zfxy.strip()
            if not zfxy_str:
                _error("空間ID が空です。")

            if args.neighbors:
                result = get_neighbors(zfxy_str)
            elif args.parent:
                result = get_parent(zfxy_str)
            elif args.children:
                result = get_children(zfxy_str)
            elif args.boundary:
                result = to_geojson(zfxy_str)
            else:
                result = decode(zfxy_str)

        # 緯度経度からエンコード
        elif has_latlon:
            if args.zoom is None:
                _error("--lat/--lon 指定時は --zoom も必要です。")
            if args.zoom < 0 or args.zoom > 25:
                _error("ズームレベルは 0〜25 の範囲で指定してください。")
            if not (-90 <= args.lat <= 90):
                _error("緯度は -90〜90 の範囲で指定してください。")
            if not (-180 <= args.lon <= 180):
                _error("経度は -180〜180 の範囲で指定してください。")
            result = encode(args.lat, args.lon, args.altitude, args.zoom)

        else:
            _error(
                "--lat/--lon/--zoom、--zfxy、--zoom-table、"
                "または --input のいずれかを指定してください。"
            )

        print(json.dumps(result, ensure_ascii=False, indent=2))

    except ValueError as e:
        _error(str(e))
    except Exception as e:
        _error(f"処理中にエラーが発生しました: {e}")


if __name__ == "__main__":
    main()
