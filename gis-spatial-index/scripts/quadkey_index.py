#!/usr/bin/env python3
"""Quadkey 空間インデックス変換スクリプト - 緯度経度 ↔ Quadkey の相互変換・近傍探索"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys

# Web Mercator の緯度限界（これを超えるとタイル座標が破綻する）
MAX_LATITUDE = 85.05112878


# ---------------------------------------------------------------------------
# タイル座標ヘルパー（tile_coords.py と最小限の重複）
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
# Quadkey 変換コア
# ---------------------------------------------------------------------------

def tile_to_quadkey(x: int, y: int, zoom: int) -> str:
    """XYZ tile → Quadkey string

    各ズームレベルのビット位置で x, y の象限(0-3)を決定し文字列化する。
    """
    quadkey = []
    for i in range(zoom, 0, -1):
        digit = 0
        mask = 1 << (i - 1)
        if (x & mask) != 0:
            digit += 1
        if (y & mask) != 0:
            digit += 2
        quadkey.append(str(digit))
    return "".join(quadkey)


def quadkey_to_tile(quadkey: str) -> tuple[int, int, int]:
    """Quadkey → (x, y, zoom)

    Quadkey 文字列の各桁をビット演算でタイル座標に復元する。
    """
    x = y = 0
    zoom = len(quadkey)
    for i, ch in enumerate(quadkey):
        mask = 1 << (zoom - 1 - i)
        if ch not in ("0", "1", "2", "3"):
            raise ValueError(f"Quadkey に無効な文字 '{ch}' が含まれています")
        digit = int(ch)
        if digit & 1:
            x |= mask
        if digit & 2:
            y |= mask
    return x, y, zoom


# ---------------------------------------------------------------------------
# 高レベル操作
# ---------------------------------------------------------------------------

def encode_from_latlon(lat: float, lon: float, zoom: int) -> dict:
    """緯度経度 → Quadkey エンコード"""
    lat = max(-MAX_LATITUDE, min(MAX_LATITUDE, lat))
    x, y = _latlon_to_tile(lat, lon, zoom)
    qk = tile_to_quadkey(x, y, zoom)
    center = _tile_center(x, y, zoom)
    bbox = _tile_to_bbox(x, y, zoom)
    return {
        "quadkey": qk,
        "zoom": zoom,
        "tile": {"x": x, "y": y},
        "center": center,
        "bbox": [bbox["west"], bbox["south"], bbox["east"], bbox["north"]],
        "input": {"lat": lat, "lon": lon},
    }


def encode_from_tile(x: int, y: int, zoom: int) -> dict:
    """タイル座標 → Quadkey エンコード"""
    n = 2 ** zoom
    if not (0 <= x < n) or not (0 <= y < n):
        raise ValueError(f"ズームレベル {zoom} でのタイル座標は 0〜{n - 1} の範囲です。")
    qk = tile_to_quadkey(x, y, zoom)
    center = _tile_center(x, y, zoom)
    bbox = _tile_to_bbox(x, y, zoom)
    return {
        "quadkey": qk,
        "zoom": zoom,
        "tile": {"x": x, "y": y},
        "center": center,
        "bbox": [bbox["west"], bbox["south"], bbox["east"], bbox["north"]],
    }


def decode_quadkey(quadkey: str) -> dict:
    """Quadkey → タイル座標・中心座標・バウンディングボックスにデコード"""
    x, y, zoom = quadkey_to_tile(quadkey)
    center = _tile_center(x, y, zoom)
    bbox = _tile_to_bbox(x, y, zoom)
    return {
        "quadkey": quadkey,
        "zoom": zoom,
        "tile": {"x": x, "y": y},
        "center": center,
        "bbox": [bbox["west"], bbox["south"], bbox["east"], bbox["north"]],
    }


def get_neighbors(quadkey: str) -> dict:
    """Quadkey の8方向の隣接タイルを返す

    x は経度方向でラップアラウンド(modulo)、y は緯度方向でクランプする。
    """
    x, y, zoom = quadkey_to_tile(quadkey)
    n = 2 ** zoom

    directions = {
        "n":  (0, -1),
        "ne": (1, -1),
        "e":  (1,  0),
        "se": (1,  1),
        "s":  (0,  1),
        "sw": (-1, 1),
        "w":  (-1, 0),
        "nw": (-1, -1),
    }

    neighbors = {}
    for name, (dx, dy) in directions.items():
        nx = (x + dx) % n  # 経度方向はラップアラウンド
        ny = y + dy
        if ny < 0 or ny >= n:
            # 緯度方向は極を超えると隣接タイルが存在しない
            neighbors[name] = None
        else:
            neighbors[name] = tile_to_quadkey(nx, ny, zoom)

    return {
        "quadkey": quadkey,
        "zoom": zoom,
        "neighbors": neighbors,
    }


def get_parent(quadkey: str) -> dict:
    """Quadkey の親タイル（1レベル上）を返す"""
    if len(quadkey) == 0:
        raise ValueError("ズームレベル 0 の Quadkey に親はありません。")
    # 親 Quadkey は末尾1文字を削除するだけ
    parent_qk = quadkey[:-1]
    result = {"quadkey": quadkey, "parent": parent_qk, "parent_zoom": len(parent_qk)}
    if parent_qk:
        px, py, pz = quadkey_to_tile(parent_qk)
        result["parent_tile"] = {"x": px, "y": py}
    else:
        result["parent_tile"] = {"x": 0, "y": 0}
    return result


def get_children(quadkey: str) -> dict:
    """Quadkey の子タイル4つ（1レベル下）を返す"""
    children = [quadkey + d for d in ("0", "1", "2", "3")]
    return {
        "quadkey": quadkey,
        "children_zoom": len(quadkey) + 1,
        "children": children,
    }


def quadkey_to_geojson(quadkey: str) -> dict:
    """Quadkey → GeoJSON Polygon（RFC 7946: WGS84）"""
    x, y, zoom = quadkey_to_tile(quadkey)
    bbox = _tile_to_bbox(x, y, zoom)
    w, s, e, n = bbox["west"], bbox["south"], bbox["east"], bbox["north"]
    return {
        "type": "Feature",
        "properties": {
            "quadkey": quadkey,
            "zoom": zoom,
            "tile_x": x,
            "tile_y": y,
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


# ---------------------------------------------------------------------------
# CSV バッチ処理
# ---------------------------------------------------------------------------

# カラム名の自動検出用
LAT_NAMES = {"lat", "latitude", "y", "緯度"}
LON_NAMES = {"lon", "lng", "longitude", "x", "経度"}
QUADKEY_NAMES = {"quadkey", "qk", "クアッドキー", "code"}


def _detect_column(fieldnames: list[str], candidates: set[str]) -> str | None:
    """CSV ヘッダーから候補名に一致するカラムを探す（大文字小文字無視）"""
    lower_map = {f.lower().strip(): f for f in fieldnames}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return None


def _batch_encode(input_path: str, output_path: str | None, zoom: int) -> None:
    """CSV 一括エンコード: 緯度経度列 → Quadkey"""
    with open(input_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        lat_col = _detect_column(fieldnames, LAT_NAMES)
        lon_col = _detect_column(fieldnames, LON_NAMES)
        if lat_col is None or lon_col is None:
            _error(f"CSV に緯度・経度列が見つかりません。検出可能な列名: {LAT_NAMES}, {LON_NAMES}")

        rows = list(reader)

    results = []
    for row in rows:
        try:
            lat = float(row[lat_col])
            lon = float(row[lon_col])
            enc = encode_from_latlon(lat, lon, zoom)
            results.append({
                "lat": lat,
                "lon": lon,
                "quadkey": enc["quadkey"],
                "zoom": zoom,
                "tile_x": enc["tile"]["x"],
                "tile_y": enc["tile"]["y"],
            })
        except (ValueError, KeyError) as e:
            results.append({
                "lat": row.get(lat_col, ""),
                "lon": row.get(lon_col, ""),
                "quadkey": None,
                "zoom": zoom,
                "tile_x": None,
                "tile_y": None,
                "error": str(e),
            })

    if output_path:
        out_fields = ["lat", "lon", "quadkey", "zoom", "tile_x", "tile_y"]
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)
        print(json.dumps({
            "status": "success",
            "output_file": output_path,
            "count": len(results),
            "failed": sum(1 for r in results if r["quadkey"] is None),
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": "success", "results": results}, ensure_ascii=False, indent=2))


def _batch_decode(input_path: str, output_path: str | None) -> None:
    """CSV 一括デコード: Quadkey列 → 緯度経度"""
    with open(input_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        qk_col = _detect_column(fieldnames, QUADKEY_NAMES)
        if qk_col is None:
            _error(f"CSV に Quadkey 列が見つかりません。検出可能な列名: {QUADKEY_NAMES}")

        rows = list(reader)

    results = []
    for row in rows:
        try:
            qk = row[qk_col].strip()
            dec = decode_quadkey(qk)
            results.append({
                "quadkey": qk,
                "zoom": dec["zoom"],
                "tile_x": dec["tile"]["x"],
                "tile_y": dec["tile"]["y"],
                "center_lat": dec["center"]["lat"],
                "center_lon": dec["center"]["lon"],
            })
        except (ValueError, KeyError) as e:
            results.append({
                "quadkey": row.get(qk_col, ""),
                "zoom": None,
                "tile_x": None,
                "tile_y": None,
                "center_lat": None,
                "center_lon": None,
                "error": str(e),
            })

    if output_path:
        out_fields = ["quadkey", "zoom", "tile_x", "tile_y", "center_lat", "center_lon"]
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
        description="Quadkey 空間インデックスの変換・探索ツール"
    )

    # エンコード: 緯度経度から
    parser.add_argument("--lat", type=float, default=None, help="緯度 (WGS84)")
    parser.add_argument("--lon", type=float, default=None, help="経度 (WGS84)")
    parser.add_argument("--zoom", type=int, default=None, help="ズームレベル (0〜28)")

    # エンコード: タイル座標から
    parser.add_argument("--tile-x", type=int, default=None, help="タイル X 座標")
    parser.add_argument("--tile-y", type=int, default=None, help="タイル Y 座標")

    # デコード / 操作
    parser.add_argument("--quadkey", type=str, default=None, help="Quadkey 文字列")
    parser.add_argument("--neighbors", action="store_true", help="8方向の隣接 Quadkey を取得")
    parser.add_argument("--parent", action="store_true", help="親 Quadkey を取得")
    parser.add_argument("--children", action="store_true", help="子 Quadkey 4つを取得")
    parser.add_argument("--boundary", action="store_true", help="GeoJSON Polygon を出力")

    # CSV バッチ
    parser.add_argument("--input", type=str, default=None, help="入力 CSV ファイルパス")
    parser.add_argument("--output", type=str, default=None, help="出力 CSV ファイルパス")
    parser.add_argument(
        "--operation",
        choices=["encode", "decode"],
        default=None,
        help="バッチ処理の操作 (encode: 緯度経度→Quadkey, decode: Quadkey→緯度経度)",
    )

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

    # --- 単一操作モード ---
    try:
        has_latlon = args.lat is not None and args.lon is not None
        has_tile = args.tile_x is not None and args.tile_y is not None
        has_quadkey = args.quadkey is not None

        # Quadkey を指定した操作
        if has_quadkey:
            qk = args.quadkey.strip()
            if not qk:
                _error("Quadkey が空です。")

            if args.neighbors:
                result = get_neighbors(qk)
            elif args.parent:
                result = get_parent(qk)
            elif args.children:
                result = get_children(qk)
            elif args.boundary:
                result = quadkey_to_geojson(qk)
            else:
                # デコード
                result = decode_quadkey(qk)

        # 緯度経度からエンコード
        elif has_latlon:
            if args.zoom is None:
                _error("--lat/--lon 指定時は --zoom も必要です。")
            if args.zoom < 0 or args.zoom > 28:
                _error("ズームレベルは 0〜28 の範囲で指定してください。")
            if not (-90 <= args.lat <= 90):
                _error("緯度は -90〜90 の範囲で指定してください。")
            if not (-180 <= args.lon <= 180):
                _error("経度は -180〜180 の範囲で指定してください。")
            result = encode_from_latlon(args.lat, args.lon, args.zoom)

        # タイル座標からエンコード
        elif has_tile:
            if args.zoom is None:
                _error("--tile-x/--tile-y 指定時は --zoom も必要です。")
            if args.zoom < 0 or args.zoom > 28:
                _error("ズームレベルは 0〜28 の範囲で指定してください。")
            result = encode_from_tile(args.tile_x, args.tile_y, args.zoom)

        else:
            _error(
                "--lat/--lon、--tile-x/--tile-y、--quadkey、"
                "または --input のいずれかを指定してください。"
            )

        print(json.dumps(result, ensure_ascii=False, indent=2))

    except ValueError as e:
        _error(str(e))
    except Exception as e:
        _error(f"処理中にエラーが発生しました: {e}")


if __name__ == "__main__":
    main()
