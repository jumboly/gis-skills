# 測地系変換ガイド

## 測地系の概要

| 測地系 | 楕円体 | EPSG | 使用期間 |
|--------|--------|------|----------|
| 旧日本測地系（Tokyo Datum） | Bessel 1841 | 4301 | 〜2002年3月 |
| JGD2000（日本測地系2000） | GRS80 | 4612 | 2002年4月〜2011年10月 |
| JGD2011（日本測地系2011） | GRS80 | 6668 | 2011年10月〜現在 |

旧測地系と新測地系では、同一地点で約 400〜450m の座標値の差が生じる。

## 変換方式

### 1. pyproj 標準変換

pyproj の `Transformer` を使った一般的な変換。精度は数メートル程度。

```python
from pyproj import Transformer
transformer = Transformer.from_crs("EPSG:4301", "EPSG:6668", always_xy=True)
lon_new, lat_new = transformer.transform(lon_old, lat_old)
```

### 2. TKY2JGD パラメータ変換（Tokyo Datum → JGD2000）

国土地理院の TKY2JGD パラメータファイル（.par）を使った高精度変換。精度 ~1.4cm。

#### .par ファイルフォーマット

テキスト形式。各行にメッシュコードと変換パラメータを格納。

```
ヘッダ行（バージョン情報等）
メッシュコード  dB(秒)  dL(秒)
メッシュコード  dB(秒)  dL(秒)
...
```

- **メッシュコード**: 3次メッシュコード（8桁の整数）
- **dB**: 緯度の補正量（秒単位）
- **dL**: 経度の補正量（秒単位）

約 380,000 セットのパラメータが含まれる。

#### 変換アルゴリズム（双一次補間）

1. 入力座標を含む3次メッシュを特定
2. メッシュの4隅のパラメータ (dB, dL) を取得
3. メッシュ内の正規化位置 (X, Y) を計算（0〜1）
4. 双一次補間で補正量を算出:
   ```
   dB = a1 + a2*X + a3*Y + a4*X*Y
   dL = b1 + b2*X + b3*Y + b4*X*Y
   ```
5. 入力座標に補正量を加算

#### jgdtrans-py を使った変換

```python
import jgdtrans

# パラメータファイルを読み込み
with open("TKY2JGD.par") as f:
    tf = jgdtrans.load(f, format="TKY2JGD")

# 順変換: Tokyo Datum → JGD2000
origin = jgdtrans.Point(lat=36.103774791666666, lon=140.08785504166664, alt=0)
result = tf.forward(origin)

# 逆変換: JGD2000 → Tokyo Datum
origin_back = tf.backward(result)
```

### 3. PatchJGD パラメータ変換（JGD2000 → JGD2011）

2011年東北地方太平洋沖地震による地殻変動を補正するための変換。

```python
with open("touhokuchihou2011.par") as f:
    tf = jgdtrans.load(f, format="PatchJGD")

result = tf.forward(jgdtrans.Point(lat=38.0, lon=140.0, alt=0))
```

## パラメータファイルのダウンロード先

- **TKY2JGD**: https://www.gsi.go.jp/sokuchikijun/tky2jgd_download.html
- **PatchJGD**: https://vldb.gsi.go.jp/sokuchi/surveycalc/patchjgd/index.html

地域別のパラメータファイルも提供されている（北海道、東北、関東など）。

## 変換方式の選び方

| 条件 | 推奨方式 |
|------|----------|
| 概算で十分（表示用途など） | pyproj 標準変換 |
| 高精度が必要（測量、図面作成） | TKY2JGD / PatchJGD パラメータ |
| Tokyo Datum → JGD2000 | TKY2JGD.par |
| JGD2000 → JGD2011 | PatchJGD.par |
| Tokyo Datum → JGD2011（一括） | TKY2JGD.par → PatchJGD.par の二段階 |
| パラメータファイルがない | pyproj 標準変換 |
