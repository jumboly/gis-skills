---
name: gis-coord-transform
description: "座標変換・投影法変換・測地系変換・地図数理計算スキル。EPSG コード間の座標変換、WGS84/JGD2000/JGD2011/UTM/平面直角座標系の変換、旧測地系（Tokyo Datum）と新測地系の変換（pyproj 標準変換および TKY2JGD/PatchJGD パラメータファイルによる高精度変換）を行う。また bbox 計算（中心座標+縮尺+ピクセル数→緯度経度範囲）、XYZ タイル座標変換、標準地域メッシュコード変換にも対応。ユーザーが座標変換、投影変換、EPSG、測地系、平面直角座標系、UTMゾーン、WGS84、JGD2011、旧測地系、新測地系、TKY2JGD、PatchJGD、bbox、縮尺計算、タイル座標、メッシュコードについて言及した場合にこのスキルを使用する。"
tools: Bash, Read, Write, Glob
---

# 座標変換・投影法変換・地図数理計算スキル

## 座標変換ワークフロー

### Step 1: 座標系の特定

1. ユーザーの入力から、変換元・変換先の座標系を特定する
2. EPSG コードが不明な場合は `${CLAUDE_SKILL_DIR}/references/common-epsg-codes.md` を参照
3. 日本の平面直角座標系の場合は `${CLAUDE_SKILL_DIR}/references/japanese-plane-rect.md` で系番号と EPSG を確認
4. `${CLAUDE_SKILL_DIR}/scripts/list_systems.py` で座標系を検索することも可能

### Step 2: 変換の実行

#### A. 一般的な座標変換（pyproj）

```python
from pyproj import Transformer

# always_xy=True で (経度, 緯度) の順序を強制
transformer = Transformer.from_crs("EPSG:4326", "EPSG:6677", always_xy=True)
x, y = transformer.transform(lon, lat)
```

**バッチ変換は `scripts/transform_coords.py` を使用:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/transform_coords.py --from-epsg 4326 --to-epsg 6677 --input coords.csv --output result.csv
```

#### B. 測地系変換（旧測地系 ↔ 新測地系）

変換方式の選択は `${CLAUDE_SKILL_DIR}/references/datum-transform.md` を参照。

**pyproj 標準変換（概算、パラメータファイル不要）:**
```python
transformer = Transformer.from_crs("EPSG:4301", "EPSG:6668", always_xy=True)
```

**TKY2JGD パラメータ変換（高精度、.par ファイル必要）:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/datum_transform.py --method tky2jgd --par-file TKY2JGD.par --input coords.csv
```

**PatchJGD 変換（JGD2000 → JGD2011）:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/datum_transform.py --method patchjgd --par-file touhokuchihou2011.par --input coords.csv
```

詳細は `${CLAUDE_SKILL_DIR}/references/datum-transform.md` を参照。

## 地図数理計算

### bbox 計算

中心座標、縮尺、ピクセルサイズから bbox を計算:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/bbox_calc.py --lat 34.7024 --lon 135.4959 --scale 2000 --width 1000 --height 1000
```

計算ロジックの詳細は `${CLAUDE_SKILL_DIR}/references/map-math.md` を参照。

### XYZ タイル座標

緯度経度 ↔ タイル番号の相互変換:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/tile_coords.py --lat 35.6586 --lon 139.7454 --zoom 15
python3 ${CLAUDE_SKILL_DIR}/scripts/tile_coords.py --x 29102 --y 12903 --zoom 15
```

### メッシュコード

緯度経度 ↔ 標準地域メッシュコードの相互変換:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/mesh_code.py --lat 35.6586 --lon 139.7454 --level 3
python3 ${CLAUDE_SKILL_DIR}/scripts/mesh_code.py --code 53394525
```

メッシュコード体系の詳細は `${CLAUDE_SKILL_DIR}/references/map-math.md` を参照。

## 距離・面積の正確な計算

座標変換と密接に関連するため、距離・面積計算のガイドラインをここに記載する。

### 測地線距離（2地点間の正確な距離）

地理座標系 (EPSG:4326) の度数で距離を計算してはいけない。`pyproj.Geod` を使う:

```python
from pyproj import Geod
geod = Geod(ellps="GRS80")  # JGD2011 準拠楕円体
az12, az21, dist_m = geod.inv(lon1, lat1, lon2, lat2)
# dist_m: メートル単位の測地線距離
# az12: 順方位角（度）
```

### 投影座標系での平面距離

平面直角座標系や UTM に投影すれば、ユークリッド距離として計算可能。ただし原点から離れるほど歪みが大きくなる:

```python
import math
from pyproj import Transformer

t = Transformer.from_crs("EPSG:4326", "EPSG:6677", always_xy=True)
x1, y1 = t.transform(lon1, lat1)
x2, y2 = t.transform(lon2, lat2)
dist = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
```

### 使い分け

- **2地点間の距離** → `Geod.inv()` が最も正確（投影歪みなし）
- **面積計算** → 投影座標系に変換してから `gdf.area`。地理座標系のまま計算してはいけない
- **バッファ作成** → 投影座標系でメートル単位で `buffer()` し、WGS84 に戻す

## リファレンス

- `${CLAUDE_SKILL_DIR}/references/japanese-plane-rect.md` — 日本の平面直角座標系19系の定義と EPSG コード
- `${CLAUDE_SKILL_DIR}/references/common-epsg-codes.md` — よく使う EPSG コード一覧と測地系の関係
- `${CLAUDE_SKILL_DIR}/references/datum-transform.md` — 測地系変換ガイド（TKY2JGD/PatchJGD の詳細）
- `${CLAUDE_SKILL_DIR}/references/map-math.md` — 地図数理計算リファレンス（bbox、タイル座標、メッシュコード）

## 注意事項

- pyproj の `Transformer` は `always_xy=True` を指定して (経度, 緯度) の順序を統一する
- 平面直角座標系の座標は (X=北方向, Y=東方向) であることに注意。pyproj は (東, 北) で返す
- TKY2JGD パラメータファイルは国土地理院からダウンロードが必要
- Tokyo Datum → JGD2011 の高精度変換は TKY2JGD → PatchJGD の二段階で実行する
