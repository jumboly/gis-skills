#!/usr/bin/env python3
"""Geohash 空間インデックススクリプト - エンコード・デコード・近傍検索・ポリフィル等"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys

# Geohash で使う Base32 アルファベット（a, i, l, o を除く）
BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
# 逆引きテーブル: 文字 → 5ビット値
DECODE_MAP = {c: i for i, c in enumerate(BASE32)}

# CSV 列名の自動検出用
LAT_NAMES = {"lat", "latitude", "y", "緯度"}
LON_NAMES = {"lon", "lng", "longitude", "x", "経度"}
GEOHASH_NAMES = {"geohash", "hash", "ジオハッシュ", "code"}


def encode(lat: float, lon: float, precision: int = 7) -> str:
    """緯度経度を Geohash 文字列にエンコードする。

    交互に経度・緯度のビットを振り分け、5ビットずつ Base32 に変換する。
    """
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]
    geohash = []
    bits = 0
    bit_count = 0
    # 経度(even)と緯度(odd)を交互にビット分割
    is_lon = True

    while len(geohash) < precision:
        if is_lon:
            mid = (lon_range[0] + lon_range[1]) / 2
            if lon >= mid:
                bits = bits * 2 + 1
                lon_range[0] = mid
            else:
                bits = bits * 2
                lon_range[1] = mid
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat >= mid:
                bits = bits * 2 + 1
                lat_range[0] = mid
            else:
                bits = bits * 2
                lat_range[1] = mid

        bit_count += 1
        is_lon = not is_lon

        if bit_count == 5:
            geohash.append(BASE32[bits])
            bits = 0
            bit_count = 0

    return "".join(geohash)


def decode(geohash: str) -> dict:
    """Geohash 文字列をデコードし、中心座標と bbox を返す。

    Base32 → ビット列に変換し、交互に経度・緯度ビットへ振り分ける。
    """
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]
    is_lon = True

    for ch in geohash:
        val = DECODE_MAP.get(ch)
        if val is None:
            raise ValueError(f"不正な Geohash 文字です: '{ch}'")
        # 5ビットを上位から順に処理
        for i in range(4, -1, -1):
            bit = (val >> i) & 1
            if is_lon:
                mid = (lon_range[0] + lon_range[1]) / 2
                if bit == 1:
                    lon_range[0] = mid
                else:
                    lon_range[1] = mid
            else:
                mid = (lat_range[0] + lat_range[1]) / 2
                if bit == 1:
                    lat_range[0] = mid
                else:
                    lat_range[1] = mid
            is_lon = not is_lon

    center_lat = (lat_range[0] + lat_range[1]) / 2
    center_lon = (lon_range[0] + lon_range[1]) / 2

    return {
        "geohash": geohash,
        "precision": len(geohash),
        "center": {"lat": center_lat, "lon": center_lon},
        "bbox": [lon_range[0], lat_range[0], lon_range[1], lat_range[1]],
    }


def _neighbor_in_direction(geohash: str, direction: str) -> str:
    """指定方向の隣接 Geohash を返す。

    末尾文字のビットを方向に応じて調整し、桁上がりが発生したら
    再帰的に上位桁の隣接セルを求める。
    """
    if not geohash:
        return ""

    last_char = geohash[-1]
    parent = geohash[:-1]
    # geohash 全体の長さが奇数なら末尾文字は "odd" 位置
    char_type = "odd" if len(geohash) % 2 == 0 else "even"

    # 方向ごとのオフセット（緯度方向 dlat, 経度方向 dlon）
    direction_map = {
        "n": (1, 0), "s": (-1, 0), "e": (0, 1), "w": (0, -1),
        "ne": (1, 1), "nw": (1, -1), "se": (-1, 1), "sw": (-1, -1),
    }

    # 複合方向は2段階で処理
    if direction in ("ne", "nw", "se", "sw"):
        lat_dir = "n" if direction[0] == "n" else "s"
        lon_dir = direction[1] if len(direction) == 2 else direction[2]
        lon_dir_full = "e" if lon_dir == "e" else "w"
        intermediate = _neighbor_in_direction(geohash, lat_dir)
        return _neighbor_in_direction(intermediate, lon_dir_full)

    # 単純方向（n/s/e/w）の処理
    # Base32 値をグリッド座標に変換して隣接セルを求める
    val = DECODE_MAP[last_char]

    # 偶数文字位置: 経度が先（ビット配置 lon-lat-lon-lat-lon の5ビット）
    # 奇数文字位置: 緯度が先
    if char_type == "even":
        # ビット配置: lon(4) lat(3) lon(2) lat(1) lon(0)
        lon_bits = ((val >> 4) & 1) << 2 | ((val >> 2) & 1) << 1 | (val & 1)
        lat_bits = ((val >> 3) & 1) << 1 | ((val >> 1) & 1)
        lon_size = 8  # 3ビット = 0..7
        lat_size = 4  # 2ビット = 0..3
    else:
        # ビット配置: lat(4) lon(3) lat(2) lon(1) lat(0)
        lat_bits = ((val >> 4) & 1) << 2 | ((val >> 2) & 1) << 1 | (val & 1)
        lon_bits = ((val >> 3) & 1) << 1 | ((val >> 1) & 1)
        lat_size = 8
        lon_size = 4

    dlat, dlon = direction_map[direction]
    new_lat = lat_bits + dlat
    new_lon = lon_bits + dlon

    # 桁上がり・桁下がりの判定
    carry = False
    if new_lat < 0 or new_lat >= lat_size or new_lon < 0 or new_lon >= lon_size:
        carry = True
        new_lat = new_lat % lat_size
        new_lon = new_lon % lon_size

    # ビットを再合成
    if char_type == "even":
        new_val = (
            ((new_lon >> 2) & 1) << 4
            | ((new_lat >> 1) & 1) << 3
            | ((new_lon >> 1) & 1) << 2
            | (new_lat & 1) << 1
            | (new_lon & 1)
        )
    else:
        new_val = (
            ((new_lat >> 2) & 1) << 4
            | ((new_lon >> 1) & 1) << 3
            | ((new_lat >> 1) & 1) << 2
            | (new_lon & 1) << 1
            | (new_lat & 1)
        )

    new_char = BASE32[new_val]

    if carry:
        if not parent:
            # 最上位桁で桁上がり → 世界の端を超えるケース
            return new_char
        parent = _neighbor_in_direction(parent, direction)

    return parent + new_char


def neighbors(geohash: str) -> dict:
    """8方向の隣接 Geohash をすべて返す。"""
    return {d: _neighbor_in_direction(geohash, d) for d in ["n", "ne", "e", "se", "s", "sw", "w", "nw"]}


def parent(geohash: str) -> str:
    """親 Geohash を返す（末尾1文字を除去）。"""
    if len(geohash) <= 1:
        raise ValueError("精度1のジオハッシュには親がありません。")
    return geohash[:-1]


def children(geohash: str) -> list[str]:
    """32個の子 Geohash を返す（各 Base32 文字を末尾に追加）。"""
    return [geohash + c for c in BASE32]


def boundary_geojson(geohash: str) -> dict:
    """Geohash セルの境界を GeoJSON Polygon として返す。"""
    info = decode(geohash)
    west, south, east, north = info["bbox"]
    # RFC 7946: 反時計回りではなく時計回りでもよいが、右手の法則に従う
    return {
        "type": "Feature",
        "properties": {
            "geohash": geohash,
            "precision": len(geohash),
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south],  # 閉じる
            ]],
        },
    }


def _point_in_polygon(px: float, py: float, polygon: list[list[float]]) -> bool:
    """Ray-casting 法によるポイント・イン・ポリゴン判定。

    polygon は [[x, y], ...] のリスト（最初と最後は同じ点で閉じていなくてもよい）。
    """
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        # 辺がテスト点のY座標をまたぐかチェックし、X方向の交差を数える
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _extract_polygon_rings(geojson: dict) -> list[list[list[float]]]:
    """GeoJSON から Polygon/MultiPolygon の外周リングを抽出する。"""
    rings = []
    geom = geojson.get("geometry", geojson)
    if "type" not in geom:
        # FeatureCollection の場合
        if geojson.get("type") == "FeatureCollection":
            for feat in geojson.get("features", []):
                rings.extend(_extract_polygon_rings(feat))
            return rings
        raise ValueError("GeoJSON に geometry が見つかりません。")

    if geom["type"] == "Feature":
        return _extract_polygon_rings(geom)

    if geom["type"] == "Polygon":
        # 外周リングのみ使用（穴は無視）
        rings.append(geom["coordinates"][0])
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            rings.append(poly[0])
    else:
        raise ValueError(f"Polygon または MultiPolygon が必要です（取得: {geom['type']}）")

    return rings


def polyfill(geojson: dict, precision: int, max_cells: int = 100000) -> list[str]:
    """GeoJSON ポリゴンを指定精度の Geohash でポリフィルする。

    バウンディングボックス内の全 Geohash を列挙し、セル中心がポリゴン内にある
    ものだけをフィルタする。
    """
    rings = _extract_polygon_rings(geojson)
    if not rings:
        raise ValueError("ポリゴンが見つかりませんでした。")

    # 全リングの bbox を計算
    all_lons = [pt[0] for ring in rings for pt in ring]
    all_lats = [pt[1] for ring in rings for pt in ring]
    min_lon, max_lon = min(all_lons), max(all_lons)
    min_lat, max_lat = min(all_lats), max(all_lats)

    # bbox の角からセルサイズを推定して列挙
    # まず1つエンコードしてセルサイズを取得
    sample = decode(encode(min_lat, min_lon, precision))
    cell_w = sample["bbox"][2] - sample["bbox"][0]
    cell_h = sample["bbox"][3] - sample["bbox"][1]

    if cell_w <= 0 or cell_h <= 0:
        raise ValueError("セルサイズの計算に失敗しました。")

    # 推定セル数でオーバーフロー防止
    est_cols = math.ceil((max_lon - min_lon) / cell_w) + 2
    est_rows = math.ceil((max_lat - min_lat) / cell_h) + 2
    est_cells = est_cols * est_rows
    if est_cells > max_cells * 10:
        raise ValueError(
            f"推定セル数が多すぎます（約{est_cells:,}セル）。"
            f"精度を下げるか --max-cells を増やしてください。"
        )

    result = []
    # bbox 内を走査
    lat = min_lat
    while lat <= max_lat + cell_h:
        lon = min_lon
        while lon <= max_lon + cell_w:
            gh = encode(lat, lon, precision)
            info = decode(gh)
            cx = info["center"]["lon"]
            cy = info["center"]["lat"]

            # いずれかのリング内にセル中心が含まれればヒット
            for ring in rings:
                if _point_in_polygon(cx, cy, ring):
                    result.append(gh)
                    break

            if len(result) > max_cells:
                raise ValueError(
                    f"セル数が上限 {max_cells:,} を超えました。"
                    f"精度を下げるか --max-cells を増やしてください。"
                )

            lon += cell_w * 0.9  # わずかに重複させて漏れ防止
        lat += cell_h * 0.9

    # 重複排除（走査の重複による）
    seen = set()
    unique = []
    for gh in result:
        if gh not in seen:
            seen.add(gh)
            unique.append(gh)

    return unique


def compact(geohashes: list[str]) -> list[str]:
    """Geohash リストを圧縮する。

    ある親の32個の子がすべて含まれていれば、親に置き換える。再帰的に繰り返す。
    """
    if not geohashes:
        return []

    hash_set = set(geohashes)

    changed = True
    while changed:
        changed = False
        parents_count: dict[str, set[str]] = {}
        for gh in hash_set:
            if len(gh) <= 1:
                continue
            p = gh[:-1]
            if p not in parents_count:
                parents_count[p] = set()
            parents_count[p].add(gh)

        for p, child_set in parents_count.items():
            if len(child_set) == 32:
                # 全32子が揃っている → 親に集約
                hash_set -= child_set
                hash_set.add(p)
                changed = True

    return sorted(hash_set)


def grid_distance(geohash1: str, geohash2: str) -> dict:
    """2つの Geohash 間のグリッド距離（マンハッタン距離）を計算する。

    同一精度に揃えた上で、ビット列からグリッド座標を算出して差を取る。
    """
    p1 = len(geohash1)
    p2 = len(geohash2)
    if p1 != p2:
        raise ValueError(
            f"2つの Geohash の精度が異なります（{p1} vs {p2}）。同一精度で指定してください。"
        )

    def _to_grid(geohash: str) -> tuple[int, int]:
        """Geohash をグリッド座標 (lon_idx, lat_idx) に変換する。"""
        lon_bits = []
        lat_bits = []
        is_lon = True
        for ch in geohash:
            val = DECODE_MAP[ch]
            for i in range(4, -1, -1):
                bit = (val >> i) & 1
                if is_lon:
                    lon_bits.append(bit)
                else:
                    lat_bits.append(bit)
                is_lon = not is_lon

        lon_idx = 0
        for b in lon_bits:
            lon_idx = lon_idx * 2 + b
        lat_idx = 0
        for b in lat_bits:
            lat_idx = lat_idx * 2 + b

        return lon_idx, lat_idx

    x1, y1 = _to_grid(geohash1)
    x2, y2 = _to_grid(geohash2)

    dx = abs(x2 - x1)
    dy = abs(y2 - y1)

    return {
        "geohash1": geohash1,
        "geohash2": geohash2,
        "precision": p1,
        "grid_distance": {"manhattan": dx + dy, "dx": dx, "dy": dy},
    }


def precision_estimate(meters: float) -> dict:
    """指定メートル精度に対して推奨される Geohash 精度レベルを返す。

    赤道付近のセルサイズを基準に推定する。
    """
    # 各精度レベルの赤道付近での概算セルサイズ (幅 x 高さ km)
    # precision: (width_km, height_km)
    size_table = [
        (1, 5000.0, 5000.0),
        (2, 1250.0, 625.0),
        (3, 156.0, 156.0),
        (4, 39.1, 19.5),
        (5, 4.9, 4.9),
        (6, 1.2, 0.61),
        (7, 0.153, 0.153),
        (8, 0.038, 0.019),
        (9, 0.0048, 0.0048),
        (10, 0.0012, 0.0006),
        (11, 0.000149, 0.000149),
        (12, 0.000037, 0.000019),
    ]

    target_km = meters / 1000.0
    recommended = 1

    for prec, w_km, h_km in size_table:
        # セルの長辺が目標精度以下になる最小の precision を推奨
        cell_size = max(w_km, h_km)
        if cell_size <= target_km:
            recommended = prec
            break
    else:
        # どれも条件を満たさなければ最高精度
        recommended = 12

    return {
        "meters": meters,
        "recommended_precision": recommended,
        "cell_size_km": {
            "width": size_table[recommended - 1][1],
            "height": size_table[recommended - 1][2],
        },
        "all_precisions": [
            {
                "precision": p,
                "width_km": w,
                "height_km": h,
            }
            for p, w, h in size_table
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
    precision: int,
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
                    gh = encode(lat, lon, precision)
                    info = decode(gh)
                    results.append({
                        "lat": lat,
                        "lon": lon,
                        "geohash": gh,
                        "precision": precision,
                        "center_lat": info["center"]["lat"],
                        "center_lon": info["center"]["lon"],
                    })
                except (ValueError, KeyError) as e:
                    results.append({
                        "lat": row.get(lat_col, ""),
                        "lon": row.get(lon_col, ""),
                        "geohash": None,
                        "error": str(e),
                    })

        elif operation == "decode":
            gh_col = _detect_column(fieldnames, GEOHASH_NAMES)
            if not gh_col:
                _error(
                    f"CSV に Geohash 列 {GEOHASH_NAMES} が必要です。"
                    f"検出された列: {fieldnames}"
                )
            results = []
            for row in reader:
                try:
                    gh = row[gh_col].strip()
                    info = decode(gh)
                    results.append({
                        "geohash": gh,
                        "lat": info["center"]["lat"],
                        "lon": info["center"]["lon"],
                        "bbox_w": info["bbox"][0],
                        "bbox_s": info["bbox"][1],
                        "bbox_e": info["bbox"][2],
                        "bbox_n": info["bbox"][3],
                    })
                except (ValueError, KeyError) as e:
                    results.append({
                        "geohash": row.get(gh_col, ""),
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


def _error(msg: str) -> None:
    """エラーメッセージを stderr に JSON 出力して終了する。"""
    print(json.dumps({"error": msg}, ensure_ascii=False), file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Geohash 空間インデックス — エンコード・デコード・近傍検索・ポリフィル等"
    )

    # 座標入力
    parser.add_argument("--lat", type=float, default=None, help="緯度 (WGS84)")
    parser.add_argument("--lon", type=float, default=None, help="経度 (WGS84)")
    parser.add_argument("--precision", type=int, default=7, help="Geohash 精度（1〜12、デフォルト: 7）")

    # Geohash 入力
    parser.add_argument("--geohash", type=str, default=None, help="Geohash 文字列")
    parser.add_argument("--geohash2", type=str, default=None, help="2つ目の Geohash（グリッド距離計算用）")

    # 操作フラグ
    parser.add_argument("--neighbors", action="store_true", help="8方向の隣接セルを取得")
    parser.add_argument("--parent", action="store_true", help="親 Geohash を取得")
    parser.add_argument("--children", action="store_true", help="32個の子 Geohash を取得")
    parser.add_argument("--boundary", action="store_true", help="セル境界を GeoJSON Polygon で出力")
    parser.add_argument("--polyfill", action="store_true", help="ポリゴンを Geohash でポリフィル")
    parser.add_argument("--compact", action="store_true", help="Geohash リストを圧縮")
    parser.add_argument("--grid-distance", action="store_true", help="2つの Geohash 間のグリッド距離")
    parser.add_argument("--precision-estimate", action="store_true", help="メートル精度から推奨 Geohash 精度を算出")

    # ポリフィル用
    parser.add_argument("--geojson-file", type=str, default=None, help="GeoJSON ファイルパス（ポリフィル用）")
    parser.add_argument("--max-cells", type=int, default=100000, help="ポリフィルの最大セル数（デフォルト: 100,000）")

    # 圧縮用
    parser.add_argument("--geohashes", type=str, default=None, help="カンマ区切りの Geohash リスト（圧縮用）")

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
            _batch_process(args.input, args.output, args.operation, args.precision)
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
            with open(args.geojson_file, encoding="utf-8") as f:
                geojson_data = json.load(f)
            hashes = polyfill(geojson_data, args.precision, args.max_cells)
            result = {
                "operation": "polyfill",
                "precision": args.precision,
                "count": len(hashes),
                "geohashes": hashes,
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # ---- 圧縮 ----
        if args.compact:
            if not args.geohashes:
                _error("--compact には --geohashes をカンマ区切りで指定してください。")
            hash_list = [h.strip() for h in args.geohashes.split(",") if h.strip()]
            compacted = compact(hash_list)
            result = {
                "operation": "compact",
                "input_count": len(hash_list),
                "output_count": len(compacted),
                "geohashes": compacted,
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # ---- グリッド距離 ----
        if args.grid_distance:
            if not args.geohash or not args.geohash2:
                _error("--grid-distance には --geohash と --geohash2 を指定してください。")
            result = grid_distance(args.geohash, args.geohash2)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # ---- Geohash 入力が必要な操作 ----
        if args.geohash:
            if args.neighbors:
                nbrs = neighbors(args.geohash)
                result = {
                    "operation": "neighbors",
                    "geohash": args.geohash,
                    "neighbors": nbrs,
                }
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return

            if args.parent:
                p = parent(args.geohash)
                p_info = decode(p)
                result = {
                    "operation": "parent",
                    "geohash": args.geohash,
                    "parent": p,
                    "parent_info": p_info,
                }
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return

            if args.children:
                ch = children(args.geohash)
                result = {
                    "operation": "children",
                    "geohash": args.geohash,
                    "count": len(ch),
                    "children": ch,
                }
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return

            if args.boundary:
                result = boundary_geojson(args.geohash)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return

            # デフォルト: デコード
            result = decode(args.geohash)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # ---- 緯度経度入力 → エンコード ----
        if args.lat is not None and args.lon is not None:
            if not (-90 <= args.lat <= 90):
                _error("緯度は -90 〜 90 の範囲で指定してください。")
            if not (-180 <= args.lon <= 180):
                _error("経度は -180 〜 180 の範囲で指定してください。")
            if not (1 <= args.precision <= 12):
                _error("精度は 1〜12 の範囲で指定してください。")

            gh = encode(args.lat, args.lon, args.precision)
            info = decode(gh)
            result = {
                "geohash": gh,
                "precision": args.precision,
                "center": info["center"],
                "bbox": info["bbox"],
                "input": {"lat": args.lat, "lon": args.lon},
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # どの操作にもマッチしなかった場合
        _error(
            "引数が不足しています。--lat/--lon（エンコード）、--geohash（デコード）、"
            "--input（バッチ）、--polyfill、--compact、--grid-distance、"
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
