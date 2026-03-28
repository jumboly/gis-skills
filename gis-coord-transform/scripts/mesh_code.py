#!/usr/bin/env python3
"""地域メッシュコード変換スクリプト - 緯度経度 ↔ JIS X 0410 標準地域メッシュ"""

import argparse
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


def latlon_to_mesh(lat: float, lon: float, level: int) -> str:
    """緯度経度からメッシュコードを計算する"""
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
    # 南西=1, 南東=2, 北西=3, 北東=4
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


def mesh_to_latlon(code: str) -> dict:
    """メッシュコードから南西角・北東角の緯度経度を計算する"""
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
        # 2次メッシュ
        lat_idx_2 = int(code[4])
        lon_idx_2 = int(code[5])
        sw_lat += lat_idx_2 / 1.5 / 8
        sw_lon += lon_idx_2 / 8

    if level >= 3:
        # 3次メッシュ
        lat_idx_3 = int(code[6])
        lon_idx_3 = int(code[7])
        sw_lat += lat_idx_3 / 1.5 / 8 / 10
        sw_lon += lon_idx_3 / 8 / 10

    if level >= 4:
        # 1/2メッシュ
        sub = int(code[8]) - 1  # 0-based
        lat_half = sub // 2
        lon_half = sub % 2
        sw_lat += lat_half / 1.5 / 8 / 10 / 2
        sw_lon += lon_half / 8 / 10 / 2

    if level >= 5:
        # 1/4メッシュ
        sub = int(code[9]) - 1
        lat_quarter = sub // 2
        lon_quarter = sub % 2
        sw_lat += lat_quarter / 1.5 / 8 / 10 / 4
        sw_lon += lon_quarter / 8 / 10 / 4

    if level >= 6:
        # 1/8メッシュ
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


def main():
    parser = argparse.ArgumentParser(
        description="緯度経度 ↔ JIS X 0410 標準地域メッシュコード の相互変換"
    )
    parser.add_argument("--lat", type=float, default=None, help="緯度 (WGS84)")
    parser.add_argument("--lon", type=float, default=None, help="経度 (WGS84)")
    parser.add_argument(
        "--level", type=int, default=None,
        help="メッシュレベル (1:1次, 2:2次, 3:3次, 4:1/2, 5:1/4, 6:1/8)"
    )
    parser.add_argument(
        "--code", type=str, default=None,
        help="メッシュコード（桁数からレベルを自動判定）"
    )
    args = parser.parse_args()

    has_latlon = args.lat is not None and args.lon is not None
    has_code = args.code is not None

    if has_latlon and has_code:
        print(
            json.dumps(
                {"error": "--lat/--lon と --code は同時に指定できません。"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    if not has_latlon and not has_code:
        print(
            json.dumps(
                {"error": "--lat/--lon/--level または --code のいずれかを指定してください。"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        if has_latlon:
            if args.level is None:
                args.level = 3  # デフォルトは3次メッシュ
            if args.level not in MESH_LEVELS:
                raise ValueError(f"レベルは 1〜6 で指定してください（指定値: {args.level}）")
            if not (20 <= args.lat <= 46):
                raise ValueError("日本の緯度範囲（約20〜46度）外です。")
            if not (122 <= args.lon <= 154):
                raise ValueError("日本の経度範囲（約122〜154度）外です。")

            code = latlon_to_mesh(args.lat, args.lon, args.level)
            result = mesh_to_latlon(code)
            result["mode"] = "latlon_to_mesh"
            result["input"] = {"lat": args.lat, "lon": args.lon, "level": args.level}
        else:
            result = mesh_to_latlon(args.code)
            result["mode"] = "mesh_to_latlon"

        print(json.dumps(result, ensure_ascii=False, indent=2))

    except ValueError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"変換中にエラーが発生しました: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
