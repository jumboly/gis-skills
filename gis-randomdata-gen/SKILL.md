---
name: gis-randomdata-gen
description: "テスト用ランダム GIS データ生成スキル。ランダム座標、ランダムポイント、ランダムライン、ランダムポリゴン、テストデータ、ダミーデータ、サンプルデータ、GeoJSON 生成、テスト用座標、テスト用図形、ランダム図形、ランダム点群、ランダム線分、ランダム多角形、Voronoi 分割、ボロノイ、凸包、convex hull、ドーナツポリゴン、穴あきポリゴン、クラスター分布、グリッド配置、格子点、一様分布、ランダムウォーク、テスト用 GeoJSON、mock data、test data、random coordinates、random geometry、random points、random lines、random polygons について言及した場合にこのスキルを使用する。"
tools: Bash, Read, Write, Glob
---

# テスト用ランダム GIS データ生成スキル

bbox または GeoJSON マスク内にランダムなポイント・ライン・ポリゴンを生成し、GeoJSON FeatureCollection として出力する。

## ワークフロー

### Step 1: 範囲の特定

ユーザーの自然言語指定を以下のパターンに分類し、スクリプトに渡す `--bbox` または `--mask` 引数を決定する。

#### パターン A: 地名 + 距離指定 → `--bbox`

例: 「大阪城付近の 1km 四方」

1. **gis-geocoding** スキルで地名をジオコーディングして中心座標 (lat, lon) を取得
2. 以下の公式で bbox を計算:
   ```
   offset_lat = (距離_m / 2) / 111320
   offset_lon = (距離_m / 2) / (111320 * cos(lat * π / 180))
   bbox = [lon - offset_lon, lat - offset_lat, lon + offset_lon, lat + offset_lat]
   ```

#### パターン B: 地方・都道府県名 → `--bbox`

例: 「近畿地方」「大阪府」

`${CLAUDE_SKILL_DIR}/references/region-bbox-table.md` を参照して bbox を取得する。

#### パターン C: 市区町村境界内 → `--mask`

例: 「渋谷区内」

Overpass API で行政境界ポリゴンを取得し、一時 GeoJSON ファイルとして保存する:

```bash
# Overpass API で市区町村境界を取得する Python コード
python3 -c "
import requests, json
query = '''[out:json][timeout:30];
relation[\"name\"=\"渋谷区\"][\"admin_level\"=\"7\"];
out geom;'''
resp = requests.get('https://overpass-api.de/api/interpreter', params={'data': query})
data = resp.json()
# relation の way メンバーから座標を抽出してポリゴンを構築
coords = []
for member in data['elements'][0].get('members', []):
    if member['type'] == 'way' and member.get('role') == 'outer':
        coords.extend([[p['lon'], p['lat']] for p in member.get('geometry', [])])
if coords:
    geojson = {'type': 'Polygon', 'coordinates': [coords + [coords[0]]]}
    with open('/tmp/mask.geojson', 'w') as f:
        json.dump(geojson, f)
    print('OK')
"
```

※ Overpass API のレスポンス構造は複雑なため、実際には shapely を使ってマルチポリゴンを適切に構築すること。

#### パターン D: 円形範囲 → `--mask`

例: 「東京駅から半径 3km」

1. **gis-geocoding** スキルで中心座標を取得
2. shapely で円ポリゴンを生成:

```bash
python3 -c "
import json, math
from shapely.geometry import Point, mapping
lat, lon, radius_km = 35.6812, 139.7671, 3.0
# 度数に変換
dlat = radius_km / 111.32
dlon = radius_km / (111.32 * math.cos(math.radians(lat)))
# 楕円補正した円を生成
from shapely import affinity
circle = Point(lon, lat).buffer(1, resolution=64)
circle = affinity.scale(circle, xfact=dlon, yfact=dlat)
with open('/tmp/mask.geojson', 'w') as f:
    json.dump(mapping(circle), f)
print('OK')
"
```

#### パターン E: bbox 直接指定 → `--bbox`

例: 「bbox 135.0 34.5 136.0 35.5」

そのまま `--bbox 135.0 34.5 136.0 35.5` に変換。

#### パターン F: GeoJSON/WKT マスク → `--mask`

例: 「この GeoJSON ファイル内に」

ユーザーが提供した GeoJSON ファイルをそのまま `--mask` に渡す。
WKT の場合は shapely で GeoJSON に変換して一時ファイルに保存する。

#### パターン G: バッファー付きライン → `--mask`

例: 「東海道新幹線沿い 500m」

1. ラインデータを取得（Overpass API またはユーザー提供）
2. shapely でバッファを適用して一時 GeoJSON に保存:

```bash
python3 -c "
import json, math
from shapely.geometry import LineString, mapping
# ラインの座標（例）
line = LineString([(139.7671, 35.6812), (135.5023, 34.7025)])
# 500m をおおよその度数に変換
buffer_deg = 0.5 / 111.32
buffered = line.buffer(buffer_deg)
with open('/tmp/mask.geojson', 'w') as f:
    json.dump(mapping(buffered), f)
print('OK')
"
```

### Step 2: ジオメトリ種別とパラメータの決定

ユーザーの要求からジオメトリ種別（ポイント/ライン/ポリゴン）と各パラメータを判断する。

**パラメータ決定のガイドライン:**

