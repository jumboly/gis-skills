---
name: gis-data-convert
description: "GISデータ変換スキル。GeoJSON、Shapefile、KML、GeoPackage、CSV（座標付き）間のフォーマット変換を行う。ユーザーがGISファイルの変換、フォーマット変換、Shapefile から GeoJSON、KML 変換、GeoPackage、CSVから空間データへの変換、ファイル形式の判定について言及した場合にこのスキルを使用する。'convert shapefile' や 'GeoJSONに変換' のようなリクエストでもトリガーする。"
tools: Bash, Read, Write, Glob
---

# GIS データ変換スキル

## 注意: GDAL

`fiona` / `GDAL` の自動インストールに失敗する場合は、OS に応じた方法で GDAL を先にインストールする:
- **macOS**: `brew install gdal`
- **Linux (Debian/Ubuntu)**: `sudo apt install gdal-bin libgdal-dev`
- **Linux (Fedora/RHEL)**: `sudo dnf install gdal gdal-devel`
- **Windows**: `conda install -c conda-forge gdal`（推奨）

GeoJSON / CSV 間の変換は GDAL がなくても純 Python フォールバックで動作する。

## ワークフロー

### Step 1: 入力ファイルの確認

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/detect_format.py --input data.shp
```

出力例:
```json
{
  "format": "ESRI Shapefile",
  "crs": "EPSG:4326",
  "features": 1234,
  "geometry_type": "Polygon",
  "encoding": "cp932",
  "fields": ["name", "area", "code"]
}
```

### Step 2: 変換の実行

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/convert_format.py --input data.shp --output data.geojson
```

オプション:
- `--input-encoding cp932` — 入力ファイルのエンコーディング指定
- `--output-crs EPSG:4326` — 出力の CRS を変換
- `--csv-lat lat --csv-lon lng` — CSV の座標列名を指定
- `--csv-crs EPSG:4326` — CSV の座標系を指定

### 変換パターン別の注意事項

#### Shapefile → GeoJSON

```python
import geopandas as gpd
gdf = gpd.read_file("data.shp", encoding="cp932")
gdf = gdf.to_crs(epsg=4326)  # GeoJSON は WGS84 が標準
gdf.to_file("data.geojson", driver="GeoJSON")
```

- .cpg ファイルがあればエンコーディングはそれに従う
- なければ `cp932` を試し、ダメなら `utf-8`

#### GeoJSON → Shapefile

```python
gdf = gpd.read_file("data.geojson")
gdf.to_file("data.shp", encoding="utf-8")
```

- フィールド名が 10 文字を超える場合は切り詰められる（警告を出す）
- .shp ファイルは 2GB 制限がある

#### CSV → GeoJSON

```python
import pandas as pd
import geopandas as gpd

df = pd.read_csv("data.csv", encoding="utf-8")
gdf = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df["lng"], df["lat"]),
    crs="EPSG:4326"
)
gdf.to_file("data.geojson", driver="GeoJSON")
```

**純 Python フォールバック（geopandas なし）:**
```python
import csv, json

with open("data.csv") as f:
    reader = csv.DictReader(f)
    features = []
    for row in reader:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(row["lng"]), float(row["lat"])]
            },
            "properties": {k: v for k, v in row.items() if k not in ("lat", "lng")}
        })

geojson = {"type": "FeatureCollection", "features": features}
with open("data.geojson", "w") as f:
    json.dump(geojson, f, ensure_ascii=False, indent=2)
```

#### GeoJSON / Shapefile → KML

```python
gdf = gpd.read_file("data.geojson")
gdf = gdf.to_crs(epsg=4326)  # KML は WGS84 固定
gdf.to_file("data.kml", driver="KML")
```

#### GeoJSON / Shapefile → GeoPackage

```python
gdf = gpd.read_file("data.geojson")
gdf.to_file("data.gpkg", layer="layer_name", driver="GPKG")
```

GeoPackage はマルチレイヤ対応:
```python
gdf1.to_file("data.gpkg", layer="buildings", driver="GPKG")
gdf2.to_file("data.gpkg", layer="roads", driver="GPKG", mode="a")  # 追加
```

## リファレンス

- `${CLAUDE_SKILL_DIR}/references/format-specs.md` — 各フォーマットの仕様、制限事項、エンコーディング

## 重要な注意事項

- GeoJSON 出力は WGS84 (EPSG:4326) にすべき（RFC 7946 準拠）
- Shapefile の日本語属性は cp932 エンコーディングが多い
- Shapefile のフィールド名は最大 10 文字
- KML は WGS84 固定、他の座標系からは変換が必要
- 大きなファイルの場合はメモリ使用量に注意（fiona でストリーミング読み込みを検討）
