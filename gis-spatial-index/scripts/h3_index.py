#!/usr/bin/env python3
"""H3 空間インデックススクリプト - エンコード・デコード・K-ring・ポリフィル・コンパクト等"""
from __future__ import annotations

import argparse
import csv
import json
import sys


def _auto_install():
    for mod, pkg in {"h3": "h3>=4.0"}.items():
        try:
            __import__(mod)
        except ImportError:
            import subprocess, sys
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                stdout=subprocess.DEVNULL,
            )

_auto_install()

import h3  # noqa: E402 — h3 v4+ が _auto_install で確保済み

# H3 解像度ごとの平均エッジ長（メートル）。解像度推定に使用
H3_EDGE_LENGTHS = [
    1107710, 418676, 158244, 59810, 22606, 8544, 3229, 1221,
    461, 174, 65, 24, 9, 3, 1, 0.5,
]

# CSV 列名の自動検出用
LAT_NAMES = {"lat", "latitude", "y", "緯度"}
LON_NAMES = {"lon", "lng", "longitude", "x", "経度"}
H3_NAMES = {"h3", "h3_index", "cell", "hex", "h3_cell", "セル"}


def _error(msg: str) -> None:
    """エラーメッセージを stderr に JSON 出力して終了する。"""
    print(json.dumps({"error": msg}, ensure_ascii=False), file=sys.stderr)
    sys.exit(1)


def encode_cell(lat: float, lon: float, resolution: int) -> dict:
    """緯度経度を H3 セル ID にエンコードする。"""
    cell = h3.latlng_to_cell(lat, lon, resolution)
    center_lat, center_lon = h3.cell_to_latlng(cell)
    return {
        "cell": cell,
        "resolution": resolution,
        "center": {"lat": center_lat, "lon": center_lon},
        "input": {"lat": lat, "lon": lon},
    }


def decode_cell(cell: str) -> dict:
    """H3 セル ID をデコードして中心座標と解像度を返す。"""
    if not h3.is_valid_cell(cell):
        raise ValueError(f"無効な H3 セル ID です: '{cell}'")
    center_lat, center_lon = h3.cell_to_latlng(cell)
    resolution = h3.get_resolution(cell)
    return {
        "cell": cell,
        "resolution": resolution,
        "center": {"lat": center_lat, "lon": center_lon},
    }


def k_ring(cell: str, k: int) -> dict:
    """指定セルの k-ring（k 距離以内の全セル）を返す。"""
    if not h3.is_valid_cell(cell):
        raise ValueError(f"無効な H3 セル ID です: '{cell}'")
    if k < 0:
        raise ValueError("k は 0 以上の整数を指定してください。")
    cells = sorted(h3.grid_disk(cell, k))
    return {
        "operation": "k_ring",
        "cell": cell,
        "k": k,
        "count": len(cells),
        "cells": cells,
    }


def parent_cell(cell: str, resolution: int) -> dict:
    """指定セルの親セルを返す。"""
    if not h3.is_valid_cell(cell):
        raise ValueError(f"無効な H3 セル ID です: '{cell}'")
    current_res = h3.get_resolution(cell)
    if resolution >= current_res:
        raise ValueError(
            f"親の解像度 ({resolution}) は現在の解像度 ({current_res}) より小さくなければなりません。"
        )
    if resolution < 0:
        raise ValueError("解像度は 0 以上を指定してください。")
    parent = h3.cell_to_parent(cell, resolution)
    parent_lat, parent_lon = h3.cell_to_latlng(parent)
    return {
        "operation": "parent",
        "cell": cell,
        "cell_resolution": current_res,
        "parent": parent,
        "parent_resolution": resolution,
        "parent_center": {"lat": parent_lat, "lon": parent_lon},
    }


def children_cells(cell: str, resolution: int) -> dict:
    """指定セルの子セルを返す。"""
    if not h3.is_valid_cell(cell):
        raise ValueError(f"無効な H3 セル ID です: '{cell}'")
    current_res = h3.get_resolution(cell)
    if resolution <= current_res:
        raise ValueError(
            f"子の解像度 ({resolution}) は現在の解像度 ({current_res}) より大きくなければなりません。"
        )
    if resolution > 15:
        raise ValueError("解像度は 15 以下を指定してください。")
    children = sorted(h3.cell_to_children(cell, resolution))
    return {
        "operation": "children",
        "cell": cell,
        "cell_resolution": current_res,
        "child_resolution": resolution,
        "count": len(children),
        "children": children,
    }


