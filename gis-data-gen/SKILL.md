---
name: gis-data-gen
description: "GIS データ生成スキル。GIS データ生成、テストデータ生成、サンプルデータ生成、ダミーデータ生成、GeoJSON 生成、ポイント生成、ライン生成、ポリゴン生成、テスト用データ、フィクスチャ、data generation、generate data、generate GeoJSON、fixture、ランダム座標、ランダムポイント、ランダムライン、ランダムポリゴン、テストデータ、ダミーデータ、サンプルデータ、テスト用座標、テスト用図形、ランダム図形、ランダム点群、ランダム線分、ランダム多角形、Voronoi 分割、ボロノイ、凸包、convex hull、ドーナツポリゴン、穴あきポリゴン、クラスター分布、一様分布、ランダムウォーク、テスト用 GeoJSON、行政界、行政区域、境界ポリゴン、行政境界、boundary、市区町村境界、都道府県境界、mock data、test data、random coordinates、random geometry、random points、random lines、random polygons について言及した場合にこのスキルを使用する。"
tools: Bash, Read, Write, Glob
---

# GIS データ生成スキル

bbox または GeoJSON マスク内にランダムなポイント・ライン・ポリゴンを生成し、GeoJSON FeatureCollection として出力する。

## 共通引数

全スクリプト共通。`--bbox` と `--mask` は排他。

| 引数 | 説明 | デフォルト |
|------|------|-----------|
| `--bbox W S E N` | 矩形範囲（west south east north） | — |
| `--mask FILE` | GeoJSON マスクファイル（Polygon/MultiPolygon） | — |
| `--count N` | 生成数（1〜100,000） | 10 |
| `--seed N` | 乱数シード（再現性確保） | ランダム |
| `--output FILE` | 出力先ファイル | stdout |

都道府県・地方の bbox は `${CLAUDE_SKILL_DIR}/references/region-bbox-table.md` を参照。

## ランダムポイント生成

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/random_points.py \
  --bbox WEST SOUTH EAST NORTH --count N --seed SEED
```

| 引数 | 説明 | デフォルト |
|------|------|-----------|
| `--distribution` | uniform / clustered | uniform |
| `--clusters N` | クラスター数（clustered 時） | 3 |

## ランダムライン生成

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/random_lines.py \
  --bbox WEST SOUTH EAST NORTH --count N --seed SEED
```

| 引数 | 説明 | デフォルト |
|------|------|-----------|
| `--style` | random-walk / straight | random-walk |
| `--vertices-min N` | 最小頂点数（random-walk 時） | 3 |
| `--vertices-max N` | 最大頂点数（random-walk 時） | 10 |

## ランダムポリゴン生成

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/random_polygons.py \
  --bbox WEST SOUTH EAST NORTH --count N --seed SEED
```

| 引数 | 説明 | デフォルト |
|------|------|-----------|
| `--method` | voronoi（隙間なし分割） / convex-hull（独立ポリゴン） | voronoi |
| `--vertices-min N` | 最小頂点数（convex-hull 時） | 5 |
| `--vertices-max N` | 最大頂点数（convex-hull 時） | 12 |
| `--holes` | ドーナツポリゴン（穴あき）を有効化 | 無効 |

## 行政界ポリゴン取得

Overpass API（OpenStreetMap）から行政界ポリゴン���取得する。取得した GeoJSON は `--mask` オプションに渡して使用する。

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_boundary.py \
  --name "渋谷区" --level municipality --output /tmp/mask.geojson
```

| 引数 | 説明 | デフォルト |
|------|------|-----------|
| `--name` | 行政区域名（例: 渋谷区、大阪府） | (必須) |
| `--level` | prefecture / municipality / town | municipality |
| `--output FILE` | 出力先ファイル | stdout |

エラー時（0件・通信障害等）はエラー JSON を stderr に出力して終了する。
