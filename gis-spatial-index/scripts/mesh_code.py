#!/usr/bin/env python3
"""標準地域メッシュコード空間インデックス - JIS X 0410 準拠のエンコード・デコード・近傍検索・境界ポリゴン等"""
from __future__ import annotations

import argparse
import csv
import json
import sys


# メッシュレベルごとの桁数とサイズ定義
MESH_LEVELS = {
    1: {"digits": 4, "name": "1次メッシュ", "lat_size": 2 / 3, "lon_size": 1.0},
    2: {"digits": 6, "name": "2次メッシュ", "lat_size": 2 / 3 / 8, "lon_size": 1.0 / 8},
    3: {"digits": 8, "name": "3次メッシュ（基準地域メッシュ）", "lat_size": 2 / 3 / 8 / 10, "lon_size": 1.0 / 8 / 10},
    4: {"digits": 9, "name": "1/2地域メッシュ", "lat_size": 2 / 3 / 8 / 10 / 2, "lon_size": 1.0 / 8 / 10 / 2},
    5: {"digits": 10, "name": "1/4地域メッシュ", "lat_size": 2 / 3 / 8 / 10 / 4, "lon_size": 1.0 / 8 / 10 / 4},
    6: {"digits": 11, "name": "1/8地域メッシュ", "lat_size": 2 / 3 / 8 / 10 / 8, "lon_size": 1.0 / 8 / 10 / 8},
}

# 桁数からレベルを逆引き
DIGITS_TO_LEVEL = {v["digits"]: k for k, v in MESH_LEVELS.items()}

# CSV 列名の自動検出用
LAT_NAMES = {"lat", "latitude", "y", "緯度"}
LON_NAMES = {"lon", "lng", "longitude", "x", "経度"}
CODE_NAMES = {"code", "mesh", "mesh_code", "meshcode", "メッシュコード", "メッシュ"}

# メッシュレベル4-6の4分割: 1=南西, 2=南東, 3=北西, 4=北東
# sub_code = lat_half * 2 + lon_half + 1 で計算


def encode(lat: float, lon: float, level: int = 3) -> str:
    """緯度経度からメッシュコードを計算する。"""
    if level not in MESH_LEVELS:
        raise ValueError(f"レベルは 1〜6 で指定してください（指定値: {level}）")

    # 1次メッシュ: 緯度を1.5倍した整数部(2桁) + 経度の100の位を除いた整数部(2桁)
    lat_idx_1 = int(lat * 1.5)
    lon_idx_1 = int(lon) - 100
    code = f"{lat_idx_1:02d}{lon_idx_1:02d}"

    if level == 1:
        return code

    # 2次メッシュ: 1次メッシュ内を8×8分割
    lat_rem = lat * 1.5 - lat_idx_1
    lon_rem = lon - int(lon)
    lat_idx_2 = int(lat_rem * 8)
    lon_idx_2 = int(lon_rem * 8)
    code += f"{lat_idx_2}{lon_idx_2}"

    if level == 2:
        return code

    # 3次メッシュ: 2次メッシュ内を10×10分割
    lat_rem_2 = lat_rem * 8 - lat_idx_2
    lon_rem_2 = lon_rem * 8 - lon_idx_2
    lat_idx_3 = int(lat_rem_2 * 10)
    lon_idx_3 = int(lon_rem_2 * 10)
    code += f"{lat_idx_3}{lon_idx_3}"

    if level == 3:
        return code

    # 1/2メッシュ (レベル4): 3次メッシュ内を2×2分割、1桁(1-4)で表現
    lat_rem_3 = lat_rem_2 * 10 - lat_idx_3
    lon_rem_3 = lon_rem_2 * 10 - lon_idx_3
    lat_half = int(lat_rem_3 * 2)
    lon_half = int(lon_rem_3 * 2)
    sub_code = lat_half * 2 + lon_half + 1
    code += f"{sub_code}"

    if level == 4:
        return code

    # 1/4メッシュ (レベル5): 1/2メッシュ内をさらに2×2分割
    lat_rem_4 = lat_rem_3 * 2 - lat_half
    lon_rem_4 = lon_rem_3 * 2 - lon_half
    lat_quarter = int(lat_rem_4 * 2)
    lon_quarter = int(lon_rem_4 * 2)
    sub_code_2 = lat_quarter * 2 + lon_quarter + 1
    code += f"{sub_code_2}"

    if level == 5:
        return code

    # 1/8メッシュ (レベル6): 1/4メッシュ内をさらに2×2分割
    lat_rem_5 = lat_rem_4 * 2 - lat_quarter
    lon_rem_5 = lon_rem_4 * 2 - lon_quarter
    lat_eighth = int(lat_rem_5 * 2)
    lon_eighth = int(lon_rem_5 * 2)
    sub_code_3 = lat_eighth * 2 + lon_eighth + 1
    code += f"{sub_code_3}"

    return code