def boundary_geojson(cell: str) -> dict:
    """H3 セルの境界を GeoJSON Feature (Polygon) として返す。"""
    if not h3.is_valid_cell(cell):
        raise ValueError(f"無効な H3 セル ID です: '{cell}'")
    # cell_to_boundary は (lat, lng) タプルのリストを返す → GeoJSON は [lng, lat] 順
    boundary = h3.cell_to_boundary(cell)
    coords = [[lng, lat] for lat, lng in boundary]
    # GeoJSON Polygon は閉じたリングにする
    coords.append(coords[0])
    return {
        "type": "Feature",
        "properties": {
            "cell": cell,
            "resolution": h3.get_resolution(cell),
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [coords],
        },
    }


def polyfill_polygon(geojson_path: str, resolution: int, max_cells: int) -> dict:
    """GeoJSON ポリゴンを H3 セルでポリフィルする。"""
    with open(geojson_path, encoding="utf-8") as f:
        geojson_data = json.load(f)

    rings = _extract_polygon_coords(geojson_data)
    if not rings:
        raise ValueError("GeoJSON から Polygon / MultiPolygon が見つかりませんでした。")

    all_cells: set[str] = set()
    for outer_ring in rings:
        # GeoJSON は [lng, lat] 順 → h3.LatLngPoly は (lat, lng) タプルが必要
        latlng_tuples = [(lat, lng) for lng, lat in outer_ring]
        polygon = h3.LatLngPoly(latlng_tuples)
        cells = h3.polygon_to_cells(polygon, resolution)
        all_cells.update(cells)

    unique_cells = sorted(all_cells)

    if len(unique_cells) > max_cells:
        raise ValueError(
            f"セル数が上限 {max_cells:,} を超えました（{len(unique_cells):,} セル）。"
            f"解像度を下げるか --max-cells を増やしてください。"
        )

    return {
        "operation": "polyfill",
        "resolution": resolution,
        "count": len(unique_cells),
        "cells": unique_cells,
    }


def _extract_polygon_coords(geojson: dict) -> list[list[list[float]]]:
    """GeoJSON から Polygon/MultiPolygon の外周リング座標を抽出する。

    FeatureCollection, Feature, Geometry いずれの形式にも対応する。
    """
    rings: list[list[list[float]]] = []
    geom_type = geojson.get("type")

    if geom_type == "FeatureCollection":
        for feat in geojson.get("features", []):
            rings.extend(_extract_polygon_coords(feat))
        return rings

    if geom_type == "Feature":
        geometry = geojson.get("geometry")
        if geometry is None:
            return rings
        return _extract_polygon_coords(geometry)

    if geom_type == "Polygon":
        # 外周リングのみ（穴は無視）
        rings.append(geojson["coordinates"][0])
    elif geom_type == "MultiPolygon":
        for poly_coords in geojson["coordinates"]:
            rings.append(poly_coords[0])

    return rings


def compact_cells(cells_str: str) -> dict:
    """H3 セルリストをコンパクトにする。"""
    cell_list = [c.strip() for c in cells_str.split(",") if c.strip()]
    for c in cell_list:
        if not h3.is_valid_cell(c):
            raise ValueError(f"無効な H3 セル ID です: '{c}'")
    compacted = sorted(h3.compact_cells(set(cell_list)))
    return {
        "operation": "compact",
        "input_count": len(cell_list),
        "output_count": len(compacted),
        "cells": compacted,
    }


def uncompact_cells(cells_str: str, resolution: int) -> dict:
    """コンパクトされた H3 セルリストを展開する。"""
    cell_list = [c.strip() for c in cells_str.split(",") if c.strip()]
    for c in cell_list:
        if not h3.is_valid_cell(c):
            raise ValueError(f"無効な H3 セル ID です: '{c}'")
    if not (0 <= resolution <= 15):
        raise ValueError("解像度は 0〜15 の範囲で指定してください。")
    uncompacted = sorted(h3.uncompact_cells(set(cell_list), resolution))
    return {
        "operation": "uncompact",
        "input_count": len(cell_list),
        "target_resolution": resolution,
        "output_count": len(uncompacted),
        "cells": uncompacted,
    }


def grid_distance(cell1: str, cell2: str) -> dict:
    """2つの H3 セル間のグリッド距離を計算する。"""
    if not h3.is_valid_cell(cell1):
        raise ValueError(f"無効な H3 セル ID です: '{cell1}'")
    if not h3.is_valid_cell(cell2):
        raise ValueError(f"無効な H3 セル ID です: '{cell2}'")
    res1 = h3.get_resolution(cell1)
    res2 = h3.get_resolution(cell2)
    if res1 != res2:
        raise ValueError(
            f"2つのセルの解像度が異なります（{res1} vs {res2}）。同一解像度で指定してください。"
        )
    distance = h3.grid_distance(cell1, cell2)
    return {
        "operation": "grid_distance",
        "cell1": cell1,
        "cell2": cell2,
        "resolution": res1,
        "grid_distance": distance,
    }


