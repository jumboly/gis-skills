#!/usr/bin/env python3
"""ランダムポイント（GeoJSON Point）を生成するツール。

bbox または GeoJSON マスク内にランダムな点群を生成する。
分布パターン: uniform（一様）、clustered（クラスター）、grid（格子）。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import (
    add_area_args, add_common_args, init_seed, random_point_in_mask,
    resolve_area, validate_count, write_output,
)


def generate_uniform(
    bbox: tuple[float, float, float, float],
    count: int,
    rng,
    mask=None,
) -> list[tuple[float, float]]:
    """一様分布でランダムポイントを生成する。"""
    west, south, east, north = bbox
    points = []
    for _ in range(count):
        if mask is not None:
            lon, lat = random_point_in_mask(mask, rng)
        else:
            lon = rng.uniform(west, east)
            lat = rng.uniform(south, north)
        points.append((lon, lat))
    return points


def generate_clustered(
    bbox: tuple[float, float, float, float],
    count: int,
    rng,
    clusters: int,
    spread: float | None,
    mask=None,
) -> list[tuple[float, float]]:
    """クラスター分布でランダムポイントを生成する。"""
    west, south, east, north = bbox
    if spread is None:
        spread = (east - west) * 0.1

    centers = []
    for _ in range(clusters):
        if mask is not None:
            cx, cy = random_point_in_mask(mask, rng)
        else:
            cx = rng.uniform(west, east)
            cy = rng.uniform(south, north)
        centers.append((cx, cy))

    # マスク使用時は shapely を1回だけ import
    _Point = None
    if mask is not None:
        from shapely.geometry import Point as _Point

    points = []
    for _ in range(count):
        cx, cy = rng.choice(centers)
        lon = rng.gauss(cx, spread)
        lat = rng.gauss(cy, spread)
        lon = max(west, min(east, lon))
        lat = max(south, min(north, lat))
        if mask is not None and not mask.contains(_Point(lon, lat)):
            lon, lat = random_point_in_mask(mask, rng)
        points.append((lon, lat))
    return points


def generate_grid(
    bbox: tuple[float, float, float, float],
    count: int,
    mask=None,
) -> list[tuple[float, float]]:
    """等間隔格子点を生成する。count は目標数（実際の数は格子に依存）。"""
    west, south, east, north = bbox
    aspect = (east - west) / max(north - south, 1e-10)
    rows = max(1, int(math.sqrt(count / max(aspect, 1e-10))))
    cols = max(1, int(count / rows))

    lon_step = (east - west) / max(cols, 1)
    lat_step = (north - south) / max(rows, 1)

    # マスク使用時は shapely を1回だけ import
    _Point = None
    if mask is not None:
        from shapely.geometry import Point as _Point

    points = []
    for r in range(rows):
        for c in range(cols):
            lon = west + lon_step * (c + 0.5)
            lat = south + lat_step * (r + 0.5)
            if mask is not None and not mask.contains(_Point(lon, lat)):
                continue
            points.append((lon, lat))
    return points


def to_geojson(
    points: list[tuple[float, float]],
    bbox: tuple[float, float, float, float],
    seed: int,
    params: dict,
) -> dict:
    """ポイントリストを GeoJSON FeatureCollection に変換する。"""
    features = []
    for i, (lon, lat) in enumerate(points, 1):
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"id": i},
        })
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "bbox": list(bbox),
            "count": len(points),
            "seed": seed,
            "generator": "random_points",
            "parameters": params,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="ランダムポイント（GeoJSON Point）を生成する"
    )
    add_area_args(parser)
    add_common_args(parser)
    parser.add_argument(
        "--distribution", choices=["uniform", "clustered", "grid"],
        default="uniform", help="分布パターン (デフォルト: uniform)",
    )
    parser.add_argument("--clusters", type=int, default=3, help="クラスター数 (デフォルト: 3)")
    parser.add_argument(
        "--cluster-spread", type=float, default=None,
        help="クラスターの広がり（度数）。省略時は bbox 幅の 10%%",
    )
    args = parser.parse_args()

    validate_count(args.count)
    seed, rng = init_seed(args.seed)
    bbox, mask = resolve_area(args)

    params = {"distribution": args.distribution}
    if args.distribution == "clustered":
        params["clusters"] = args.clusters
        params["cluster_spread"] = args.cluster_spread

    if args.distribution == "uniform":
        points = generate_uniform(bbox, args.count, rng, mask)
    elif args.distribution == "clustered":
        points = generate_clustered(
            bbox, args.count, rng, args.clusters, args.cluster_spread, mask,
        )
    elif args.distribution == "grid":
        points = generate_grid(bbox, args.count, mask)

    result = to_geojson(points, bbox, seed, params)
    write_output(result, args.output, len(points))


if __name__ == "__main__":
    main()