def decode(code: str) -> dict:
    """メッシュコードから南西角・北東角の緯度経度を計算する。"""
    code = code.strip()
    length = len(code)

    if length not in DIGITS_TO_LEVEL:
        valid = sorted(DIGITS_TO_LEVEL.keys())
        raise ValueError(
            f"メッシュコードの桁数が不正です（{length}桁）。"
            f"対応桁数: {valid}"
        )

    level = DIGITS_TO_LEVEL[length]

    # 1次メッシュ
    lat_idx_1 = int(code[0:2])
    lon_idx_1 = int(code[2:4])
    sw_lat = lat_idx_1 / 1.5
    sw_lon = lon_idx_1 + 100

    if level >= 2:
        lat_idx_2 = int(code[4])
        lon_idx_2 = int(code[5])
        sw_lat += lat_idx_2 / 1.5 / 8
        sw_lon += lon_idx_2 / 8

    if level >= 3:
        lat_idx_3 = int(code[6])
        lon_idx_3 = int(code[7])
        sw_lat += lat_idx_3 / 1.5 / 8 / 10
        sw_lon += lon_idx_3 / 8 / 10

    if level >= 4:
        sub = int(code[8]) - 1
        lat_half = sub // 2
        lon_half = sub % 2
        sw_lat += lat_half / 1.5 / 8 / 10 / 2
        sw_lon += lon_half / 8 / 10 / 2

    if level >= 5:
        sub = int(code[9]) - 1
        lat_quarter = sub // 2
        lon_quarter = sub % 2
        sw_lat += lat_quarter / 1.5 / 8 / 10 / 4
        sw_lon += lon_quarter / 8 / 10 / 4

    if level >= 6:
        sub = int(code[10]) - 1
        lat_eighth = sub // 2
        lon_eighth = sub % 2
        sw_lat += lat_eighth / 1.5 / 8 / 10 / 8
        sw_lon += lon_eighth / 8 / 10 / 8

    info = MESH_LEVELS[level]
    ne_lat = sw_lat + info["lat_size"]
    ne_lon = sw_lon + info["lon_size"]

    return {
        "code": code,
        "level": level,
        "level_name": info["name"],
        "sw": {"lat": sw_lat, "lon": sw_lon},
        "ne": {"lat": ne_lat, "lon": ne_lon},
        "center": {
            "lat": (sw_lat + ne_lat) / 2,
            "lon": (sw_lon + ne_lon) / 2,
        },
        "bbox": [sw_lon, sw_lat, ne_lon, ne_lat],
        "size": {
            "lat_degrees": info["lat_size"],
            "lon_degrees": info["lon_size"],
        },
    }


def neighbors(code: str) -> dict:
    """8方向の隣接メッシュコードを返す。

    セル中心を基準に、メッシュサイズ分だけ上下左右に移動して再エンコードする。
    日本の範囲外になる場合は None を返す。
    """
    info = decode(code)
    level = info["level"]
    lat_size = info["size"]["lat_degrees"]
    lon_size = info["size"]["lon_degrees"]
    center_lat = info["center"]["lat"]
    center_lon = info["center"]["lon"]

    directions = {
        "n":  (lat_size, 0),
        "ne": (lat_size, lon_size),
        "e":  (0, lon_size),
        "se": (-lat_size, lon_size),
        "s":  (-lat_size, 0),
        "sw": (-lat_size, -lon_size),
        "w":  (0, -lon_size),
        "nw": (lat_size, -lon_size),
    }

    result = {}
    for direction, (dlat, dlon) in directions.items():
        new_lat = center_lat + dlat
        new_lon = center_lon + dlon
        try:
            result[direction] = encode(new_lat, new_lon, level)
        except (ValueError, IndexError):
            # 日本の範囲外
            result[direction] = None

    return result


def get_parent(code: str) -> str | None:
    """親メッシュコードを返す。

    レベル4-6: 末尾1桁を除去して上位レベルに。
    レベル3: 6桁の2次メッシュに（末尾2桁除去）。
    レベル2: 4桁の1次メッシュに（末尾2桁除去）。
    レベル1: 親なし。
    """
    info = decode(code)
    level = info["level"]

    if level == 1:
        return None

    if level <= 3:
        # レベル2→1, レベル3→2: 末尾2桁除去
        return code[:-2]
    else:
        # レベル4-6: 末尾1桁除去
        return code[:-1]


def get_children(code: str) -> list[str]:
    """子メッシュコードのリストを返す。

    レベル1→2: 8×8=64個の子。
    レベル2→3: 10×10=100個の子。
    レベル3→4, 4→5, 5→6: 2×2=4個の子（コード 1-4）。
    レベル6: 子なし。
    """
    info = decode(code)
    level = info["level"]

    if level >= 6:
        return []

    if level == 1:
        # 2次メッシュ: 8×8分割
        return [code + f"{lat}{lon}" for lat in range(8) for lon in range(8)]
    elif level == 2:
        # 3次メッシュ: 10×10分割
        return [code + f"{lat}{lon}" for lat in range(10) for lon in range(10)]
    else:
        # 1/2, 1/4, 1/8メッシュ: 4分割 (1:南西, 2:南東, 3:北西, 4:北東)
        return [code + str(i) for i in range(1, 5)]


