#!/usr/bin/env python3
"""gis-randomdata-gen スキル内の共通ユーティリティ。"""
from __future__ import annotations

import json
import random
import subprocess
import sys

# 赤道における緯度1度あたりの距離 (km)
DEGREE_KM = 111.32


def auto_install(deps: dict[str, str]):
    """未インストールの依存パッケージを自動インストールする。

    Args:
        deps: {import_name: pip_package_spec} の辞書
    """
    for mod, pkg in deps.items():
        try:
            __import__(mod)
        except ImportError:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                stdout=subprocess.DEVNULL,
            )


def load_mask(path: str):
    """GeoJSON ファイルからマスクポリゴンを読み込む。

    FeatureCollection / Feature / 生 Geometry いずれの形式にも対応。
    """
    auto_install({"shapely": "shapely>=2.0"})
    from shapely.geometry import shape

    with open(path) as f:
        data = json.load(f)

    if data.get("type") == "FeatureCollection":
        geom = shape(data["features"][0]["geometry"])
    elif data.get("type") == "Feature":
        geom = shape(data["geometry"])
    else:
        geom = shape(data)
    return geom


def random_point_in_mask(mask, rng: random.Random) -> tuple[float, float]:
    """マスクポリゴン内のランダムな点を rejection sampling で生成する。"""
    from shapely.geometry import Point

    minx, miny, maxx, maxy = mask.bounds
    for _ in range(10000):
        lon = rng.uniform(minx, maxx)
        lat = rng.uniform(miny, maxy)
        if mask.contains(Point(lon, lat)):
            return lon, lat
    raise RuntimeError("マスク内に点を生成できませんでした（形状が極端に細い可能性があります）")


def init_seed(seed_arg: int | None) -> tuple[int, random.Random]:
    """シードを初期化し、(seed値, Randomインスタンス) を返す。"""
    seed = seed_arg if seed_arg is not None else random.randint(0, 2**31 - 1)
    return seed, random.Random(seed)


def resolve_area(args) -> tuple[tuple[float, float, float, float], object | None]:
    """argparse の args から bbox とマスクを解決する。"""
    mask = None
    if args.mask:
        mask = load_mask(args.mask)
        bbox = mask.bounds
    else:
        bbox = tuple(args.bbox)
    return bbox, mask


def write_output(result: dict, output_path: str | None, count: int):
    """GeoJSON を stdout またはファイルに出力する。"""
    output_str = json.dumps(result, ensure_ascii=False, indent=2)
    if output_path:
        with open(output_path, "w") as f:
            f.write(output_str)
        print(json.dumps({"status": "success", "output": output_path, "count": count}))
    else:
        print(output_str)


def validate_count(count: int):
    """count の範囲チェック。範囲外なら stderr にエラーを出して終了。"""
    if count < 1:
        print(json.dumps({"error": "count は 1 以上を指定してください"}), file=sys.stderr)
        sys.exit(1)
    if count > 100000:
        print(json.dumps({"error": "count は 100,000 以下を指定してください"}), file=sys.stderr)
        sys.exit(1)


def add_area_args(parser):
    """--bbox / --mask の排他引数グループを argparse に追加する。"""
    area = parser.add_mutually_exclusive_group(required=True)
    area.add_argument(
        "--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help="矩形範囲 [west south east north]",
    )
    area.add_argument(
        "--mask", type=str,
        help="GeoJSON Polygon ファイルで不規則な範囲を指定",
    )


def add_common_args(parser):
    """--count / --seed / --output の共通引数を argparse に追加する。"""
    parser.add_argument("--count", type=int, default=10, help="生成数 (デフォルト: 10)")
    parser.add_argument("--seed", type=int, default=None, help="乱数シード（省略時はランダム）")
    parser.add_argument("--output", type=str, default=None, help="出力先ファイル（省略時は stdout）")
