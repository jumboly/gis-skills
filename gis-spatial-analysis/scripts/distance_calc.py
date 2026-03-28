#!/usr/bin/env python3
"""距離計算スクリプト: ジオメトリ間の距離を計算する"""

import argparse
import contextlib
import csv
import json
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description="GeoJSON フィーチャ間の距離を計算する"
    )
    parser.add_argument("--input1", required=True, help="入力 GeoJSON ファイル1")
    parser.add_argument(
        "--input2",
        default=None,
        help="入力 GeoJSON ファイル2（省略時は input1 内での距離計算）",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["pairwise", "nearest", "matrix"],
        help="計算モード: pairwise（対応ペア）, nearest（最近傍）, matrix（全組み合わせ）",
    )
    parser.add_argument("--output", required=True, help="出力 CSV ファイルパス")
    parser.add_argument(
        "--use-geodesic",
        action="store_true",
        help="測地線距離を使用する（pyproj Geod）。未指定時は重心間のユークリッド距離",
    )
    return parser.parse_args()


_GEOD = None


def geodesic_distance(geom1, geom2):
    """2つのジオメトリの重心間の測地線距離（メートル）を計算する"""
    global _GEOD
    if _GEOD is None:
        from pyproj import Geod
        _GEOD = Geod(ellps="WGS84")
    c1 = geom1.centroid
    c2 = geom2.centroid
    _, _, dist = _GEOD.inv(c1.x, c1.y, c2.x, c2.y)
    return abs(dist)


def euclidean_distance(geom1, geom2):
    """2つのジオメトリ間のユークリッド距離を計算する（CRS の単位に依存）"""
    return geom1.distance(geom2)


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

    if args.input2:
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
    else:
        gdf2 = gdf1.copy()

    dist_func = geodesic_distance if args.use_geodesic else euclidean_distance
    dist_unit = "meters" if args.use_geodesic else "crs_units"
    distances = []

    if args.mode == "pairwise":
        n = min(len(gdf1), len(gdf2))
        if len(gdf1) != len(gdf2):
            print(
                json.dumps(
                    {
                        "warning": f"フィーチャ数が異なります（input1: {len(gdf1)}, input2: {len(gdf2)}）。"
                        f"先頭 {n} ペアのみ計算します。"
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )

        rows = []
        for i in range(n):
            d = dist_func(gdf1.geometry.iloc[i], gdf2.geometry.iloc[i])
            distances.append(d)
            rows.append({"index1": i, "index2": i, "distance": d})

        _write_csv(args.output, ["index1", "index2", "distance"], rows)

    elif args.mode == "nearest":
        # ストリーミング書き出しでメモリ使用量を抑制
        fieldnames = ["index1", "nearest_index2", "distance"]
        with _open_csv_writer(args.output, fieldnames) as writer:
            for i in range(len(gdf1)):
                min_dist = float("inf")
                min_idx = -1
                for j in range(len(gdf2)):
                    # 同一データセットの場合、自分自身との距離はスキップ
                    if args.input2 is None and i == j:
                        continue
                    d = dist_func(gdf1.geometry.iloc[i], gdf2.geometry.iloc[j])
                    if d < min_dist:
                        min_dist = d
                        min_idx = j
                if min_idx >= 0:
                    distances.append(min_dist)
                    writer.writerow(
                        {"index1": i, "nearest_index2": min_idx, "distance": min_dist}
                    )

    elif args.mode == "matrix":
        # ストリーミング書き出しでメモリ使用量を抑制
        fieldnames = ["index1", "index2", "distance"]
        with _open_csv_writer(args.output, fieldnames) as writer:
            for i in range(len(gdf1)):
                for j in range(len(gdf2)):
                    d = dist_func(gdf1.geometry.iloc[i], gdf2.geometry.iloc[j])
                    distances.append(d)
                    writer.writerow({"index1": i, "index2": j, "distance": d})

    if distances:
        summary = {
            "status": "success",
            "mode": args.mode,
            "geodesic": args.use_geodesic,
            "distance_unit": dist_unit,
            "input1_features": len(gdf1),
            "input2_features": len(gdf2),
            "pair_count": len(distances),
            "min_distance": round(min(distances), 6),
            "max_distance": round(max(distances), 6),
            "mean_distance": round(sum(distances) / len(distances), 6),
            "output_file": args.output,
        }
    else:
        summary = {
            "status": "success",
            "mode": args.mode,
            "pair_count": 0,
            "message": "距離を計算できるペアがありませんでした。",
        }

    print(json.dumps(summary, ensure_ascii=False, indent=2))


@contextlib.contextmanager
def _open_csv_writer(path, fieldnames):
    """CSV ファイルへのストリーミング書き出し用コンテキストマネージャ"""
    try:
        f = open(path, "w", newline="", encoding="utf-8")
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        yield writer
    except Exception as e:
        print(
            json.dumps(
                {"error": f"CSV ファイルの書き込みに失敗しました: {e}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)
    finally:
        f.close()


def _write_csv(path, fieldnames, rows):
    """CSV ファイルに結果を書き出す"""
    with _open_csv_writer(path, fieldnames) as writer:
        writer.writerows(rows)


if __name__ == "__main__":
    main()
