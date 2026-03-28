#!/usr/bin/env python3
"""タイル座標変換スクリプト - 緯度経度 ↔ XYZ タイル座標の相互変換"""

import argparse
import json
import math
import sys


def latlon_to_tile(lat: float, lon: float, zoom: int) -> dict:
    """緯度経度からXYZタイル座標を計算する（Slippy map tilenames 仕様）"""
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)

    # タイル範囲を超えないようクランプ
    x = max(0, min(x, n - 1))
    y = max(0, min(y, n - 1))

    # タイルのバウンディングボックスも計算
    bbox = tile_to_bbox(x, y, zoom)

    return {
        "mode": "latlon_to_tile",
        "input": {"lat": lat, "lon": lon, "zoom": zoom},
        "tile": {"x": x, "y": y, "z": zoom},
        "tile_bbox": bbox,
    }


def tile_to_bbox(x: int, y: int, zoom: int) -> dict:
    """タイル座標からバウンディングボックスを計算する"""
    n = 2 ** zoom

    # 北西角（左上）
    west = x / n * 360.0 - 180.0
    north_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    north = math.degrees(north_rad)

    # 南東角（右下）
    east = (x + 1) / n * 360.0 - 180.0
    south_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
    south = math.degrees(south_rad)

    return {
        "west": west,
        "south": south,
        "east": east,
        "north": north,
    }


def tile_to_latlon(x: int, y: int, zoom: int) -> dict:
    """XYZタイル座標から緯度経度（タイル中心とBBox）を返す"""
    bbox = tile_to_bbox(x, y, zoom)

    # タイルの中心座標
    center_lat = (bbox["north"] + bbox["south"]) / 2.0
    center_lon = (bbox["west"] + bbox["east"]) / 2.0

    return {
        "mode": "tile_to_latlon",
        "input": {"x": x, "y": y, "zoom": zoom},
        "center": {"lat": center_lat, "lon": center_lon},
        "bbox": bbox,
        "bbox_array": [bbox["west"], bbox["south"], bbox["east"], bbox["north"]],
    }


def main():
    parser = argparse.ArgumentParser(
        description="緯度経度 ↔ XYZ タイル座標の相互変換"
    )
    parser.add_argument("--lat", type=float, default=None, help="緯度 (WGS84)")
    parser.add_argument("--lon", type=float, default=None, help="経度 (WGS84)")
    parser.add_argument("--x", type=int, default=None, help="タイル X 座標")
    parser.add_argument("--y", type=int, default=None, help="タイル Y 座標")
    parser.add_argument("--zoom", type=int, required=True, help="ズームレベル")
    args = parser.parse_args()

    has_latlon = args.lat is not None and args.lon is not None
    has_tile = args.x is not None and args.y is not None

    if has_latlon and has_tile:
        print(
            json.dumps(
                {"error": "lat/lon と x/y は同時に指定できません。どちらか一方を指定してください。"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    if not has_latlon and not has_tile:
        print(
            json.dumps(
                {"error": "--lat/--lon または --x/--y のいずれかを指定してください。"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    if args.zoom < 0 or args.zoom > 28:
        print(
            json.dumps({"error": "ズームレベルは 0〜28 の範囲で指定してください。"}, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        if has_latlon:
            if not (-90 <= args.lat <= 90):
                raise ValueError("緯度は -90 〜 90 の範囲で指定してください。")
            if not (-180 <= args.lon <= 180):
                raise ValueError("経度は -180 〜 180 の範囲で指定してください。")
            result = latlon_to_tile(args.lat, args.lon, args.zoom)
        else:
            n = 2 ** args.zoom
            if not (0 <= args.x < n) or not (0 <= args.y < n):
                raise ValueError(
                    f"ズームレベル {args.zoom} でのタイル座標は 0〜{n - 1} の範囲です。"
                )
            result = tile_to_latlon(args.x, args.y, args.zoom)

        print(json.dumps(result, ensure_ascii=False, indent=2))

    except ValueError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"変換中にエラーが発生しました: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
