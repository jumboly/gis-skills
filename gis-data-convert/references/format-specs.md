# GIS フォーマット仕様概要

## フォーマット比較

| フォーマット | 拡張子 | マルチレイヤ | CRS保持 | 日本語属性 | ファイル構成 | 最大サイズ目安 |
|-------------|--------|-------------|---------|-----------|-------------|---------------|
| GeoJSON | .geojson, .json | × | △（EPSG:4326前提） | ○（UTF-8） | 単一ファイル | 〜数百MB |
| Shapefile | .shp 他 | × | ○（.prj） | △（要エンコーディング指定） | 複数ファイル | 2GB（.shpの制限） |
| KML | .kml | ○ | △（WGS84固定） | ○（UTF-8） | 単一ファイル | 〜数十MB |
| GeoPackage | .gpkg | ○ | ○ | ○（UTF-8） | 単一ファイル（SQLite） | 制限なし |
| CSV | .csv | × | ×（座標列を指定） | △（エンコーディング依存） | 単一ファイル | 制限なし |

## 各フォーマットの詳細

### GeoJSON

- **仕様**: RFC 7946
- **座標系**: WGS84 (EPSG:4326) が標準。他の CRS を使う場合は `crs` プロパティで指定可能だが非推奨
- **ジオメトリ型**: Point, MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon, GeometryCollection
- **座標順序**: [経度, 緯度]（RFC 7946）
- **読み書き**:
  ```python
  import geopandas as gpd
  gdf = gpd.read_file("data.geojson")
  gdf.to_file("output.geojson", driver="GeoJSON")
  ```
- **純 Python フォールバック**: `json` モジュールで直接読み書き可能

### Shapefile

- **構成ファイル**:
  - `.shp` — ジオメトリデータ（必須）
  - `.dbf` — 属性データ（必須）
  - `.shx` — インデックス（必須）
  - `.prj` — 座標参照系定義（推奨）
  - `.cpg` — エンコーディング定義（任意）
- **制限事項**:
  - フィールド名は最大 10 文字
  - .shp ファイルサイズは最大 2GB
  - NULL 値の扱いが不完全
  - 日付型は Date のみ（DateTime 非対応）
- **日本語エンコーディング**:
  - 多くの日本の Shapefile は cp932（Shift_JIS）
  - .cpg ファイルがあればそれに従う
  - なければ `encoding="cp932"` を試す
  ```python
  gdf = gpd.read_file("data.shp", encoding="cp932")
  gdf.to_file("output.shp", encoding="utf-8")
  ```

### KML（Keyhole Markup Language）

- **座標系**: WGS84 固定（他の座標系は使用不可）
- **特徴**: Google Earth で表示可能、スタイル情報を含む
- **読み書き**:
  ```python
  gdf = gpd.read_file("data.kml", driver="KML")
  gdf.to_file("output.kml", driver="KML")
  ```
- **注意**: fiona で KML を読むには `GDAL_KML_DRIVER=KML` 環境変数が必要な場合がある
- **純 Python フォールバック**: `xml.etree.ElementTree` で基本的な読み書きが可能

### GeoPackage

- **ベース**: SQLite データベース
- **特徴**:
  - マルチレイヤ対応
  - ラスタとベクタの両方を格納可能
  - メタデータ、スタイル情報の格納も可能
  - Shapefile の制限を克服した後継フォーマット
- **読み書き**:
  ```python
  gdf = gpd.read_file("data.gpkg", layer="layer_name")
  gdf.to_file("output.gpkg", layer="layer_name", driver="GPKG")
  ```

### CSV（座標付き）

- **座標列**: 緯度・経度の列名を指定する必要がある
- **一般的な列名**: lat/lng, latitude/longitude, Y/X, 緯度/経度
- **読み込み**:
  ```python
  import pandas as pd
  df = pd.read_csv("data.csv")
  gdf = gpd.GeoDataFrame(
      df,
      geometry=gpd.points_from_xy(df["lng"], df["lat"]),
      crs="EPSG:4326"
  )
  ```
- **エンコーディング**: `encoding="cp932"` or `encoding="utf-8"` を試す

## 変換時の注意事項

### CRS の取り扱い

- GeoJSON: 出力は常に WGS84 にすべき（RFC 7946 準拠）
- Shapefile → GeoJSON: CRS 変換が必要な場合 `gdf.to_crs(epsg=4326)` を実行
- KML: WGS84 固定のため、他の CRS からは変換が必要

### 日本語属性データ

変換時のエンコーディング問題:
1. Shapefile 読み込み時: `encoding="cp932"` を試す
2. 出力時: UTF-8 が推奨（GeoJSON, KML, GeoPackage は UTF-8 が標準）
3. .cpg ファイルの確認: `UTF-8` or `SHIFT_JIS` が記載されている

### Shapefile のフィールド名制限

10文字制限があるため、長いフィールド名は切り詰められる:
```python
# 変換前にフィールド名を短縮する
gdf.columns = [c[:10] if len(c) > 10 else c for c in gdf.columns]
```
