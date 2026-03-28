#!/usr/bin/env python3
"""バッファ解析スクリプト: 入力ジオメトリに対してバッファを生成する"""

import argparse
import json
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description="GeoJSON フィーチャに対してバッファ解析を行う"
    )
    parser.add_argument("--input", required=True, help="入力 GeoJSON ファイルパス")
    parser.add_argument(
        "--distance", required=True, type=float, help="バッファ距離（メートル）"
    )
    parser.add_argument(
        "--epsg",
        required=True,
        type=int,
        help="投影座標系の EPSG コード（例: 6677 = JGD2011 / Japan Plane IX）",
    )
    parser.add_argument("--output", required=True, help="出力 GeoJSON ファイルパス")
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        import geopandas as gpd
    except ImportError:
        import subprocess
        for pkg in ["shapely", "geopandas", "pyproj"]:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                stdout=subprocess.DEVNULL,
            )
        import geopandas as gpd

    try:
        gdf = gpd.read_file(args.input)
    except Exception as e:
        print(
            json.dumps(
                {"error": f"入力ファイルの読み込みに失敗しました: {e}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    if gdf.empty:
        print(
            json.dumps({"error": "入力ファイルにフィーチャが含まれていません。"}, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(1)

    original_crs = gdf.crs

    # 正確なバッファ計算のため投影座標系に変換
    try:
        gdf_projected = gdf.to_crs(epsg=args.epsg)
    except Exception as e:
        print(
            json.dumps(
                {"error": f"EPSG:{args.epsg} への座標変換に失敗しました: {e}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    # バッファ生成（投影座標系上でメートル単位）
    gdf_buffered = gdf_projected.copy()
    gdf_buffered["geometry"] = gdf_projected.geometry.buffer(args.distance)

    # バッファ面積を投影座標系で計算（平方メートル）
    total_area_m2 = gdf_buffered.geometry.area.sum()

    # WGS84 に戻す
    if original_crs is not None:
        gdf_output = gdf_buffered.to_crs(original_crs)
    else:
        # 元の CRS が不明の場合は WGS84 を使用
        gdf_output = gdf_buffered.to_crs(epsg=4326)

    try:
        gdf_output.to_file(args.output, driver="GeoJSON")
    except Exception as e:
        print(
            json.dumps(
                {"error": f"出力ファイルの書き込みに失敗しました: {e}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    summary = {
        "status": "success",
        "input_file": args.input,
        "output_file": args.output,
        "buffer_distance_m": args.distance,
        "projected_crs": f"EPSG:{args.epsg}",
        "feature_count": len(gdf_output),
        "total_area_m2": round(total_area_m2, 2),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
