#!/usr/bin/env python3
"""日本の座標系一覧表示スクリプト"""
from __future__ import annotations  # Python 3.9 で str | None 構文を有効化

import argparse
import json
import subprocess
import sys


def _auto_install():
    """未インストールの依存パッケージを自動インストールする"""
    for mod, pkg in {"pyproj": "pyproj"}.items():
        try:
            __import__(mod)
        except ImportError:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                stdout=subprocess.DEVNULL,
            )


_auto_install()

from pyproj import CRS
from pyproj.aoi import AreaOfInterest
from pyproj.database import query_crs_info
from pyproj.enums import PJType


# 日本の概略的なバウンディングボックス
_JAPAN_AOI = AreaOfInterest(
    west_lon_degree=122.0, south_lat_degree=20.0,
    east_lon_degree=154.0, north_lat_degree=46.0,
)

_PJ_TYPE_MAP = {
    "geographic": [PJType.GEOGRAPHIC_2D_CRS],
    "projected": [PJType.PROJECTED_CRS],
}

# 日本語キーワードから英語名へのマッピング（検索の利便性向上）
_JA_KEYWORD_MAP = {
    "平面直角": "plane rectangular",
    "地理座標": "geographic",
    "ウェブメルカトル": "web mercator",
    "webメルカトル": "web mercator",
    "utm": "utm",
    "旧測地系": "tokyo",
    "日本測地系2000": "jgd2000",
    "日本測地系2011": "jgd2011",
}


def list_japanese_crs(search: str | None = None, crs_type: str = "all") -> list[dict]:
    """日本に関連する座標系を検索・一覧表示する"""
    pj_types = _PJ_TYPE_MAP.get(crs_type)

    crs_list = query_crs_info(
        auth_name="EPSG",
        area_of_interest=_JAPAN_AOI,
        pj_types=pj_types,
    )

    # "Japan" を含むもののみに絞る（AOI は周辺国も含むため）
    results = []
    for info in crs_list:
        area = info.area_of_use
        area_name = area.name if area else ""
        if "Japan" not in area_name and "日本" not in area_name:
            continue

        # キーワード検索フィルタ
        if search:
            # 日本語キーワードを英語に変換して検索
            search_lower = search.lower()
            search_terms = [search_lower]
            for ja, en in _JA_KEYWORD_MAP.items():
                if ja in search_lower:
                    search_terms.append(search_lower.replace(ja, en))
            searchable = f"{info.name} {info.code} {area_name}".lower()
            if not any(term in searchable for term in search_terms):
                continue

        results.append({
            "epsg": f"{info.auth_name}:{info.code}",
            "code": info.code,
            "name": info.name,
            "type": str(info.type) if info.type else "",
            "area_of_use": area_name,
        })

    # EPSG コード順にソート
    results.sort(key=lambda x: x["code"])
    return results


def main():
    parser = argparse.ArgumentParser(
        description="日本の座標系（EPSG コード）を一覧表示"
    )
    parser.add_argument(
        "--search",
        default=None,
        help="検索キーワード（名前・コード・使用地域で部分一致検索）",
    )
    parser.add_argument(
        "--type",
        choices=["geographic", "projected", "all"],
        default="all",
        help="座標系の種類でフィルタ (geographic: 地理座標系, projected: 投影座標系, all: すべて)",
    )
    args = parser.parse_args()

    try:
        results = list_japanese_crs(search=args.search, crs_type=args.type)

        output = {
            "count": len(results),
            "filter": {
                "search": args.search,
                "type": args.type,
            },
            "coordinate_systems": results,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))

    except Exception as e:
        print(
            json.dumps({"error": f"座標系の取得中にエラーが発生しました: {e}"}, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
