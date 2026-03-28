---
name: gis-spatial-analysis
description: "空間解析スキル。バッファ解析、オーバーレイ（交差・和集合・差分）、距離計算、ポイント・イン・ポリゴン判定、面積計算、空間結合などの空間演算を実行する。ユーザーがバッファ、オーバーレイ、距離計算、ポイントインポリゴン、空間結合、intersection、union、difference、面積、空間解析、最近傍、凸包について言及した場合にこのスキルを使用する。GeoJSON や Shapefile のデータに対する空間的な分析や演算のリクエストでもトリガーする。"
tools: Bash, Read, Write, Glob
---

# 空間解析スキル

## ワークフロー

### Step 1: 入力データの確認

1. 入力ファイルのフォーマットと CRS を確認する
2. 距離・面積計算が必要な場合は、**投影座標系**に変換する（地理座標系のままでは不正確）

```python
import geopandas as gpd
gdf = gpd.read_file("input.geojson")
print(f"CRS: {gdf.crs}")
print(f"ジオメトリ型: {gdf.geom_type.unique()}")
print(f"フィーチャ数: {len(gdf)}")
```

### Step 2: CRS の変換（必要に応じて）

距離・面積を正確に計測するには投影座標系が必要。日本のデータなら平面直角座標系を使用。
対象地域に応じた系番号は `/Users/masa/.claude/skills/gis-coord-transform/references/japanese-plane-rect.md` を参照。

```python
gdf_proj = gdf.to_crs(epsg=6677)  # 例: 平面直角9系（関東）
```

### Step 3: 空間演算の実行

各演算の詳細は `${CLAUDE_SKILL_DIR}/references/spatial-operations.md` を参照。

#### バッファ解析

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/buffer_analysis.py --input data.geojson --distance 500 --epsg 6677 --output buffer.geojson
```

または Python コード:
```python
gdf_proj = gdf.to_crs(epsg=6677)
gdf_proj["geometry"] = gdf_proj.buffer(500)  # 500m バッファ
result = gdf_proj.to_crs(epsg=4326)  # WGS84 に戻す
result.to_file("buffer.geojson", driver="GeoJSON")
```

#### オーバーレイ解析

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/overlay_analysis.py --input1 a.geojson --input2 b.geojson --operation intersection --output result.geojson
```

対応演算: `intersection`, `union`, `difference`, `symmetric_difference`

#### 距離計算

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/distance_calc.py --input1 points.geojson --input2 polygons.geojson --mode nearest --output distances.csv
```

**測地線距離（投影変換なしで正確な距離を求める場合）:**
```python
from pyproj import Geod
geod = Geod(ellps="GRS80")
az12, az21, dist_m = geod.inv(lon1, lat1, lon2, lat2)
```

#### ポイント・イン・ポリゴン

```python
result = gpd.sjoin(points_gdf, polygons_gdf, how="inner", predicate="within")
```

#### 面積・長さ計算

```python
gdf_proj = gdf.to_crs(epsg=6677)
gdf_proj["area_m2"] = gdf_proj.area
gdf_proj["area_ha"] = gdf_proj.area / 10000
```

## リファレンス

- `${CLAUDE_SKILL_DIR}/references/spatial-operations.md` — 空間演算の種類、メソッド一覧、注意事項

## 重要な注意事項

- **地理座標系（EPSG:4326 等）で距離・面積を計算してはいけない。** 必ず投影座標系に変換する
- バッファの距離は投影座標系の単位（通常メートル）で指定する
- CRS が異なるデータ同士のオーバーレイは事前に統一する
- 大量のフィーチャに対する空間結合は spatial index を使って高速化できる（geopandas はデフォルトで使用）
