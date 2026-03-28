---
name: gis-spatial-index
description: "空間インデックス・位置エンコーディングスキル。Geohash（ジオハッシュ）、H3（Uber H3、六角形グリッド）、Plus Code（Open Location Code、OLC、プラスコード）、Quadkey（クアッドキー、Bing Maps タイルキー）、MGRS（Military Grid Reference System、軍用グリッド座標）、Maidenhead（メイデンヘッド、グリッドロケーター、アマチュア無線）、Morton code（モートンコード、Z-order curve、空間充填曲線）の7種の空間インデックスシステムに対応。エンコード（座標→コード）、デコード（コード→座標）、近傍セル検索、親子セル、セル境界ポリゴン取得、ポリフィル、コンパクト、グリッド距離、精度推定、CSV一括変換（バッチ処理）を提供。ユーザーが空間インデックス、空間コード、グリッドシステム、セルID、geohash、h3、hex、hexagon、plus code、open location code、quadkey、quadtree、mgrs、military grid、maidenhead、grid locator、morton、z-order、空間充填曲線、エンコード、デコード、近傍、neighbor、polyfill、compact、空間検索、位置コードについて言及した場合にこのスキルを使用する。"
tools: Bash, Read, Write, Glob
---

# 空間インデックス・位置エンコーディングスキル

## ワークフロー

### Step 1: システムの選択

ユーザーの要件に基づき、適切な空間インデックスシステムを選択する。
`${CLAUDE_SKILL_DIR}/references/spatial-index-systems.md` を参照して、比較表・選択ガイドを確認する。

**簡易選択ガイド:**
- DB空間インデックス (Elasticsearch/DynamoDB/Redis) → **Geohash**
- データエンジニアリング (BigQuery/Snowflake/Databricks) → **H3**
- 人間可読な位置コード (Google Maps共有) → **Plus Code**
- Web地図タイルキャッシュ (Bing Maps/CARTO) → **Quadkey**
- 防災・捜索救助・軍事 → **MGRS**
- アマチュア無線 → **Maidenhead**
- 空間ソートキー・空間充填曲線 → **Morton code**

### Step 2: 操作の実行

#### A. Geohash

矩形グリッドの空間インデックス。prefix でレンジクエリ可能。純Python実装（外部ライブラリ不要）。

```bash
# エンコード (緯度経度 → Geohash)
python3 ${CLAUDE_SKILL_DIR}/scripts/geohash_index.py --lat 35.6586 --lon 139.7454 --precision 7

# デコード (Geohash → 緯度経度・bbox)
python3 ${CLAUDE_SKILL_DIR}/scripts/geohash_index.py --geohash xn76urx

# 隣接セル (8方向)
python3 ${CLAUDE_SKILL_DIR}/scripts/geohash_index.py --neighbors --geohash xn76urx

# 親セル
python3 ${CLAUDE_SKILL_DIR}/scripts/geohash_index.py --parent --geohash xn76urx

# 子セル (32個)
python3 ${CLAUDE_SKILL_DIR}/scripts/geohash_index.py --children --geohash xn76urx

# セル境界 (GeoJSON)
python3 ${CLAUDE_SKILL_DIR}/scripts/geohash_index.py --boundary --geohash xn76urx

# ポリゴン内のGeohash一覧 (polyfill)
python3 ${CLAUDE_SKILL_DIR}/scripts/geohash_index.py --polyfill --geojson-file polygon.geojson --precision 6

# Geohash集合のコンパクト化
python3 ${CLAUDE_SKILL_DIR}/scripts/geohash_index.py --compact --geohashes "xn76ur0,xn76ur1,...,xn76urz"

# グリッド距離
python3 ${CLAUDE_SKILL_DIR}/scripts/geohash_index.py --grid-distance --geohash xn76urx --geohash2 xn76ury

# 目標サイズ(m)から推奨precision
python3 ${CLAUDE_SKILL_DIR}/scripts/geohash_index.py --precision-estimate --meters 100

# CSV一括変換
python3 ${CLAUDE_SKILL_DIR}/scripts/geohash_index.py --input coords.csv --operation encode --precision 7
python3 ${CLAUDE_SKILL_DIR}/scripts/geohash_index.py --input hashes.csv --operation decode
```

