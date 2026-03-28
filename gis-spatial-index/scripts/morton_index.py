#!/usr/bin/env python3
"""Morton コード（Z-order curve）変換スクリプト - 緯度経度 ↔ Morton コードの相互変換"""

from __future__ import annotations

import argparse
import csv
import json
import sys

LAT_NAMES = {"lat", "latitude", "y", "緯度"}
LON_NAMES = {"lon", "lng", "longitude", "x", "経度"}
CODE_NAMES = {"morton", "code", "z_order", "zorder", "モートン"}


def _spread_bits(v: int) -> int:
    """各ビット間にゼロを挿入してビットを拡散する（インターリーブ用）"""
    v = v & 0xFFFFFFFF
    v = (v | (v << 16)) & 0x0000FFFF0000FFFF
    v = (v | (v << 8))  & 0x00FF00FF00FF00FF
    v = (v | (v << 4))  & 0x0F0F0F0F0F0F0F0F
    v = (v | (v << 2))  & 0x3333333333333333
    v = (v | (v << 1))  & 0x5555555555555555
    return v


def _compact_bits(v: int) -> int:
    """拡散の逆操作: 偶数ビットだけを抽出して詰める"""
    v = v & 0x5555555555555555
    v = (v | (v >> 1))  & 0x3333333333333333
    v = (v | (v >> 2))  & 0x0F0F0F0F0F0F0F0F
    v = (v | (v >> 4))  & 0x00FF00FF00FF00FF
    v = (v | (v >> 8))  & 0x0000FFFF0000FFFF
    v = (v | (v >> 16)) & 0x00000000FFFFFFFF
    return v


def encode(lat: float, lon: float, bits: int = 32) -> dict:
    """緯度経度を Morton コードにエンコードする"""
    max_val = (1 << bits) - 1
    norm_x = int((lon + 180.0) / 360.0 * max_val)
    norm_y = int((lat + 90.0) / 180.0 * max_val)
    morton = _spread_bits(norm_x) | (_spread_bits(norm_y) << 1)
    return {
        "morton_code": morton,
        "bits_per_axis": bits,
        "total_bits": bits * 2,
        "normalized": {"x": norm_x, "y": norm_y},
        "center": {"lat": lat, "lon": lon},
        "input": {"lat": lat, "lon": lon},
    }


def decode(code: int, bits: int = 32) -> dict:
    """Morton コードを緯度経度にデコードする"""
    max_val = (1 << bits) - 1
    norm_x = _compact_bits(code)
    norm_y = _compact_bits(code >> 1)
    lon = norm_x / max_val * 360.0 - 180.0
    lat = norm_y / max_val * 180.0 - 90.0
    return {
        "morton_code": code,
        "bits_per_axis": bits,
        "total_bits": bits * 2,
        "normalized": {"x": norm_x, "y": norm_y},
        "center": {"lat": lat, "lon": lon},
    }


def _detect_columns(header: list[str], names: set[str]) -> int | None:
    """ヘッダーから該当カラムのインデックスを探す"""
    for i, col in enumerate(header):
        if col.strip().lower() in names:
            return i
    return None


def _process_csv(input_path: str, output_path: str | None, operation: str, bits: int) -> None:
    """CSV バッチ処理: encode または decode を一括実行する"""
    with open(input_path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = [r for r in reader if r and any(c.strip() for c in r)]

    results = []
    if operation == "encode":
        lat_idx = _detect_columns(header, LAT_NAMES)
        lon_idx = _detect_columns(header, LON_NAMES)
        if lat_idx is None or lon_idx is None:
            raise ValueError(f"緯度/経度カラムが見つかりません。対応名: 緯度={LAT_NAMES}, 経度={LON_NAMES}")
        for row in rows:
            r = encode(float(row[lat_idx].strip()), float(row[lon_idx].strip()), bits)
            results.append(r)
    else:
        code_idx = _detect_columns(header, CODE_NAMES)
        if code_idx is None:
            raise ValueError(f"Morton コードカラムが見つかりません。対応名: {CODE_NAMES}")
        for row in rows:
            r = decode(int(row[code_idx].strip()), bits)
            results.append(r)

    if output_path:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["morton_code", "lat", "lon"])
            writer.writeheader()
            for r in results:
                writer.writerow({"morton_code": r["morton_code"], "lat": r["center"]["lat"], "lon": r["center"]["lon"]})
        print(json.dumps({"status": "ok", "output_file": output_path, "count": len(results)}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="緯度経度 ↔ Morton コード（Z-order curve）の相互変換")
    parser.add_argument("--lat", type=float, default=None, help="緯度 (WGS84)")
    parser.add_argument("--lon", type=float, default=None, help="経度 (WGS84)")
    parser.add_argument("--code", type=int, default=None, help="Morton コード（整数）")
    parser.add_argument("--bits", type=int, default=32, help="軸あたりのビット数（デフォルト: 32）")
    parser.add_argument("--input", default=None, help="入力CSVファイルパス（バッチ処理用）")
    parser.add_argument("--output", default=None, help="出力CSVファイルパス（省略時は標準出力にJSON）")
    parser.add_argument("--operation", choices=["encode", "decode"], default=None, help="バッチ処理の操作種別")
    args = parser.parse_args()

    try:
        # ビット深度の範囲チェック（_spread_bits が 32 ビットマスクに依存するため）
        if not (1 <= args.bits <= 32):
            raise ValueError("--bits は 1〜32 の範囲で指定してください。")

        # バッチ処理モード
        if args.input:
            if not args.operation:
                raise ValueError("--input 使用時は --operation (encode|decode) を指定してください。")
            _process_csv(args.input, args.output, args.operation, args.bits)
            return

        has_latlon = args.lat is not None and args.lon is not None
        has_code = args.code is not None

        if has_latlon and has_code:
            raise ValueError("--lat/--lon と --code は同時に指定できません。")
        if not has_latlon and not has_code:
            raise ValueError("--lat/--lon または --code のいずれかを指定してください。")

        if has_latlon:
            result = encode(args.lat, args.lon, args.bits)
        else:
            result = decode(args.code, args.bits)

        print(json.dumps(result, ensure_ascii=False, indent=2))

    except FileNotFoundError:
        print(json.dumps({"error": f"ファイルが見つかりません: {args.input}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"変換中にエラーが発生しました: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
