#!/usr/bin/env python3
"""地名・住所・ランドマークから座標を求めるジオコーディングツール。

デフォルトは国土地理院 地名検索API（日本国内向け、APIキー不要）。
--service nominatim で OpenStreetMap Nominatim（世界対応）に切替可能。
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
import warnings

# macOS標準Python (LibreSSL) でのurllib3警告を抑制
warnings.filterwarnings("ignore", message=".*urllib3.*OpenSSL.*")


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


GSI_ENDPOINT = "https://msearch.gsi.go.jp/address-search/AddressSearch"
NOMINATIM_ENDPOINT = "https://nominatim.openstreetmap.org/search"

# Nominatim 利用規約: 1リクエスト/秒以下
NOMINATIM_DELAY = 1.1
# GSI バッチ処理時の推奨間隔
GSI_DELAY = 0.5


def _gsi_relevance(name: str, query: str) -> tuple[int, int]:
    """GSI結果の関連度スコアを返す（小さいほど高関連）。

    APIは部分一致で大量の結果を返すため、クエリとの一致度で並び替える。
    タプル(一致度, 名前長)で返し、同スコア時は短い名前を優先する。
    """
    if name == query:
        return (0, len(name))
    if name.startswith(query):
        return (1, len(name))
    if query in name:
        return (2, len(name))
    # 逆方向: クエリが結果名を含む場合（例: query="東京駅前" → name="東京駅"）
    if name in query:
        return (2, len(name))
    return (3, len(name))


def geocode_gsi(query: str) -> list[dict]:
    """国土地理院 地名検索APIでジオコーディングする。"""
    resp = requests.get(GSI_ENDPOINT, params={"q": query}, timeout=10)
    resp.raise_for_status()
    results = []
    for item in resp.json():
        lon, lat = item["geometry"]["coordinates"]
        results.append({
            "query": query,
            "name": item["properties"]["title"],
            "lat": lat,
            "lon": lon,
        })
    results.sort(key=lambda r: _gsi_relevance(r["name"], query))
    return results


def geocode_nominatim(query: str) -> list[dict]:
    """Nominatim でジオコーディングする。"""
    resp = requests.get(
        NOMINATIM_ENDPOINT,
        params={"q": query, "format": "jsonv2", "limit": 5},
        headers={"User-Agent": "gis-skills-geocoder/1.0"},
        timeout=10,
    )
    resp.raise_for_status()
    results = []
    for item in resp.json():
        results.append({
            "query": query,
            "name": item.get("display_name", ""),
            "lat": float(item["lat"]),
            "lon": float(item["lon"]),
        })
    return results


def main():
    parser = argparse.ArgumentParser(description="地名・住所から座標を求める")
    parser.add_argument("--query", help="検索クエリ（地名・住所・ランドマーク）")
    parser.add_argument("--input", help="CSVファイルパス（query列を含む）")
    parser.add_argument("--output", default=None, help="出力CSVファイルパス（省略時は標準出力にJSON）")
    parser.add_argument(
        "--service",
        choices=["gsi", "nominatim"],
        default="gsi",
        help="ジオコーディングサービス（デフォルト: gsi）",
    )
    parser.add_argument("--all-results", action="store_true", help="全候補を返す（デフォルトは最上位1件）")
    args = parser.parse_args()

    if not args.query and not args.input:
        print(
            json.dumps({"error": "--query または --input を指定してください。"}, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(1)

    geocode_fn = geocode_gsi if args.service == "gsi" else geocode_nominatim

    try:
        if args.query:
            results = geocode_fn(args.query)
            if not results:
                print(
                    json.dumps({"error": f"該当する結果が見つかりませんでした: {args.query}"}, ensure_ascii=False),
                    file=sys.stderr,
                )
                sys.exit(1)
            if not args.all_results:
                results = results[:1]
            print(json.dumps({"status": "success", "results": results}, ensure_ascii=False, indent=2))

        elif args.input:
            all_results = []
            with open(args.input, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                if "query" not in reader.fieldnames:
                    print(
                        json.dumps({"error": "CSV に 'query' 列が必要です。"}, ensure_ascii=False),
                        file=sys.stderr,
                    )
                    sys.exit(1)
                for row in reader:
                    q = row["query"].strip()
                    if not q:
                        continue
                    hits = geocode_fn(q)
                    if hits:
                        all_results.append(hits[0])
                    else:
                        all_results.append({"query": q, "name": None, "lat": None, "lon": None})
                    delay = NOMINATIM_DELAY if args.service == "nominatim" else GSI_DELAY
                    time.sleep(delay)

            if args.output:
                with open(args.output, "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=["query", "name", "lat", "lon"])
                    writer.writeheader()
                    writer.writerows(all_results)
                print(json.dumps({
                    "status": "success",
                    "output_file": args.output,
                    "count": len(all_results),
                    "failed": sum(1 for r in all_results if r["lat"] is None),
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
            json.dumps({"error": f"ジオコーディング中にエラーが発生しました: {e}"}, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
