#!/usr/bin/env python3
"""ランダムライン（GeoJSON LineString）を生成するツール。

bbox または GeoJSON マスク内にランダムな線分を生成する。
スタイル: random-walk（折れ線）、straight（直線）。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import (
    DEGREE_KM, add_area_args, add_common_args, init_seed,
    random_point_in_mask, resolve_area, validate_count, write_output,
)


def _random_point_in_bbox(
    bbox: tuple[float, float, float, float], rng,
) -> tuple[float, float]:
    west, south, east, north = bbox
    return rng.uniform(west, east), rng.uniform(south, north)


def generate_random_walk(
    bbox: tuple[float, float, float, float],
    count: int,
    rng,
    vertices_min: int,
    vertices_max: int,
    max_segment_km: float | None,
    mask=None,
) -> list[list[tuple[float, float]]]:
    """ランダムウォークで折れ線を生成する。"""
    west, south, east, north = bbox

    if max_segment_km is None:
        diag_km = math.sqrt(
            ((east - west) * DEGREE_KM * math.cos(math.radians((south + north) / 2))) ** 2
            + ((north - south) * DEGREE_KM) ** 2
        )
        max_segment_km = diag_km * 0.2

    lines = []
    for _ in range(count):
        n_verts = rng.randint(vertices_min, vertices_max)
        if mask is not None:
            lon, lat = random_point_in_mask(mask, rng)
        else:
            lon, lat = _random_point_in_bbox(bbox, rng)
        coords = [(lon, lat)]
        bearing = rng.uniform(0, 360)

        for _ in range(n_verts - 1):
            bearing += rng.gauss(0, 45)
            step_km = rng.uniform(max_segment_km * 0.2, max_segment_km)
            dlat = step_km / DEGREE_KM
            dlon = step_km / (DEGREE_KM * math.cos(math.radians(lat)))

            new_lon = lon + dlon * math.sin(math.radians(bearing))
            new_lat = lat + dlat * math.cos(math.radians(bearing))

            new_lon = max(west, min(east, new_lon))
            new_lat = max(south, min(north, new_lat))

            lon, lat = new_lon, new_lat
            coords.append((lon, lat))

        if mask is not None:
            coords = _clip_line_to_mask(coords, mask)
            if len(coords) < 2:
                p1 = random_point_in_mask(mask, rng)
                p2 = random_point_in_mask(mask, rng)
                coords = [p1, p2]

        lines.append(coords)
    return lines


def _clip_line_to_mask(
    coords: list[tuple[float, float]], mask,
) -> list[tuple[float, float]]:
    """ラインをマスクポリゴンでクリップする。"""
    from shapely.geometry import LineString

    line = LineString(coords)
    clipped = mask.intersection(line)
    if clipped.is_empty:
        return []
    if clipped.geom_type == "LineString":
        return list(clipped.coords)
    if clipped.geom_type == "MultiLineString":
        longest = max(clipped.geoms, key=lambda g: g.length)
        return list(longest.coords)
    return []


def generate_straight(
    bbox: tuple[float, float, float, float],
    count: int,
    rng,
    mask=None,
) -> list[list[tuple[float, float]]]:
    """始点と終点を結ぶ直線を生成する。"""
    lines = []
    for _ in range(count):
        if mask is not None:
            p1 = random_point_in_mask(mask, rng)
            p2 = random_point_in_mask(mask, rng)
        else:
            p1 = _random_point_in_bbox(bbox, rng)
            p2 = _random_point_in_bbox(bbox, rng)
        lines.append([p1, p2])
    return lines


def to_geojson(
    lines: list[list[tuple[float, float]]],
    bbox: tuple[float, float, float, float],
    seed: int,
    params: dict,
) -> dict:
    """ラインリストを GeoJSON FeatureCollection に変換する。"""
    features = []
    for i, coords in enumerate(lines, 1):
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [list(c) for c in coords],
            },
            "properties": {"id": i, "vertices": len(coords)},
        })
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "bbox": list(bbox),
            "count": len(lines),
            "seed": seed,
            "generator": "random_lines",
            "parameters": params,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="ランダムライン（GeoJSON LineString）を生成する"
    )
    add_area_args(parser)
    add_common_args(parser)
    parser.add_argument(
        "--style", choices=["random-walk", "straight"],
        default="random-walk", help="スタイル (デフォルト: random-walk)",
    )
    parser.add_argument("--vertices-min", type=int, default=3, help="最小頂点数 (デフォルト: 3)")
    parser.add_argument("--vertices-max", type=int, default=10, help="最大頂点数 (デフォルト: 10)")
    parser.add_argument(
        "--max-segment-km", type=float, default=None,
        help="セグメント最大長 (km)。省略時は bbox 対角線の 20%%",
    )
    args = parser.parse_args()

    validate_count(args.count)
    seed, rng = init_seed(args.seed)
    bbox, mask = resolve_area(args)

    params = {
        "style": args.style,
        "vertices_min": args.vertices_min,
        "vertices_max": args.vertices_max,
    }
    if args.max_segment_km is not None:
        params["max_segment_km"] = args.max_segment_km

    if args.style == "random-walk":
        lines = generate_random_walk(
            bbox, args.count, rng,
            args.vertices_min, args.vertices_max, args.max_segment_km, mask,
        )
    elif args.style == "straight":
        lines = generate_straight(bbox, args.count, rng, mask)

    result = to_geojson(lines, bbox, seed, params)
    write_output(result, args.output, len(lines))


if __name__ == "__main__":
    main()
