# 国土地理院 DEM タイル仕様

## データセット一覧

| 名称 | レイヤー名 | 解像度 | ズームレベル | カバレッジ | URL パターン |
|------|-----------|--------|-------------|-----------|-------------|
| 5m DEM（航空レーザ） | dem5a_png | 約5m | 15 | 都市部・主要河川流域 | `https://cyberjapandata.gsi.go.jp/xyz/dem5a_png/{z}/{x}/{y}.png` |
| 5m DEM（写真測量） | dem5b_png | 約5m | 15 | 山間部等 | `https://cyberjapandata.gsi.go.jp/xyz/dem5b_png/{z}/{x}/{y}.png` |
| 5m DEM（その他） | dem5c_png | 約5m | 15 | 補完エリア | `https://cyberjapandata.gsi.go.jp/xyz/dem5c_png/{z}/{x}/{y}.png` |
| 10m DEM | dem_png | 約10m | 14 | 日本全国（陸域） | `https://cyberjapandata.gsi.go.jp/xyz/dem_png/{z}/{x}/{y}.png` |

### フォールバック順序

`dem5a` → `dem5b` → `dem5c` → `dem10` の順で試行する。5m DEM は全国をカバーしていないため、404 またはnodata の場合に次のソースへフォールバックする。

## PNG 標高エンコーディング

タイルは 256×256 ピクセルの PNG 画像。各ピクセルの RGB 値から標高を計算する。

### 計算式

```
x = R × 65536 + G × 256 + B

x == 8388608 (2^23)  → nodata（海域・データ欠損）
x <  8388608          → elevation = x × 0.01 (m)
x >  8388608          → elevation = (x - 16777216) × 0.01 (m)  ※負の標高
```

- 分解能: 0.01m
- 正の最大値: 83886.07m（実用上十分）
- 負の最小値: -83886.08m

### nodata の識別

RGB = (128, 0, 0) → x = 8388608 = 2^23 → nodata

海域、データ未整備エリア、ボイド（データ欠損）で返される。

## タイル座標計算

緯度経度からタイル座標およびタイル内ピクセル座標を算出する（Slippy map tilenames 仕様）:

```
n = 2^zoom
global_px = (lon + 180) / 360 × n × 256
global_py = (1 - ln(tan(lat_rad) + 1/cos(lat_rad)) / π) / 2 × n × 256

tile_x = floor(global_px / 256)
tile_y = floor(global_py / 256)
pixel_x = global_px mod 256
pixel_y = global_py mod 256
```

## 利用上の注意

- **利用規約**: 地理院タイルは出典明記の上で自由に利用可能（[利用規約](https://maps.gsi.go.jp/development/ichiran.html)）
- **アクセス頻度**: 大量リクエスト時は適切な間隔を空ける。バッチ処理ではタイルキャッシュで重複リクエストを回避する
- **精度**: 5m DEM は航空レーザ測量由来で精度が高い。10m DEM は等高線からの内挿で、山間部では実際の地形と乖離する場合がある
- **座標系**: タイル座標系は Web Mercator (EPSG:3857) だが、入出力の緯度経度は WGS84 (EPSG:4326)