- count をユーザーが指定していれば使用する。未指定なら文脈から推定する
- 「市区町村サイズ」→ `${CLAUDE_SKILL_DIR}/references/region-bbox-table.md` のサイズ目安テーブルで count を逆算
- 「ドーナツ」「穴あき」→ `--holes` フラグを有効化
- 「クラスター」「密集」→ `--distribution clustered`
- 「格子」「グリッド」「等間隔」→ `--distribution grid`
- 「折れ線」「曲がった線」→ `--style random-walk`
- 「直線」→ `--style straight`

### Step 3: スクリプトの実行

#### A. ランダムポイント生成

```bash
# 一様分布（デフォルト）
python3 ${CLAUDE_SKILL_DIR}/scripts/random_points.py \
  --bbox WEST SOUTH EAST NORTH --count N --seed SEED

# クラスター分布
python3 ${CLAUDE_SKILL_DIR}/scripts/random_points.py \
  --bbox WEST SOUTH EAST NORTH --count N --seed SEED \
  --distribution clustered --clusters 5 --cluster-spread 0.01

# 格子点（グリッド配置）
python3 ${CLAUDE_SKILL_DIR}/scripts/random_points.py \
  --bbox WEST SOUTH EAST NORTH --count N \
  --distribution grid

# マスク指定
python3 ${CLAUDE_SKILL_DIR}/scripts/random_points.py \
  --mask /tmp/mask.geojson --count N --seed SEED
```

**オプション:**
| 引数 | 説明 | デフォルト |
|------|------|-----------|
| `--bbox W S E N` | 矩形範囲（`--mask` と排他） | — |
| `--mask FILE` | GeoJSON マスクファイル | — |
| `--count N` | 生成数 | 10 |
| `--seed N` | 乱数シード | ランダム |
| `--distribution` | uniform / clustered / grid | uniform |
| `--clusters N` | クラスター数 | 3 |
| `--cluster-spread F` | クラスターの広がり（度数） | bbox幅の10% |
| `--output FILE` | 出力先ファイル | stdout |

#### B. ランダムライン生成

```bash
# ランダムウォーク（デフォルト）
python3 ${CLAUDE_SKILL_DIR}/scripts/random_lines.py \
  --bbox WEST SOUTH EAST NORTH --count N --seed SEED

# 直線
python3 ${CLAUDE_SKILL_DIR}/scripts/random_lines.py \
  --bbox WEST SOUTH EAST NORTH --count N --seed SEED \
  --style straight

# マスク指定
python3 ${CLAUDE_SKILL_DIR}/scripts/random_lines.py \
  --mask /tmp/mask.geojson --count N --seed SEED
```

**オプション:**
| 引数 | 説明 | デフォルト |
|------|------|-----------|
| `--bbox W S E N` | 矩形範囲（`--mask` と排他） | — |
| `--mask FILE` | GeoJSON マスクファイル | — |
| `--count N` | 生成数 | 10 |
| `--seed N` | 乱数シード | ランダム |
| `--style` | random-walk / straight | random-walk |
| `--vertices-min N` | 最小頂点数 | 3 |
| `--vertices-max N` | 最大頂点数 | 10 |
| `--max-segment-km F` | セグメント最大長 (km) | bbox対角線の20% |
| `--output FILE` | 出力先ファイル | stdout |

#### C. ランダムポリゴン生成

```bash
# Voronoi 分割（デフォルト、隙間なし）
python3 ${CLAUDE_SKILL_DIR}/scripts/random_polygons.py \
  --bbox WEST SOUTH EAST NORTH --count N --seed SEED

# Voronoi + ドーナツポリゴン
python3 ${CLAUDE_SKILL_DIR}/scripts/random_polygons.py \
  --bbox WEST SOUTH EAST NORTH --count N --seed SEED \
  --holes --donut-ratio 0.5 --hole-ratio 0.3 --max-holes 3

# 凸包（独立ポリゴン）
python3 ${CLAUDE_SKILL_DIR}/scripts/random_polygons.py \
  --bbox WEST SOUTH EAST NORTH --count N --seed SEED \
  --method convex-hull --vertices-min 5 --vertices-max 12

# マスク指定
python3 ${CLAUDE_SKILL_DIR}/scripts/random_polygons.py \
  --mask /tmp/mask.geojson --count N --seed SEED
```

**オプション:**
| 引数 | 説明 | デフォルト |
|------|------|-----------|
| `--bbox W S E N` | 矩形範囲（`--mask` と排他） | — |
| `--mask FILE` | GeoJSON マスクファイル | — |
| `--count N` | 生成数 | 10 |
| `--seed N` | 乱数シード | ランダム |
| `--method` | voronoi / convex-hull | voronoi |
| `--vertices-min N` | convex-hull: 最小頂点数 | 5 |
| `--vertices-max N` | convex-hull: 最大頂点数 | 12 |
| `--holes` | ドーナツポリゴンを有効化 | 無効 |
| `--max-holes N` | 1ポリゴンあたりの最大穴数 | 3 |
| `--hole-ratio F` | 穴の面積比 | 0.3 |
| `--donut-ratio F` | 穴あきにするポリゴンの割合 | 0.5 |
| `--output FILE` | 出力先ファイル | stdout |

### Step 4: 結果の出力

- `--output` 指定時はファイルに保存し、パスを表示
- 未指定時は stdout に GeoJSON を出力
- seed は metadata に記録されるため、同じ seed で再実行すれば同じ結果が得られる

出力形式（GeoJSON FeatureCollection）:
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "Point", "coordinates": [135.5, 34.7]},
      "properties": {"id": 1}
    }
  ],
  "metadata": {
    "bbox": [135.0, 34.5, 136.0, 35.5],
    "count": 100,
    "seed": 42,
    "generator": "random_points",
    "parameters": {"distribution": "uniform"}
  }
}
```
