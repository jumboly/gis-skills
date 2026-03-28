---
name: gis-elevation
description: "標高・DEM タイルスキル。国土地理院（GSI）の標高タイル（DEM）を使用して標高を取得する。5m DEM（航空レーザ測量 dem5a、写真測量 dem5b/dem5c）と 10m DEM の自動フォールバック。単一座標の標高取得、CSV 一括標高付与（バッチ処理）、2点間の標高断面図（プロファイル）データ生成に対応。ユーザーが標高、elevation、高度、altitude、DEM、数値標高モデル、Digital Elevation Model、地理院タイル、GSI DEM、標高タイル、dem5a、dem5b、dem5c、dem10、5mメッシュ、10mメッシュ、標高断面図、elevation profile、断面図、クロスセクション、cross section、標高取得、地形、terrain、起伏、relief、高さ、height、CSV標高、バッチ標高について言及した場合にこのスキルを使用する。"
tools: Bash, Read, Write, Glob
---

# 標高・DEM タイルスキル

## ワークフロー

### Step 1: データソースの確認

国土地理院 DEM タイルの仕様とフォールバック順序を確認する。
`${CLAUDE_SKILL_DIR}/references/gsi-dem-tiles.md` を参照。

**データソース（フォールバック順）:**
1. **dem5a** — 5m DEM（航空レーザ測量）。都市部・主要河川流域。最高精度
2. **dem5b** — 5m DEM（写真測量）。山間部等
3. **dem5c** — 5m DEM（その他）。補完エリア
4. **dem10** — 10m DEM。日本全国カバー

デフォルトでは dem5a → dem5b → dem5c → dem10 の順で試行する。`--source` オプションで特定のソースに限定可能。

### Step 2: 操作の実行

#### A. 単一座標の標高取得

```bash
# 基本的な標高取得（自動フォールバック）
python3 ${CLAUDE_SKILL_DIR}/scripts/elevation.py point --lat 35.3606 --lon 138.7274

# データソースを指定
python3 ${CLAUDE_SKILL_DIR}/scripts/elevation.py --source dem5a point --lat 35.6586 --lon 139.7454
```

出力例:
```json
{
  "lat": 35.3606,
  "lon": 138.7274,
  "elevation": 3773.74,
  "source": "dem5a"
}
```

#### B. CSV 一括標高取得（バッチ処理）

CSV には緯度列（lat/latitude/y/緯度）と経度列（lon/lng/longitude/x/経度）が必要。

```bash
# CSV に標高を付与して出力ファイルに保存
python3 ${CLAUDE_SKILL_DIR}/scripts/elevation.py batch --input points.csv --output result.csv

# stdout に JSON で出力
python3 ${CLAUDE_SKILL_DIR}/scripts/elevation.py batch --input points.csv

# データソースを指定
python3 ${CLAUDE_SKILL_DIR}/scripts/elevation.py --source dem10 batch --input points.csv --output result.csv
```

#### C. 標高断面図データ生成

2点間を等間隔で補間し、各地点の標高と累積距離を出力する。

```bash
# 基本的な断面図（100分割）
python3 ${CLAUDE_SKILL_DIR}/scripts/elevation.py profile \
  --from-lat 35.3606 --from-lon 138.7274 \
  --to-lat 35.3800 --to-lon 138.7500 \
  --steps 50

# データソースを指定
python3 ${CLAUDE_SKILL_DIR}/scripts/elevation.py --source dem10 profile \
  --from-lat 35.6586 --from-lon 139.7454 \
  --to-lat 35.6896 --to-lon 139.6917 \
  --steps 100
```

出力には各地点の `{index, distance, lat, lon, elevation, source}` と統計値 `{total_distance, min_elevation, max_elevation, total_ascent, total_descent}` が含まれる。

## リファレンス

- `${CLAUDE_SKILL_DIR}/references/gsi-dem-tiles.md` — DEM タイル URL パターン、PNG エンコーディング仕様、データセット比較

## 注意事項

- 対応エリアは日本国内のみ（国土地理院タイルの提供範囲）
- 海域・データ未整備エリアでは elevation が null になる
- 5m DEM は全国カバーではない。カバレッジ外では自動的に 10m DEM にフォールバックする
- バッチ処理ではインメモリキャッシュにより同一タイルの重複ダウンロードを回避する
- 大量リクエスト時は地理院タイルの利用規約に留意すること