def boundary_geojson(code: str) -> dict:
    """メッシュセルの境界を GeoJSON Polygon として返す。"""
    info = decode(code)
    west, south, east, north = info["bbox"]
    return {
        "type": "Feature",
        "properties": {
            "code": code,
            "level": info["level"],
            "level_name": info["level_name"],
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south],
            ]],
        },
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
    level: int,
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
                    mesh = encode(lat, lon, level)
                    info = decode(mesh)
                    results.append({
                        "lat": lat,
                        "lon": lon,
                        "code": mesh,
                        "level": level,
                        "center_lat": info["center"]["lat"],
                        "center_lon": info["center"]["lon"],
                    })
                except (ValueError, KeyError) as e:
                    results.append({
                        "lat": row.get(lat_col, ""),
                        "lon": row.get(lon_col, ""),
                        "code": None,
                        "error": str(e),
                    })

        elif operation == "decode":
            code_col = _detect_column(fieldnames, CODE_NAMES)
            if not code_col:
                _error(
                    f"CSV にメッシュコード列 {CODE_NAMES} が必要です。"
                    f"検出された列: {fieldnames}"
                )
            results = []
            for row in reader:
                try:
                    mesh = row[code_col].strip()
                    info = decode(mesh)
                    results.append({
                        "code": mesh,
                        "level": info["level"],
                        "lat": info["center"]["lat"],
                        "lon": info["center"]["lon"],
                        "bbox_w": info["bbox"][0],
                        "bbox_s": info["bbox"][1],
                        "bbox_e": info["bbox"][2],
                        "bbox_n": info["bbox"][3],
                    })
                except (ValueError, KeyError) as e:
                    results.append({
                        "code": row.get(code_col, ""),
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
        description="標準地域メッシュコード (JIS X 0410) — エンコード・デコード・近傍検索・境界ポリゴン等"
    )

    # 座標入力
    parser.add_argument("--lat", type=float, default=None, help="緯度 (WGS84)")
    parser.add_argument("--lon", type=float, default=None, help="経度 (WGS84)")
    parser.add_argument(
        "--level", type=int, default=3,
        help="メッシュレベル (1:1次, 2:2次, 3:3次, 4:1/2, 5:1/4, 6:1/8)（デフォルト: 3）"
    )

    # メッシュコード入力
    parser.add_argument("--code", type=str, default=None, help="メッシュコード（桁数からレベルを自動判定）")

    # 操作フラグ
    parser.add_argument("--neighbors", action="store_true", help="8方向の隣接メッシュコードを取得")
    parser.add_argument("--parent", action="store_true", help="親メッシュコードを取得")
    parser.add_argument("--children", action="store_true", help="子メッシュコードを取得")
    parser.add_argument("--boundary", action="store_true", help="セル境界を GeoJSON Polygon で出力")

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
            _batch_process(args.input, args.output, args.operation, args.level)
            return

        # ---- メッシュコード入力が必要な操作 ----
        if args.code:
            if args.neighbors:
                nbrs = neighbors(args.code)
                result = {
                    "operation": "neighbors",
                    "code": args.code,
                    "neighbors": nbrs,
                }
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return

            if args.parent:
                p = get_parent(args.code)
                if p is None:
                    _error("1次メッシュ（レベル1）には親がありません。")
                p_info = decode(p)
                result = {
                    "operation": "parent",
                    "code": args.code,
                    "parent": p,
                    "parent_info": p_info,
                }
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return

            if args.children:
                ch = get_children(args.code)
                if not ch:
                    _error("1/8メッシュ（レベル6）には子がありません。")
                result = {
                    "operation": "children",
                    "code": args.code,
                    "count": len(ch),
                    "children": ch,
                }
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return

            if args.boundary:
                result = boundary_geojson(args.code)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return

            # デフォルト: デコード
            result = decode(args.code)
            result["mode"] = "mesh_to_latlon"
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # ---- 緯度経度入力 → エンコード ----
        if args.lat is not None and args.lon is not None:
            if args.level not in MESH_LEVELS:
                _error(f"レベルは 1〜6 で指定してください（指定値: {args.level}）")
            if not (20 <= args.lat <= 46):
                _error("日本の緯度範囲（約20〜46度）外です。")
            if not (122 <= args.lon <= 154):
                _error("日本の経度範囲（約122〜154度）外です。")

            mesh = encode(args.lat, args.lon, args.level)
            result = decode(mesh)
            result["mode"] = "latlon_to_mesh"
            result["input"] = {"lat": args.lat, "lon": args.lon, "level": args.level}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # どの操作にもマッチしなかった場合
        _error(
            "引数が不足しています。--lat/--lon（エンコード）、--code（デコード）、"
            "--input（バッチ）のいずれかを指定してください。"
        )

    except ValueError as e:
        _error(str(e))
    except FileNotFoundError as e:
        _error(f"ファイルが見つかりません: {e}")
    except Exception as e:
        _error(f"処理中にエラーが発生しました: {e}")


if __name__ == "__main__":
    main()
