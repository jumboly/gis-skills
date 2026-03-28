#!/usr/bin/env python3
"""オーバーレイ解析スクリプト: 2つのレイヤ間で空間演算を行う"""

import argparse
import json
import sys

VALID_OPERATIONS = ["intersection", "union", "difference", "symmetric_difference"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="2つの GeoJSON レイヤ間でオーバーレイ解析を行う"
    )
    parser.add_argument("--input1", required=True, help="入力 GeoJSON ファイル1")
    parser.add_argument("--input2", required=True, help="入力 GeoJSON ファイル2")
    parser.add_argument(
        "--operation",
        required=True,
        choices=VALID_OPERATIONS,
        help=f"オーバーレイ操作: {', '.join(VALID_OPERATIONS)}",
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
        gdf1 = gpd.read_file(args.input1)
    except Exception as e:
        print(
            json.dumps(
                {"error": f"入力ファイル1の読み込みに失敗しました: {e}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        gdf2 = gpd.read_file(args.input2)
    except Exception as e:
        print(
            json.dumps(
                {"error": f"入力ファイル2の読み込みに失敗しました: {e}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    # CRS の整合: input2 を input1 の CRS に合わせる
    if gdf1.crs is not None and gdf2.crs is not None and gdf1.crs != gdf2.crs:
        gdf2 = gdf2.to_crs(gdf1.crs)

    try:
        result = gpd.overlay(gdf1, gdf2, how=args.operation)
    except Exception as e:
        print(
            json.dumps(
                {"error": f"オーバーレイ操作 '{args.operation}' に失敗しました: {e}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        result.to_file(args.output, driver="GeoJSON")
    except Exception as e:
        print(
            json.dumps(
                {"error": f"出力ファイルの書き込みに失敗しました: {e}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    # ジオメトリタイプの集計
    geom_types = result.geometry.geom_type.value_counts().to_dict()

    summary = {
        "status": "success",
        "input1": args.input1,
        "input2": args.input2,
        "operation": args.operation,
        "output_file": args.output,
        "input1_feature_count": len(gdf1),
        "input2_feature_count": len(gdf2),
        "result_feature_count": len(result),
        "result_geometry_types": geom_types,
        "result_crs": str(result.crs) if result.crs else None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