#### B. H3

Uber の六角形階層グリッドシステム。均一な面積と良好な近傍性が特徴。

```bash
# エンコード
python3 ${CLAUDE_SKILL_DIR}/scripts/h3_index.py --lat 35.6586 --lon 139.7454 --resolution 9

# デコード
python3 ${CLAUDE_SKILL_DIR}/scripts/h3_index.py --cell 892f5aab2dbffff

# k-ring (近傍セル)
python3 ${CLAUDE_SKILL_DIR}/scripts/h3_index.py --k-ring --cell 892f5aab2dbffff --k 1

# 親セル
python3 ${CLAUDE_SKILL_DIR}/scripts/h3_index.py --parent --cell 892f5aab2dbffff --resolution 7

# 子セル
python3 ${CLAUDE_SKILL_DIR}/scripts/h3_index.py --children --cell 872f5aab2ffffff --resolution 9

# セル境界 (GeoJSON)
python3 ${CLAUDE_SKILL_DIR}/scripts/h3_index.py --boundary --cell 892f5aab2dbffff

# ポリフィル
python3 ${CLAUDE_SKILL_DIR}/scripts/h3_index.py --polyfill --geojson-file polygon.geojson --resolution 9

# コンパクト / アンコンパクト
python3 ${CLAUDE_SKILL_DIR}/scripts/h3_index.py --compact --cells "892f5aab2dbffff,892f5aab2d3ffff"
python3 ${CLAUDE_SKILL_DIR}/scripts/h3_index.py --uncompact --cells "872f5aab2ffffff" --resolution 9

# グリッド距離
python3 ${CLAUDE_SKILL_DIR}/scripts/h3_index.py --grid-distance --cell 892f5aab2dbffff --cell2 892f5aab2d3ffff

# 目標サイズ(m)→推奨resolution
python3 ${CLAUDE_SKILL_DIR}/scripts/h3_index.py --precision-estimate --meters 100

# CSV一括変換
python3 ${CLAUDE_SKILL_DIR}/scripts/h3_index.py --input coords.csv --operation encode --resolution 9
```

#### C. Plus Code (Open Location Code)

Google が開発した人間可読な位置コード。住所がない場所でも位置を共有できる。

```bash
# エンコード
python3 ${CLAUDE_SKILL_DIR}/scripts/pluscode_index.py --lat 35.6586 --lon 139.7454 --length 10

# デコード
python3 ${CLAUDE_SKILL_DIR}/scripts/pluscode_index.py --code 8Q7XMM5G+QV

# セル境界 (GeoJSON)
python3 ${CLAUDE_SKILL_DIR}/scripts/pluscode_index.py --boundary --code 8Q7XMM5G+QV

# CSV一括変換
python3 ${CLAUDE_SKILL_DIR}/scripts/pluscode_index.py --input coords.csv --operation encode --length 10
```

#### D. Quadkey

Microsoft Bing Maps のタイルキーシステム。XYZ タイル座標と1:1対応。

```bash
# エンコード (緯度経度 → Quadkey)
python3 ${CLAUDE_SKILL_DIR}/scripts/quadkey_index.py --lat 35.6586 --lon 139.7454 --zoom 15

# タイル座標 → Quadkey
python3 ${CLAUDE_SKILL_DIR}/scripts/quadkey_index.py --tile-x 29102 --tile-y 12903 --zoom 15

# デコード (Quadkey → 緯度経度・bbox)
python3 ${CLAUDE_SKILL_DIR}/scripts/quadkey_index.py --quadkey 133010110110001

# 隣接セル
python3 ${CLAUDE_SKILL_DIR}/scripts/quadkey_index.py --neighbors --quadkey 133010110110001

# 親セル / 子セル
python3 ${CLAUDE_SKILL_DIR}/scripts/quadkey_index.py --parent --quadkey 133010110110001
python3 ${CLAUDE_SKILL_DIR}/scripts/quadkey_index.py --children --quadkey 133010110110001

# セル境界 (GeoJSON)
python3 ${CLAUDE_SKILL_DIR}/scripts/quadkey_index.py --boundary --quadkey 133010110110001

# CSV一括変換
python3 ${CLAUDE_SKILL_DIR}/scripts/quadkey_index.py --input coords.csv --operation encode --zoom 15
```

