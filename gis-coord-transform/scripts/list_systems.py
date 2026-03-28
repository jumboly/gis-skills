#!/usr/bin/env python3
"""日本の座標系一覧表示スクリプト"""

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
from pyproj.database import query_crs_info


def list_japanese_crs(search: str | None = None, crs_type: str = "all") -> list[dict]:
    """日本に関連する座標系を検索・一覧表示する"""
    # pyproj の CRS データベースから日本関連の座標系を検索
    # area_of_use で "Japan" を含むものを取得
    type_filter = None
    if crs_type == "geographic":
        from pyproj.database import CRSType
        type_filter = CRSType.GEOGRAPHIC_2D
    elif crs_type == "projected":
        from pyproj.database import CRSType
        type_filter = CRSType.PROJECTED

    # 日本の座標系を取得（area_of_use に "Japan" を含むもの）
    if type_filter:
        crs_list = query_crs_info(
            auth_name="EPSG",
            area_of_use="Japan",
            crs_type=type_filter,
        )
    else:
        crs_list = query_crs_info(
            auth_name="EPSG",
            area_of_use="Japan",
        )

    results = []
    for info in crs_list:
        auth_name, code, name, crs_type_val, *rest = info
        # area_of_use は CRSInfo の属性
        area = info.area_of_use if hasattr(info, "area_of_use") else ""

        # キーワード検索フィルタ
        if search:
            search_lower = search.lower()
            searchable = f"{name} {code} {area}".lower()
            if search_lower not in searchable:
                continue

        results.append({
            "epsg": f"{auth_name}:{code}",
            "code": code,
            "name": name,
            "type": str(crs_type_val) if crs_type_val else "",
            "area_of_use": area or "",
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
