#!/usr/bin/env python3
"""国土地理院 DEM タイルから標高を取得するツール。

5m DEM（dem5a/5b/5c）→ 10m DEM（dem10）の自動フォールバックで標高を取得する。
point（単一座標）、batch（CSV一括）、profile（断面図）の3モードを提供。
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import json
import math
import subprocess
import sys
import warnings

# macOS標準Python (LibreSSL) でのurllib3警告を抑制
warnings.filterwarnings("ignore", message=".*urllib3.*OpenSSL.*")


def _auto_install():
    """未インストールの依存パッケージを自動インストールする"""
    for mod, pkg in {"PIL": "Pillow", "requests": "requests"}.items():
        try:
            __import__(mod)
        except ImportError:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                stdout=subprocess.DEVNULL,
            )


_auto_install()

import requests
from PIL import Image

# ---------------------------------------------------------------------------
# DEM データソース定義（フォールバック順）
# ---------------------------------------------------------------------------
DEM_SOURCES = [
    {"name": "dem5a", "url": "https://cyberjapandata.gsi.go.jp/xyz/dem5a_png/{z}/{x}/{y}.png", "zoom": 15,
     "description": "5m DEM（航空レーザ測量）"},
    {"name": "dem5b", "url": "https://cyberjapandata.gsi.go.jp/xyz/dem5b_png/{z}/{x}/{y}.png", "zoom": 15,
     "description": "5m DEM（写真測量）"},
    {"name": "dem5c", "url": "https://cyberjapandata.gsi.go.jp/xyz/dem5c_png/{z}/{x}/{y}.png", "zoom": 15,
     "description": "5m DEM（写真測量、その他）"},
    {"name": "dem10", "url": "https://cyberjapandata.gsi.go.jp/xyz/dem_png/{z}/{x}/{y}.png", "zoom": 14,
     "description": "10m DEM（全国カバー）"},
]

DEM_SOURCE_NAMES = {s["name"] for s in DEM_SOURCES}

# CSV 列名の自動検出用
LAT_NAMES = {"lat", "latitude", "y", "緯度"}
LON_NAMES = {"lon", "lng", "longitude", "x", "経度"}

TILE_SIZE = 256

# PNG 標高エンコーディングの閾値（地理院タイル仕様）
_NODATA_THRESHOLD = 2 ** 23       # 8388608: nodata を示す RGB 合成値
_NEGATIVE_ELEV_OFFSET = 2 ** 24   # 16777216: 負の標高を復元するオフセット


# ---------------------------------------------------------------------------
# タイル座標計算（gis-coord-transform/scripts/tile_coords.py から移植・拡張）
# ---------------------------------------------------------------------------
def _latlon_to_pixel(lat: float, lon: float, zoom: int) -> tuple[int, int, int, int]:
    """緯度経度からタイル座標 (tx, ty) とタイル内ピクセル座標 (px, py) を返す。"""
    n = 2 ** zoom
    # グローバルピクセル座標
    global_px = (lon + 180.0) / 360.0 * n * TILE_SIZE
    lat_rad = math.radians(lat)
    global_py = (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n * TILE_SIZE

    tx = int(global_px // TILE_SIZE)
    ty = int(global_py // TILE_SIZE)
    px = int(global_px % TILE_SIZE)
    py = int(global_py % TILE_SIZE)

    # タイル範囲クランプ
    max_tile = n - 1
    tx = max(0, min(tx, max_tile))
    ty = max(0, min(ty, max_tile))
    px = max(0, min(px, TILE_SIZE - 1))
    py = max(0, min(py, TILE_SIZE - 1))

    return tx, ty, px, py


# ---------------------------------------------------------------------------
# 標高デコード
# ---------------------------------------------------------------------------
def _decode_elevation(r: int, g: int, b: int) -> float | None:
    """PNG ピクセルの RGB 値から標高 (m) をデコードする。

    地理院タイル仕様:
      x = r * 65536 + g * 256 + b
      x == 2^23 → nodata（海域・データ欠損）
      x < 2^23  → elevation = x * 0.01
      x > 2^23  → elevation = (x - 2^24) * 0.01（負の標高）
    """
    x = r * 65536 + g * 256 + b
    if x == _NODATA_THRESHOLD:
        return None
    if x < _NODATA_THRESHOLD:
        return round(x * 0.01, 2)
    return round((x - _NEGATIVE_ELEV_OFFSET) * 0.01, 2)


# ---------------------------------------------------------------------------
# タイルキャッシュ
# ---------------------------------------------------------------------------
class _TileCache:
    """DEM タイル画像のインメモリキャッシュ。

    同一タイルの重複ダウンロードを回避する（バッチ・断面図処理で有効）。
    404 応答もネガティブキャッシュして再リクエストを防ぐ。
    """

    _SENTINEL = object()

    def __init__(self, maxsize: int = 100):
        self._cache: dict[str, Image.Image | object] = {}
        self._order: collections.deque[str] = collections.deque()
        self._maxsize = maxsize

    def get(self, url: str) -> Image.Image | None:
        """URL からタイル画像を取得する。キャッシュヒット時はそれを返す。

        404 の場合は None を返し、ネガティブキャッシュに記録する。
        """
        if url in self._cache:
            val = self._cache[url]
            return None if val is self._SENTINEL else val

        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 404:
                self._put(url, self._SENTINEL)
                return None
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            self._put(url, img)
            return img
        except requests.RequestException:
            self._put(url, self._SENTINEL)
            return None

    def _put(self, url: str, value: Image.Image | object) -> None:
        if url not in self._cache:
            if len(self._order) >= self._maxsize:
                oldest = self._order.popleft()
                self._cache.pop(oldest, None)
            self._order.append(url)
        self._cache[url] = value


# ---------------------------------------------------------------------------
# 標高取得
# ---------------------------------------------------------------------------
def get_elevation(
    lat: float, lon: float, source: str | None = None, cache: _TileCache | None = None
) -> dict:
    """指定座標の標高を取得する。

    source を指定した場合はそのデータソースのみ使用。
    None の場合は DEM_SOURCES を順に試行してフォールバックする。
    """
    if cache is None:
        cache = _TileCache()

    sources = DEM_SOURCES
    if source:
        sources = [s for s in DEM_SOURCES if s["name"] == source]
        if not sources:
            return {"lat": lat, "lon": lon, "elevation": None, "source": None,
                    "error": f"不明なデータソース: {source}"}

    for src in sources:
        zoom = src["zoom"]
        tx, ty, px, py = _latlon_to_pixel(lat, lon, zoom)
        url = src["url"].format(z=zoom, x=tx, y=ty)
        img = cache.get(url)
        if img is None:
            continue

        r, g, b = img.getpixel((px, py))
        elev = _decode_elevation(r, g, b)
        if elev is not None:
            return {"lat": lat, "lon": lon, "elevation": elev, "source": src["name"]}

    return {"lat": lat, "lon": lon, "elevation": None, "source": None}


# ---------------------------------------------------------------------------
# Haversine 距離計算
# ---------------------------------------------------------------------------
def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """2点間の距離 (m) を Haversine 公式で計算する。"""
    R = 6_371_000  # 地球の平均半径 (m)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# CSV 列名の自動検出
# ---------------------------------------------------------------------------
def _detect_columns(fieldnames: list[str]) -> tuple[str, str]:
    """CSV ヘッダーから緯度・経度列を検出する。"""
    lat_col = lon_col = None
    lower_map = {f.lower(): f for f in fieldnames}
    for name in LAT_NAMES:
        if name in lower_map:
            lat_col = lower_map[name]
            break
    for name in LON_NAMES:
        if name in lower_map:
            lon_col = lower_map[name]
            break
    if not lat_col or not lon_col:
        raise ValueError(
            f"CSV に緯度列 ({'/'.join(sorted(LAT_NAMES))}) と"
            f"経度列 ({'/'.join(sorted(LON_NAMES))}) が必要です。"
            f" 検出された列: {fieldnames}"
        )
    return lat_col, lon_col


# ---------------------------------------------------------------------------
# サブコマンド: point
# ---------------------------------------------------------------------------
def cmd_point(args: argparse.Namespace) -> None:
    """単一座標の標高を取得する。"""
    result = get_elevation(args.lat, args.lon, source=args.source)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["elevation"] is None:
        sys.exit(1)


# ---------------------------------------------------------------------------
# サブコマンド: batch
# ---------------------------------------------------------------------------
def cmd_batch(args: argparse.Namespace) -> None:
    """CSV ファイルの各行に標高を付与する。"""
    cache = _TileCache()
    results = []

    with open(args.input, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        lat_col, lon_col = _detect_columns(list(reader.fieldnames or []))

        for row in reader:
            lat_str = row[lat_col].strip()
            lon_str = row[lon_col].strip()
            if not lat_str or not lon_str:
                row["elevation"] = ""
                row["elevation_source"] = ""
                results.append(row)
                continue

            elev = get_elevation(float(lat_str), float(lon_str), source=args.source, cache=cache)
            row["elevation"] = elev["elevation"] if elev["elevation"] is not None else ""
            row["elevation_source"] = elev["source"] or ""
            results.append(row)

    if not results:
        print(json.dumps({"error": "CSV にデータ行がありません。"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    fieldnames = list(results[0].keys())

    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        succeeded = sum(1 for r in results if r["elevation"] != "")
        print(json.dumps({
            "status": "success",
            "output_file": args.output,
            "count": len(results),
            "succeeded": succeeded,
            "failed": len(results) - succeeded,
        }, ensure_ascii=False, indent=2))
    else:
        # stdout に JSON で出力
        json_results = []
        for r in results:
            json_results.append({
                "lat": r.get(lat_col, ""),
                "lon": r.get(lon_col, ""),
                "elevation": r["elevation"],
                "elevation_source": r["elevation_source"],
            })
        print(json.dumps({"status": "success", "results": json_results}, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# サブコマンド: profile
# ---------------------------------------------------------------------------
def cmd_profile(args: argparse.Namespace) -> None:
    """2点間の標高断面図データを生成する。"""
    cache = _TileCache()
    points = []
    cumulative_dist = 0.0
    prev_lat, prev_lon = args.from_lat, args.from_lon

    for i in range(args.steps + 1):
        t = i / args.steps
        lat = args.from_lat + t * (args.to_lat - args.from_lat)
        lon = args.from_lon + t * (args.to_lon - args.from_lon)

        if i > 0:
            cumulative_dist += _haversine(prev_lat, prev_lon, lat, lon)
        prev_lat, prev_lon = lat, lon

        elev = get_elevation(lat, lon, source=args.source, cache=cache)
        points.append({
            "index": i,
            "distance": round(cumulative_dist, 1),
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "elevation": elev["elevation"],
            "source": elev["source"],
        })

    # 統計値を計算
    elevations = [p["elevation"] for p in points if p["elevation"] is not None]
    total_ascent = 0.0
    total_descent = 0.0
    if len(elevations) >= 2:
        valid_elevs = [p["elevation"] for p in points if p["elevation"] is not None]
        for j in range(1, len(valid_elevs)):
            diff = valid_elevs[j] - valid_elevs[j - 1]
            if diff > 0:
                total_ascent += diff
            else:
                total_descent += abs(diff)

    statistics = {
        "total_distance": round(cumulative_dist, 1),
        "num_points": len(points),
        "valid_elevations": len(elevations),
        "min_elevation": round(min(elevations), 2) if elevations else None,
        "max_elevation": round(max(elevations), 2) if elevations else None,
        "total_ascent": round(total_ascent, 2),
        "total_descent": round(total_descent, 2),
    }

    print(json.dumps({
        "profile": points,
        "statistics": statistics,
    }, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="国土地理院 DEM タイルから標高を取得する"
    )
    parser.add_argument(
        "--source",
        choices=sorted(DEM_SOURCE_NAMES),
        default=None,
        help="データソースを指定（省略時は自動フォールバック: dem5a→5b→5c→dem10）",
    )

    subparsers = parser.add_subparsers(dest="command", help="サブコマンド")

    # point
    p_point = subparsers.add_parser("point", help="単一座標の標高を取得")
    p_point.add_argument("--lat", type=float, required=True, help="緯度 (WGS84)")
    p_point.add_argument("--lon", type=float, required=True, help="経度 (WGS84)")

    # batch
    p_batch = subparsers.add_parser("batch", help="CSV 一括標高取得")
    p_batch.add_argument("--input", required=True, help="入力 CSV ファイルパス")
    p_batch.add_argument("--output", default=None, help="出力 CSV ファイルパス（省略時は stdout に JSON）")

    # profile
    p_profile = subparsers.add_parser("profile", help="2点間の標高断面図データを生成")
    p_profile.add_argument("--from-lat", type=float, required=True, help="始点の緯度")
    p_profile.add_argument("--from-lon", type=float, required=True, help="始点の経度")
    p_profile.add_argument("--to-lat", type=float, required=True, help="終点の緯度")
    p_profile.add_argument("--to-lon", type=float, required=True, help="終点の経度")
    p_profile.add_argument("--steps", type=int, default=100, help="分割数（デフォルト: 100）")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "point":
            cmd_point(args)
        elif args.command == "batch":
            cmd_batch(args)
        elif args.command == "profile":
            cmd_profile(args)
    except ValueError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print(
            json.dumps({"error": f"タイル取得中にネットワークエラーが発生しました: {e}"}, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(
            json.dumps({"error": f"標高取得中にエラーが発生しました: {e}"}, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
