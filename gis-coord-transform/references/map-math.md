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

## 標準地域メッシュコード

JIS X 0410 に基づく日本の地域メッシュ体系。

### メッシュ区分

| メッシュ | コード桁数 | 緯度幅 | 経度幅 | 辺の長さ（約） |
|----------|-----------|--------|--------|----------------|
| 1次メッシュ | 4桁 | 40′ | 1° | 約 80km |
| 2次メッシュ | 6桁 | 5′ | 7′30″ | 約 10km |
| 3次メッシュ（基準地域メッシュ） | 8桁 | 30″ | 45″ | 約 1km |
| 1/2メッシュ | 9桁 | 15″ | 22.5″ | 約 500m |
| 1/4メッシュ | 10桁 | 7.5″ | 11.25″ | 約 250m |
| 1/8メッシュ | 11桁 | 3.75″ | 5.625″ | 約 125m |

### メッシュコード体系

```
1次メッシュ:  AABB
  AA = 緯度 × 1.5（整数部）
  BB = 経度 - 100（整数部）

2次メッシュ:  AABBCD
  C = 1次メッシュ内の緯度方向分割（0〜7）
  D = 1次メッシュ内の経度方向分割（0〜7）

3次メッシュ:  AABBCDEF
  E = 2次メッシュ内の緯度方向分割（0〜9）
  F = 2次メッシュ内の経度方向分割（0〜9）

1/2メッシュ: AABBCDEFG
  G = 3次メッシュ内の4分割（1:南西, 2:南東, 3:北西, 4:北東）

1/4メッシュ: AABBCDEFGH
  H = 1/2メッシュ内の4分割（同上）

1/8メッシュ: AABBCDEFGHI
  I = 1/4メッシュ内の4分割（同上）
```

### 緯度経度 → メッシュコード

```python
def latlon_to_mesh(lat, lon, level=3):
    """緯度経度から指定レベルのメッシュコードを計算する。"""
    # 1次メッシュ
    lat_a = int(lat * 1.5)
    lon_b = int(lon) - 100
    code = f"{lat_a:02d}{lon_b:02d}"
    if level == 1:
        return code

    # 2次メッシュ
    lat_rem = lat * 1.5 - lat_a
    lon_rem = lon - int(lon)
    lat_c = int(lat_rem * 8)
    lon_d = int(lon_rem * 8)
    code += f"{lat_c}{lon_d}"
    if level == 2:
        return code

    # 3次メッシュ
    lat_rem2 = lat_rem * 8 - lat_c
    lon_rem2 = lon_rem * 8 - lon_d
    lat_e = int(lat_rem2 * 10)
    lon_f = int(lon_rem2 * 10)
    code += f"{lat_e}{lon_f}"
    if level == 3:
        return code

    return code
```

### メッシュコード → 緯度経度（南西角）

```python
def mesh_to_latlon(code):
    """メッシュコードから南西角の緯度経度を返す。"""
    code = str(code)
    lat = int(code[0:2]) / 1.5
    lon = int(code[2:4]) + 100

    if len(code) >= 6:
        lat += int(code[4]) / 12.0
        lon += int(code[5]) / 8.0

    if len(code) >= 8:
        lat += int(code[6]) / 120.0
        lon += int(code[7]) / 80.0

    # 1/2, 1/4, 1/8 メッシュ（Level 4-6）
    # 各レベルで4分割（1:南西, 2:南東, 3:北西, 4:北東）
    # 緯度・経度の刻み幅を半分にしながら再帰的に位置を特定
    lat_size = 1.0 / 120.0   # 3次メッシュの緯度幅（30秒 = 1/120度）
    lon_size = 1.0 / 80.0    # 3次メッシュの経度幅（45秒 = 1/80度）

    for i in range(8, min(len(code), 11)):
        lat_size /= 2.0
        lon_size /= 2.0
        sub = int(code[i])
        # sub: 1=南西, 2=南東, 3=北西, 4=北東
        if sub in (3, 4):  # 北側
            lat += lat_size
        if sub in (2, 4):  # 東側
            lon += lon_size

    return lat, lon
```
