# 地図数理計算リファレンス

## bbox 計算（中心座標 + 縮尺 + ピクセルサイズ → 緯度経度範囲）

### 計算手順

1. 画像の物理サイズを求める: `物理サイズ(m) = ピクセル数 × (0.0254 / DPI) × 縮尺`
   - 標準 DPI = 96（Web）、72（印刷プレビュー）、300（印刷）
2. 中心座標から東西南北の地上距離を計算
3. 地上距離を緯度経度の差に変換

### 距離 → 緯度経度差の近似式

```
緯度1度 ≈ 111,320 m（赤道付近。緯度による変動は小さい）
経度1度 ≈ 111,320 × cos(緯度) m
```

より正確には pyproj の Geod を使用:
```python
from pyproj import Geod
geod = Geod(ellps="GRS80")
```

### 計算例

大阪駅（34.7024, 135.4959）を中心に 1/2000、1000×1000px、96DPI:
```
物理幅 = 1000 × (0.0254 / 96) × 2000 = 529.17 m
半幅 = 264.58 m
```

## XYZ タイル座標

### 緯度経度 → タイル番号

```python
import math

def latlon_to_tile(lat, lon, zoom):
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return x, y
```

### タイル番号 → 緯度経度（北西角）

```python
def tile_to_latlon(x, y, zoom):
    n = 2 ** zoom
    lon = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat = math.degrees(lat_rad)
    return lat, lon
```

### タイル番号 → bbox

```python
def tile_to_bbox(x, y, zoom):
    nw_lat, nw_lon = tile_to_latlon(x, y, zoom)
    se_lat, se_lon = tile_to_latlon(x + 1, y + 1, zoom)
    return [nw_lon, se_lat, se_lon, nw_lat]  # [west, south, east, north]
```

### 注意事項

- Web Mercator (EPSG:3857) は高緯度になるほど面積・距離の歪みが大きくなる。北海道（北緯43°付近）では約37%の面積歪みが発生する
- タイル座標と緯度経度を繰り返し相互変換すると丸め誤差が蓄積する
- ズームレベル0〜2ではタイル数が極端に少なく（1〜16枚）、実用的ではない

### 主なタイルサーバ

| サーバ | URL パターン | 最大ズーム |
|--------|-------------|-----------|
| 地理院タイル（標準地図） | `https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png` | 18 |
| 地理院タイル（淡色地図） | `https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png` | 18 |
| 地理院タイル（写真） | `https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg` | 18 |
| OpenStreetMap | `https://tile.openstreetmap.org/{z}/{x}/{y}.png` | 19 |