def precision_estimate(meters: float) -> dict:
    """目標メートル精度に最適な H3 解像度を推定する。

    H3_EDGE_LENGTHS テーブルから、平均エッジ長が目標に最も近い解像度を選ぶ。
    """
    if meters <= 0:
        raise ValueError("メートルは正の数を指定してください。")

    best_res = 0
    best_diff = abs(H3_EDGE_LENGTHS[0] - meters)

    for res in range(len(H3_EDGE_LENGTHS)):
        diff = abs(H3_EDGE_LENGTHS[res] - meters)
        if diff < best_diff:
            best_diff = diff
            best_res = res

    return {
        "operation": "precision_estimate",
        "target_meters": meters,
        "recommended_resolution": best_res,
        "average_edge_length_m": H3_EDGE_LENGTHS[best_res],
        "all_resolutions": [
            {"resolution": i, "average_edge_length_m": length}
            for i, length in enumerate(H3_EDGE_LENGTHS)
        ],
    }


def _detect_column(fieldnames: list[str], candidates: set[str]) -> str | None:
    """CSV ヘッダーから候補名に一致する列名を返す。"""
    for name in fieldnames:
        if name.strip().lower() in candidates:
            return name
    return None


def _batch_process(
    input_path: str,
    output_path: str | None,
    operation: str,
    resolution: int,
) -> None:
    """CSV バッチ処理: encode または decode を一括実行する。"""
    with open(input_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])

        if operation == "encode":
            lat_col = _detect_column(fieldnames, LAT_NAMES)
            lon_col = _detect_column(fieldnames, LON_NAMES)
            if not lat_col or not lon_col:
                _error(
                    f"CSV に緯度列 {LAT_NAMES} と経度列 {LON_NAMES} が必要です。"
                    f"検出された列: {fieldnames}"
                )
            results = []
            for row in reader:
                try:
                    lat = float(row[lat_col])
                    lon = float(row[lon_col])
                    info = encode_cell(lat, lon, resolution)
                    results.append({
                        "lat": lat,
                        "lon": lon,
                        "h3_cell": info["cell"],
                        "resolution": resolution,
                        "center_lat": info["center"]["lat"],
                        "center_lon": info["center"]["lon"],
                    })
                except (ValueError, KeyError) as e:
                    results.append({
                        "lat": row.get(lat_col, ""),
                        "lon": row.get(lon_col, ""),
                        "h3_cell": None,
                        "error": str(e),
                    })

        elif operation == "decode":
            h3_col = _detect_column(fieldnames, H3_NAMES)
            if not h3_col:
                _error(
                    f"CSV に H3 セル列 {H3_NAMES} が必要です。"
                    f"検出された列: {fieldnames}"
                )
            results = []
            for row in reader:
                try:
                    cell = row[h3_col].strip()
                    info = decode_cell(cell)
                    results.append({
                        "h3_cell": cell,
                        "resolution": info["resolution"],
                        "lat": info["center"]["lat"],
                        "lon": info["center"]["lon"],
                    })
                except (ValueError, KeyError) as e:
                    results.append({
                        "h3_cell": row.get(h3_col, ""),
                        "lat": None,
                        "lon": None,
                        "error": str(e),
                    })
        else:
            _error(f"--operation は 'encode' または 'decode' を指定してください（指定値: {operation}）")

    if output_path:
        if results:
            out_fields = [k for k in results[0].keys() if k != "error"]
            with open(output_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(results)
            print(json.dumps({
                "status": "success",
                "operation": operation,
                "output_file": output_path,
                "count": len(results),
                "errors": sum(1 for r in results if r.get("error")),
            }, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({
                "status": "success",
                "operation": operation,
                "output_file": output_path,
                "count": 0,
            }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({
            "status": "success",
            "operation": operation,
            "results": results,
        }, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="H3 空間インデックス - エンコード・デコード・K-ring・ポリフィル・コンパクト等"
    )

    # 座標入力
    parser.add_argument("--lat", type=float, default=None, help="緯度 (WGS84)")
    parser.add_argument("--lon", type=float, default=None, help="経度 (WGS84)")
    parser.add_argument("--resolution", type=int, default=9, help="H3 解像度（0〜15、デフォルト: 9）")

    # セル入力
    parser.add_argument("--cell", type=str, default=None, help="H3 セル ID")
    parser.add_argument("--cell2", type=str, default=None, help="2つ目の H3 セル ID（グリッド距離計算用）")

    # 操作フラグ
    parser.add_argument("--k-ring", action="store_true", help="K-ring（k 距離以内の全セル）を取得")
    parser.add_argument("--k", type=int, default=1, help="K-ring の距離 k（デフォルト: 1）")
    parser.add_argument("--parent", action="store_true", help="親セルを取得")
    parser.add_argument("--children", action="store_true", help="子セルを取得")
    parser.add_argument("--boundary", action="store_true", help="セル境界を GeoJSON Polygon で出力")
    parser.add_argument("--polyfill", action="store_true", help="ポリゴンを H3 セルでポリフィル")
    parser.add_argument("--compact", action="store_true", help="H3 セルリストをコンパクトにする")
    parser.add_argument("--uncompact", action="store_true", help="コンパクトされた H3 セルリストを展開")
    parser.add_argument("--grid-distance", action="store_true", help="2つの H3 セル間のグリッド距離")
    parser.add_argument("--precision-estimate", action="store_true", help="メートル精度から推奨 H3 解像度を算出")

    # ポリフィル用
    parser.add_argument("--geojson-file", type=str, default=None, help="GeoJSON ファイルパス（ポリフィル用）")
    parser.add_argument("--max-cells", type=int, default=100000, help="ポリフィルの最大セル数（デフォルト: 100,000）")

    # コンパクト/アンコンパクト用
    parser.add_argument("--cells", type=str, default=None, help="カンマ区切りの H3 セル ID リスト")

    # 精度推定用
    parser.add_argument("--meters", type=float, default=None, help="目標精度（メートル）")

    # CSV バッチ
    parser.add_argument("--input", type=str, default=None, help="入力 CSV ファイルパス")
    parser.add_argument("--output", type=str, default=None, help="出力 CSV ファイルパス")
    parser.add_argument("--operation", type=str, default=None, help="バッチ操作（encode / decode）")

    args = parser.parse_args()

    try:
        # ---- バッチ CSV 処理 ----
        if args.input:
            if not args.operation:
                _error("--input を指定した場合は --operation (encode/decode) も必要です。")
            _batch_process(args.input, args.output, args.operation, args.resolution)
            return

        # ---- 精度推定 ----
        if args.precision_estimate:
            if args.meters is None:
                _error("--precision-estimate には --meters を指定してください。")
            result = precision_estimate(args.meters)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # ---- ポリフィル ----
        if args.polyfill:
            if not args.geojson_file:
                _error("--polyfill には --geojson-file を指定してください。")
            result = polyfill_polygon(args.geojson_file, args.resolution, args.max_cells)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # ---- コンパクト ----
        if args.compact:
            if not args.cells:
                _error("--compact には --cells をカンマ区切りで指定してください。")
            result = compact_cells(args.cells)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # ---- アンコンパクト ----
        if args.uncompact:
            if not args.cells:
                _error("--uncompact には --cells をカンマ区切りで指定してください。")
            result = uncompact_cells(args.cells, args.resolution)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # ---- グリッド距離 ----
        if args.grid_distance:
            if not args.cell or not args.cell2:
                _error("--grid-distance には --cell と --cell2 を指定してください。")
            result = grid_distance(args.cell, args.cell2)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # ---- セル入力が必要な操作 ----
        if args.cell:
            if args.k_ring:
                result = k_ring(args.cell, args.k)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return

            if args.parent:
                result = parent_cell(args.cell, args.resolution)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return

            if args.children:
                result = children_cells(args.cell, args.resolution)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return

            if args.boundary:
                result = boundary_geojson(args.cell)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return

            # デフォルト: デコード
            result = decode_cell(args.cell)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # ---- 緯度経度入力 → エンコード ----
        if args.lat is not None and args.lon is not None:
            if not (-90 <= args.lat <= 90):
                _error("緯度は -90 〜 90 の範囲で指定してください。")
            if not (-180 <= args.lon <= 180):
                _error("経度は -180 〜 180 の範囲で指定してください。")
            if not (0 <= args.resolution <= 15):
                _error("解像度は 0〜15 の範囲で指定してください。")

            result = encode_cell(args.lat, args.lon, args.resolution)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # どの操作にもマッチしなかった場合
        _error(
            "引数が不足しています。--lat/--lon（エンコード）、--cell（デコード）、"
            "--input（バッチ）、--polyfill、--compact、--uncompact、--grid-distance、"
            "--precision-estimate のいずれかを指定してください。"
        )

    except ValueError as e:
        _error(str(e))
    except FileNotFoundError as e:
        _error(f"ファイルが見つかりません: {e}")
    except json.JSONDecodeError as e:
        _error(f"JSON パースエラー: {e}")
    except Exception as e:
        _error(f"処理中にエラーが発生しました: {e}")


if __name__ == "__main__":
    main()
