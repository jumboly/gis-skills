#!/usr/bin/env python3
"""ランダムポリゴン（GeoJSON Polygon）を生成するツール。

bbox または GeoJSON マスク内にランダムなポリゴンを生成する。
方式: voronoi（隙間なし分割）、convex-hull（独立ポリゴン）。
ドーナツポリゴン（穴あき）にも対応。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import (
    DEGREE_KM, add_area_args, add_common_args, auto_install, init_seed,
    random_point_in_mask, resolve_area, validate_count, write_output,
)


def _ensure_deps():
    """scipy/shapely を遅延インストールする。"""
    auto_install({"scipy": "scipy", "shapely": "shapely>=2.0"})


def generate_voronoi(
    bbox: tuple[float, float, float, float],
    count: int,
    rng,
    mask=None,
):
    """Voronoi 分割でポリゴンを生成する。bbox/mask 内を隙間なく分割。"""
    _ensure_deps()
    from scipy.spatial import Voronoi
    from shapely.geometry import Polygon, box

    west, south, east, north = bbox

    points = []
    for _ in range(count):
        if mask is not None:
            lon, lat = random_point_in_mask(mask, rng)
        else:
            lon = rng.uniform(west, east)
            lat = rng.uniform(south, north)
        points.append((lon, lat))

    if len(points) < 2:
        clip = mask if mask is not None else box(west, south, east, north)
        return [clip]

    # 無限セル対策: bbox 外側に仮想点を追加して全セルを有限化
    dx = (east - west) * 2
    dy = (north - south) * 2
    cx, cy = (west + east) / 2, (south + north) / 2
    far_points = [
        (cx - dx, cy - dy), (cx + dx, cy - dy),
        (cx - dx, cy + dy), (cx + dx, cy + dy),
        (cx - dx, cy), (cx + dx, cy),
        (cx, cy - dy), (cx, cy + dy),
    ]
    all_points = points + far_points

    vor = Voronoi(all_points)

    clip_geom = mask if mask is not None else box(west, south, east, north)
    polygons = []

    for i in range(len(points)):
        region_idx = vor.point_region[i]
        region = vor.regions[region_idx]
        if not region or -1 in region:
            continue
        verts = [vor.vertices[v] for v in region]
        try:
            poly = Polygon(verts)
            if not poly.is_valid:
                poly = poly.buffer(0)
            clipped = poly.intersection(clip_geom)
            if not clipped.is_empty and clipped.geom_type == "Polygon":
                polygons.append(clipped)
            elif clipped.geom_type == "MultiPolygon":
                largest = max(clipped.geoms, key=lambda g: g.area)
                polygons.append(largest)
        except Exception:
            # Voronoi セルの頂点配置が不正な場合はスキップ
            continue

    return polygons


def generate_convex_hull(
    bbox: tuple[float, float, float, float],
    count: int,
    rng,
    vertices_min: int,
    vertices_max: int,
    mask=None,
):
    """ランダム凸包でポリゴンを生成する。各ポリゴンは独立（重なりあり）。"""
    _ensure_deps()
    from shapely.geometry import MultiPoint

    west, south, east, north = bbox
    dx = east - west
    dy = north - south

    polygons = []
    for _ in range(count):
        n_verts = rng.randint(vertices_min, vertices_max)

        if mask is not None:
            cx, cy = random_point_in_mask(mask, rng)
        else:
            cx = rng.uniform(west, east)
            cy = rng.uniform(south, north)

        spread_x = dx * rng.uniform(0.02, 0.1)
        spread_y = dy * rng.uniform(0.02, 0.1)
        pts = [(cx + rng.gauss(0, spread_x), cy + rng.gauss(0, spread_y))
               for _ in range(n_verts)]

        if len(pts) < 3:
            continue

        hull = MultiPoint(pts).convex_hull
        if hull.geom_type != "Polygon":
            continue

        if mask is not None:
            hull = hull.intersection(mask)
            if hull.is_empty or hull.geom_type not in ("Polygon", "MultiPolygon"):
                continue
            if hull.geom_type == "MultiPolygon":
                hull = max(hull.geoms, key=lambda g: g.area)

        polygons.append(hull)

    return polygons


def add_holes(polygons, rng, max_holes: int, hole_ratio: float, donut_ratio: float):
    """ポリゴンにランダムな穴を追加してドーナツポリゴンを作る。"""
    from shapely.geometry import Point
    from shapely.ops import unary_union

    result = []
    for poly in polygons:
        if rng.random() > donut_ratio:
            result.append(poly)
            continue

        n_holes = rng.randint(1, max_holes)
        holes = []
        minx, miny, maxx, maxy = poly.bounds
        target_area = poly.area * hole_ratio / n_holes

        for _ in range(n_holes):
            for _ in range(100):
                hx = rng.uniform(minx, maxx)
                hy = rng.uniform(miny, maxy)
                if poly.contains(Point(hx, hy)):
                    break
            else:
                continue

            radius = math.sqrt(target_area / math.pi)
            hole = Point(hx, hy).buffer(radius, resolution=16)

            # ポリゴン境界から少し内側にクリップ
            hole = hole.intersection(poly.buffer(-radius * 0.1))
            if hole.is_empty or hole.geom_type not in ("Polygon", "MultiPolygon"):
                continue
            if hole.geom_type == "MultiPolygon":
                hole = max(hole.geoms, key=lambda g: g.area)
            holes.append(hole)

        if holes:
            try:
                result_poly = poly.difference(unary_union(holes))
                if result_poly.is_empty:
                    result.append(poly)
                elif result_poly.geom_type == "Polygon":
                    result.append(result_poly)
                elif result_poly.geom_type == "MultiPolygon":
                    result.append(max(result_poly.geoms, key=lambda g: g.area))
                else:
                    result.append(poly)
            except Exception:
                # ジオメトリ演算の例外時は穴なしで続行
                result.append(poly)
        else:
            result.append(poly)

    return result


def polygon_to_geojson_coords(poly) -> list:
    """Shapely Polygon を GeoJSON の coordinates 形式に変換する。"""
    coords = [list(poly.exterior.coords)]
    for interior in poly.interiors:
        coords.append(list(interior.coords))
    return [[list(c) for c in ring] for ring in coords]


def to_geojson(polygons, bbox, seed: int, params: dict) -> dict:
    """ポリゴンリストを GeoJSON FeatureCollection に変換する。"""
    # bbox 中央緯度での cos 係数を1回だけ計算
    mid_lat = (bbox[1] + bbox[3]) / 2
    cos_factor = math.cos(math.radians(mid_lat))

    features = []
    for i, poly in enumerate(polygons, 1):
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": polygon_to_geojson_coords(poly),
            },
            "properties": {
                "id": i,
                "area_km2": round(poly.area * (DEGREE_KM ** 2) * cos_factor, 4),
                "has_holes": len(poly.interiors) > 0,
                "n_holes": len(poly.interiors),
            },
        })
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "bbox": list(bbox),
            "count": len(polygons),
            "seed": seed,
            "generator": "random_polygons",
            "parameters": params,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="ランダムポリゴン（GeoJSON Polygon）を生成する"
    )
    add_area_args(parser)
    add_common_args(parser)
    parser.add_argument(
        "--method", choices=["voronoi", "convex-hull"],
        default="voronoi", help="生成方式 (デフォルト: voronoi)",
    )
    parser.add_argument("--vertices-min", type=int, default=5, help="convex-hull: 最小頂点数 (デフォルト: 5)")
    parser.add_argument("--vertices-max", type=int, default=12, help="convex-hull: 最大頂点数 (デフォルト: 12)")

    parser.add_argument("--holes", action="store_true", help="穴あきポリゴン（ドーナツ）を有効化")
    parser.add_argument("--max-holes", type=int, default=3, help="1ポリゴンあたりの最大穴数 (デフォルト: 3)")
    parser.add_argument(
        "--hole-ratio", type=float, default=0.3,
        help="穴の面積比（外側ポリゴンに対する割合、デフォルト: 0.3）",
    )
    parser.add_argument(
        "--donut-ratio", type=float, default=0.5,
        help="全ポリゴンのうち穴あきにする割合 (デフォルト: 0.5)",
    )
    args = parser.parse_args()

    validate_count(args.count)
    seed, rng = init_seed(args.seed)
    bbox, mask = resolve_area(args)

    params = {"method": args.method}
    if args.holes:
        params["holes"] = True
        params["max_holes"] = args.max_holes
        params["hole_ratio"] = args.hole_ratio
        params["donut_ratio"] = args.donut_ratio

    if args.method == "voronoi":
        polygons = generate_voronoi(bbox, args.count, rng, mask)
    elif args.method == "convex-hull":
        params["vertices_min"] = args.vertices_min
        params["vertices_max"] = args.vertices_max
        polygons = generate_convex_hull(
            bbox, args.count, rng, args.vertices_min, args.vertices_max, mask,
        )

    if args.holes:
        polygons = add_holes(polygons, rng, args.max_holes, args.hole_ratio, args.donut_ratio)

    result = to_geojson(polygons, bbox, seed, params)
    write_output(result, args.output, len(polygons))


if __name__ == "__main__":
    main()