**注意:** 詳細な XYZ タイル操作（タイル座標の相互変換等）は `gis-coord-transform` スキルを使用してください。

#### E. MGRS

NATO 軍事グリッド座標系。防災・捜索救助でも使用される高精度座標表現。

```bash
# エンコード
python3 ${CLAUDE_SKILL_DIR}/scripts/mgrs_index.py --lat 35.6586 --lon 139.7454 --precision 5

# デコード
python3 ${CLAUDE_SKILL_DIR}/scripts/mgrs_index.py --mgrs 54SUE85555300

# セル境界 (GeoJSON)
python3 ${CLAUDE_SKILL_DIR}/scripts/mgrs_index.py --boundary --mgrs 54SUE8553

# CSV一括変換
python3 ${CLAUDE_SKILL_DIR}/scripts/mgrs_index.py --input coords.csv --operation encode --precision 5
```

#### F. Maidenhead

アマチュア無線で使用されるグリッドロケーター。

```bash
# エンコード
python3 ${CLAUDE_SKILL_DIR}/scripts/maidenhead_index.py --lat 35.6586 --lon 139.7454 --precision 3

# デコード
python3 ${CLAUDE_SKILL_DIR}/scripts/maidenhead_index.py --locator PM95qk

# 隣接セル
python3 ${CLAUDE_SKILL_DIR}/scripts/maidenhead_index.py --neighbors --locator PM95qk

# セル境界 (GeoJSON)
python3 ${CLAUDE_SKILL_DIR}/scripts/maidenhead_index.py --boundary --locator PM95qk

# CSV一括変換
python3 ${CLAUDE_SKILL_DIR}/scripts/maidenhead_index.py --input coords.csv --operation encode --precision 3
```

#### G. Morton Code (Z-order curve)

空間充填曲線によるビットインターリーブ。Geohash や Quadkey の基盤技術。

```bash
# エンコード
python3 ${CLAUDE_SKILL_DIR}/scripts/morton_index.py --lat 35.6586 --lon 139.7454 --bits 32

# デコード
python3 ${CLAUDE_SKILL_DIR}/scripts/morton_index.py --code 3803488912476885196

# CSV一括変換
python3 ${CLAUDE_SKILL_DIR}/scripts/morton_index.py --input coords.csv --operation encode --bits 32
```

## 精度の選択

目標セルサイズ（メートル）から適切な精度レベルを推定する機能は Geohash と H3 で利用可能:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/geohash_index.py --precision-estimate --meters 100
python3 ${CLAUDE_SKILL_DIR}/scripts/h3_index.py --precision-estimate --meters 100
```

他システムの精度テーブルは `${CLAUDE_SKILL_DIR}/references/spatial-index-systems.md` を参照。

## リファレンス

- `${CLAUDE_SKILL_DIR}/references/spatial-index-systems.md` — 全システム比較表・精度テーブル・選択ガイド

## 注意事項

- Geohash の辺境界問題: 隣接するセルでも prefix が完全に異なることがある。近傍検索は必ず `--neighbors` を併用する
- H3 の六角形グリッドは矩形領域と完全には対応しない。矩形バウンディングボックスには Geohash/Quadkey が適する
- Quadkey は Web Mercator 投影 (EPSG:3857) に基づくため、極地 (緯度±85.05°以上) では利用不可
- MGRS は UTM ゾーン境界をまたぐ場合に注意が必要
- polyfill の `--max-cells` パラメータでセル数上限を制御できる（デフォルト 100,000）
