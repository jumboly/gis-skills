# 空間演算リファレンス

## 演算一覧

### ジオメトリ演算

| 演算 | 説明 | shapely メソッド | geopandas メソッド |
|------|------|------------------|-------------------|
| Buffer | ジオメトリから指定距離のバッファ領域を生成 | `geom.buffer(distance)` | `gdf.buffer(distance)` |
| Intersection | 2つのジオメトリの重なり部分 | `a.intersection(b)` | `gpd.overlay(gdf1, gdf2, how="intersection")` |
| Union | 2つのジオメトリの和集合 | `a.union(b)` | `gpd.overlay(gdf1, gdf2, how="union")` |
| Difference | ジオメトリAからBを除いた部分 | `a.difference(b)` | `gpd.overlay(gdf1, gdf2, how="difference")` |
| Symmetric Difference | 重なり部分を除いた和集合 | `a.symmetric_difference(b)` | `gpd.overlay(gdf1, gdf2, how="symmetric_difference")` |
| Convex Hull | 凸包 | `geom.convex_hull` | `gdf.convex_hull` |
| Envelope | 最小外接矩形 | `geom.envelope` | `gdf.envelope` |
| Centroid | 重心 | `geom.centroid` | `gdf.centroid` |
| Simplify | ジオメトリの簡略化 | `geom.simplify(tolerance)` | `gdf.simplify(tolerance)` |

### 空間判定

| 演算 | 説明 | shapely メソッド |
|------|------|------------------|
| Contains | AがBを含む | `a.contains(b)` |
| Within | AがBに含まれる | `a.within(b)` |
| Intersects | AとBが交差する | `a.intersects(b)` |
| Touches | AとBが接する（内部は重ならない） | `a.touches(b)` |
| Crosses | AとBが交差する（線と線、線とポリゴン） | `a.crosses(b)` |
| Overlaps | AとBが部分的に重なる（同じ次元） | `a.overlaps(b)` |
| Disjoint | AとBが離れている | `a.disjoint(b)` |

### 計測

| 演算 | 説明 | メソッド |
|------|------|----------|
| 距離 | 2つのジオメトリ間の最短距離 | `a.distance(b)` |
| 面積 | ポリゴンの面積 | `geom.area` / `gdf.area` |
| 長さ | 線の長さ | `geom.length` / `gdf.length` |

### 空間結合（Spatial Join）

```python
# 点データとポリゴンデータを空間結合
result = gpd.sjoin(points_gdf, polygons_gdf, how="inner", predicate="within")
```

| predicate | 説明 |
|-----------|------|
| `intersects` | 交差するフィーチャを結合（デフォルト） |
| `within` | 左側が右側に含まれるフィーチャを結合 |
| `contains` | 左側が右側を含むフィーチャを結合 |

## 重要な注意点

### 座標参照系（CRS）と距離・面積計算

**地理座標系（EPSG:4326 等）で距離・面積を計算してはいけない。**

- 地理座標系の単位は「度」であり、メートルではない
- `geom.area` は度の二乗を返すため、実際の面積ではない
- 距離・面積計算の前に、適切な投影座標系に変換する必要がある

```python
# 日本のデータなら平面直角座標系に変換してから計測
gdf_projected = gdf.to_crs(epsg=6677)  # 平面直角9系（関東）
area_m2 = gdf_projected.area  # 平方メートル
```

### 測地線距離（pyproj.Geod）

投影変換せずに正確な距離を求めたい場合:
```python
from pyproj import Geod
geod = Geod(ellps="GRS80")
az12, az21, dist = geod.inv(lon1, lat1, lon2, lat2)  # dist はメートル
```

### バッファの注意点

- 地理座標系でバッファを作ると、距離が「度」単位になる
- 正確なメートル単位のバッファには投影座標系を使用する
- `cap_style`: 端点の形状（1=円、2=平ら、3=正方形）
- `join_style`: 角の形状（1=丸、2=マイター、3=ベベル）
- `resolution`: 円の近似に使う四分円あたりのセグメント数（デフォルト16）
