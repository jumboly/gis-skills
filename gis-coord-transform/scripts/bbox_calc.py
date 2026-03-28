#!/usr/bin/env python3
"""バウンディングボックス計算スクリプト - 中心座標・縮尺・ピクセル寸法からBBoxを算出"""

import argparse
import json
import math
import sys


def meters_per_pixel(scale_denominator: float, dpi: float) -> float:
    """縮尺とDPIから1ピクセルあたりの地上距離(メートル)を計算する

    1インチ = 0.0254m なので、1ピクセルの物理サイズ = 0.0254 / dpi (m)
    地上での1ピクセル = 物理サイズ × 縮尺分母
    """
    inch_per_meter = 1.0 / 0.0254
    return scale_denominator / (dpi * inch_per_meter)


def offset_lat(lat: float, distance_m: float) -> float:
    """緯度方向にメートル単位でオフセットした緯度を返す

    地球を球体近似: 緯度1度 ≈ 111,320m
    """
    return lat + (distance_m / 111_320.0)


def offset_lon(lat: float, lon: float, distance_m: float) -> float:
    """経度方向にメートル単位でオフセットした経度を返す

    経度1度の距離は緯度に依存: 111,320m × cos(lat)
    """
    meters_per_deg = 111_320.0 * math.cos(math.radians(lat))
    if meters_per_deg == 0:
        return lon
    return lon + (distance_m / meters_per_deg)


def calculate_bbox(
    lat: float, lon: float, scale: float, width_px: int, height_px: int, dpi: float
) -> dict:
    """中心座標・縮尺・ピクセル寸法からBBoxと地上寸法を計算する"""
    mpp = meters_per_pixel(scale, dpi)

    # 地上での幅・高さ（メートル）
    ground_width_m = width_px * mpp
    ground_height_m = height_px * mpp

    # 中心からの半分の距離でオフセット
    half_w = ground_width_m / 2.0
    half_h = ground_height_m / 2.0

    south = offset_lat(lat, -half_h)
    north = offset_lat(lat, half_h)
    west = offset_lon(lat, lon, -half_w)
    east = offset_lon(lat, lon, half_w)

    return {
        "bbox": [west, south, east, north],
        "bbox_wsen": {
            "west": west,
            "south": south,
            "east": east,
            "north": north,
        },
        "ground_dimensions": {
            "width_m": round(ground_width_m, 3),
            "height_m": round(ground_height_m, 3),
        },
        "parameters": {
            "center_lat": lat,
            "center_lon": lon,
            "scale": f"1:{int(scale)}",
            "width_px": width_px,
            "height_px": height_px,
            "dpi": dpi,
            "meters_per_pixel": round(mpp, 6),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="中心座標・縮尺・ピクセル寸法からバウンディングボックスを計算"
    )
    parser.add_argument("--lat", type=float, required=True, help="中心緯度 (WGS84)")
    parser.add_argument("--lon", type=float, required=True, help="中心経度 (WGS84)")
    parser.add_argument(
        "--scale", type=float, required=True,
        help="縮尺の分母 (例: 2000 → 1:2000)"
    )
    parser.add_argument("--width", type=int, required=True, help="画像の幅 (ピクセル)")
    parser.add_argument("--height", type=int, required=True, help="画像の高さ (ピクセル)")
    parser.add_argument(
        "--dpi", type=float, default=96, help="解像度 (デフォルト: 96)"
    )
    args = parser.parse_args()

    if not (-90 <= args.lat <= 90):
        print(json.dumps({"error": "緯度は -90 〜 90 の範囲で指定してください。"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    if not (-180 <= args.lon <= 180):
        print(json.dumps({"error": "経度は -180 〜 180 の範囲で指定してください。"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    if args.scale <= 0:
        print(json.dumps({"error": "縮尺は正の数で指定してください。"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    try:
        result = calculate_bbox(
            args.lat, args.lon, args.scale, args.width, args.height, args.dpi
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": f"計算中にエラーが発生しました: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
