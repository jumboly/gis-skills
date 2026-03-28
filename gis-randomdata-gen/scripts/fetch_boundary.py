#!/usr/bin/env python3
"""Overpass API で行政界ポリゴンを取得するツール。

都道府県・市区町村・町丁目の境界を GeoJSON Polygon/MultiPolygon として出力する。
gis-randomdata-gen の --mask オプションと組み合わせて使用可能。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _common import auto_install

auto_install({"requests": "requests", "shapely": "shapely>=2.0"})

import requests
from shapely.geometry import LineString, MultiPolygon, Polygon, mapping
from shapely.ops import polygonize, unary_union

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
USER_AGENT = "gis-skills-fetch-boundary/1.0"

# --level から OSM admin_level への変換
LEVEL_MAP = {
    "prefecture": [4],
    "municipality": [7],
    # 町丁目は OSM のマッピング状況に依存するため複数レベルを試す
    "town": [8, 9, 10],
}


def _query_overpass(name: str, admin_level: int) -> dict:
    """Overpass API にクエリを送信して JSON レスポンスを返す。"""
    query = f"""[out:json][timeout:30];
relation["name"="{name}"]["admin_level"="{admin_level}"];
out geom;"""
    resp = requests.get(
        OVERPASS_ENDPOINT,
        params={"data": query},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _build_rings(ways: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    """way の座標列を連結して閉じたリングを構築する。

    Overpass の relation には複数の way が含まれ、
    端点が一致する way 同士を連結して閉リングにする必要がある。
    """
    if not ways:
        return []

    lines = [LineString(w) for w in ways if len(w) >= 2]
    if not lines:
        return []

    # polygonize は閉じたリングを自動構築する
    merged = unary_union(lines)
    polys = list(polygonize(merged))
    rings = [list(p.exterior.coords) for p in polys]
    return rings


def _relation_to_geometry(element: dict) -> Polygon | MultiPolygon | None:
    """Overpass の relation 要素を Shapely ジオメトリに変換する。"""
    members = element.get("members", [])

    outer_ways = []
    inner_ways = []
    for member in members:
        if member.get("type") != "way":
            continue
        geom = member.get("geometry", [])
        if not geom:
            continue
        coords = [(p["lon"], p["lat"]) for p in geom]
        role = member.get("role", "outer")
        if role == "outer":
            outer_ways.append(coords)
        elif role == "inner":
            inner_ways.append(coords)

    outer_rings = _build_rings(outer_ways)
    inner_rings = _build_rings(inner_ways)

    if not outer_rings:
        return None

    # 各 outer ring に対して、内包する inner ring を穴として割り当てる
    polygons = []
    for outer in outer_rings:
        outer_poly = Polygon(outer)
        if not outer_poly.is_valid:
            outer_poly = outer_poly.buffer(0)
        holes = []
        for inner in inner_rings:
            inner_poly = Polygon(inner)
            if not inner_poly.is_valid:
                inner_poly = inner_poly.buffer(0)
            if outer_poly.contains(inner_poly):
                holes.append(inner)
        poly = Polygon(outer, holes) if holes else outer_poly
        if not poly.is_valid:
            poly = poly.buffer(0)
        if not poly.is_empty:
            polygons.append(poly)

    if not polygons:
        return None
    if len(polygons) == 1:
        return polygons[0]
    return MultiPolygon(polygons)


def fetch_boundary(name: str, admin_levels: list[int]) -> dict | None:
    """行政界ポリゴンを取得して GeoJSON geometry dict を返す。"""
    for level in admin_levels:
        data = _query_overpass(name, level)
        elements = data.get("elements", [])

        for elem in elements:
            if elem.get("type") != "relation":
                continue
            geom = _relation_to_geometry(elem)
            if geom is not None:
                result = mapping(geom)
                # 取得した行政区域の情報を metadata として付与
                tags = elem.get("tags", {})
                return {
                    "geometry": result,
                    "name": tags.get("name", name),
                    "admin_level": tags.get("admin_level", str(level)),
                    "osm_id": elem.get("id"),
                }

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Overpass API で行政界ポリゴンを取得する（GeoJSON 出力）"
    )
    parser.add_argument("--name", required=True, help="行政区域名（例: 渋谷区、大阪府）")
    parser.add_argument(
        "--level", choices=["prefecture", "municipality", "town"],
        default="municipality",
        help="行政レベル (デフォルト: municipality)",
    )
    parser.add_argument("--output", type=str, default=None, help="出力先ファイル（省略時は stdout）")
    args = parser.parse_args()

    admin_levels = LEVEL_MAP[args.level]
    result = fetch_boundary(args.name, admin_levels)

    if result is None:
        print(json.dumps({
            "error": f"'{args.name}' (level={args.level}) の行政界が見つかりませんでした",
        }), file=sys.stderr)
        sys.exit(1)

    # load_mask() が受け付ける GeoJSON 形式で出力
    geojson = result["geometry"]

    output_str = json.dumps(geojson, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output_str)
        print(json.dumps({
            "status": "success",
            "output": args.output,
            "name": result["name"],
            "admin_level": result["admin_level"],
            "osm_id": result["osm_id"],
            "geometry_type": geojson["type"],
        }, ensure_ascii=False))
    else:
        print(output_str)


if __name__ == "__main__":
    main()
