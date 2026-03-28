#!/usr/bin/env python3
"""座標から住所を求める逆ジオコーディングツール。

デフォルトは国土地理院 逆ジオコーディングAPI（日本国内向け、APIキー不要）。
--service nominatim で OpenStreetMap Nominatim（世界対応）に切替可能。
"""
import argparse
import csv
import json
import subprocess
import sys
import time


def _auto_install():
    """未インストールの依存パッケージを自動インストールする"""
    for mod, pkg in {"requests": "requests"}.items():
        try:
            __import__(mod)
        except ImportError:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                stdout=subprocess.DEVNULL,
            )


_auto_install()

import requests


GSI_REVERSE_ENDPOINT = "https://mreversegeocoder.gsi.go.jp/reverse-geocoder/LonLatToAddress"
NOMINATIM_REVERSE_ENDPOINT = "https://nominatim.openstreetmap.org/reverse"

NOMINATIM_DELAY = 1.1


def reverse_geocode_gsi(lat: float, lon: float) -> dict:
    """国土地理院 逆ジオコーディングAPIで住所を求める。"""
    resp = requests.get(
        GSI_REVERSE_ENDPOINT,
        params={"lat": lat, "lon": lon},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", {})
    muniCd = results.get("mupiCd", "") or results.get("muniCd", "")
    lv01Nm = results.get("lv01Nm", "")
    return {
        "lat": lat,
        "lon": lon,
        "address": muniCd + lv01Nm if muniCd else lv01Nm,
        "muniCd": muniCd,
        "lv01Nm": lv01Nm,
    }


def reverse_geocode_nominatim(lat: float, lon: float) -> dict:
    """Nominatim で逆ジオコーディングする。"""
    resp = requests.get(
        NOMINATIM_REVERSE_ENDPOINT,
        params={"lat": lat, "lon": lon, "format": "jsonv2"},
        headers={"User-Agent": "gis-skills-geocoder/1.0"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "lat": lat,
        "lon": lon,
        "address": data.get("display_name", ""),
    }


def main():
    parser = argparse.ArgumentParser(description="座標から住所を求める逆ジオコーディング")
    parser.add_argument("--lat", type=float, help="緯度")
    parser.add_argument("--lon", type=float, help="経度")
    parser.add_argument("--input", help="CSVファイルパス（lat,lon列を含む）")
    parser.add_argument("--output", default=None, help="出力CSVファイルパス（省略時は標準出力にJSON）")
    parser.add_argument(
        "--service",
        choices=["gsi", "nominatim"],
        default="gsi",
        help="逆ジオコーディングサービス（デフォルト: gsi）",
    )
    args = parser.parse_args()

    has_single = args.lat is not None and args.lon is not None
    if not has_single and not args.input:
        print(
            json.dumps({"error": "--lat/--lon または --input を指定してください。"}, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(1)

    if has_single:
        if not (-90 <= args.lat <= 90):
            print(
                json.dumps({"error": "緯度は -90 〜 90 の範囲で指定してください。"}, ensure_ascii=False),
                file=sys.stderr,
            )
            sys.exit(1)
        if not (-180 <= args.lon <= 180):
            print(
                json.dumps({"error": "経度は -180 〜 180 の範囲で指定してください。"}, ensure_ascii=False),
                file=sys.stderr,
            )
            sys.exit(1)

    reverse_fn = reverse_geocode_gsi if args.service == "gsi" else reverse_geocode_nominatim

    try:
        if has_single:
            result = reverse_fn(args.lat, args.lon)
            print(json.dumps({"status": "success", "result": result}, ensure_ascii=False, indent=2))

        elif args.input:
            all_results = []
            with open(args.input, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if "lat" not in reader.fieldnames or "lon" not in reader.fieldnames:
                    print(
                        json.dumps({"error": "CSV に 'lat' と 'lon' 列が必要です。"}, ensure_ascii=False),
                        file=sys.stderr,
                    )
                    sys.exit(1)
                for row in reader:
                    lat = float(row["lat"])
                    lon = float(row["lon"])
                    result = reverse_fn(lat, lon)
                    all_results.append(result)
                    if args.service == "nominatim":
                        time.sleep(NOMINATIM_DELAY)

            if args.output:
                fieldnames = list(all_results[0].keys()) if all_results else ["lat", "lon", "address"]
                with open(args.output, "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(all_results)
                print(json.dumps({
                    "status": "success",
                    "output_file": args.output,
                    "count": len(all_results),
                }, ensure_ascii=False, indent=2))
            else:
                print(json.dumps({"status": "success", "results": all_results}, ensure_ascii=False, indent=2))

    except requests.RequestException as e:
        print(
            json.dumps({"error": f"API リクエストに失敗しました: {e}"}, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(
            json.dumps({"error": f"逆ジオコーディング中にエラーが発生しました: {e}"}, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
