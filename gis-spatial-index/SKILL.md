---
name: gis-spatial-index
description: "空間インデックス・位置エンコーディングスキル。メッシュコード（標準地域メッシュ、JIS X 0410、地域メッシュ、統計メッシュ）、Geohash（ジオハッシュ）、H3（Uber H3、六角形グリッド）、Plus Code（Open Location Code、OLC、プラスコード）、Quadkey（クアッドキー、Bing Maps タイルキー）、MGRS（Military Grid Reference System、軍用グリッド座標）、Maidenhead（メイデンヘッド、グリッドロケーター、アマチュア無線）、Morton code（モートンコード、Z-order curve、空間充填曲線）、XYZ タイル（タイル座標、Slippy Map Tilenames、tile coordinates、Web地図タイル）、空間ID（Spatial ID、ZFXY、3D空間インデックス、ボクセル、voxel、デジタルツイン、3次元空間ID、4次元時空間、PLATEAU）の10種の空間インデックスシステムに対応。エンコード（座標→コード）、デコード（コード→座標）、近傍セル検索、親子セル、セル境界ポリゴン取得、ポリフィル、コンパクト、グリッド距離、精度推定、CSV一括変換（バッチ処理）を提供。ユーザーが空間インデックス、空間コード、グリッドシステム、セルID、メッシュコード、地域メッシュ、mesh code、JIS X 0410、統計メッシュ、1次メッシュ、2次メッシュ、3次メッシュ、geohash、h3、hex、hexagon、plus code、open location code、quadkey、quadtree、mgrs、military grid、maidenhead、grid locator、morton、z-order、空間充填曲線、タイル座標、tile、XYZ、slippy map、空間ID、spatial id、ZFXY、ボクセル、voxel、デジタルツイン、エンコード、デコード、近傍、neighbor、polyfill、compact、空間検索、位置コードについて言及した場合にこのスキルを使用する。"
tools: Bash, Read, Write, Glob
---

# 空間インデックス・位置エンコーディングスキル

## ワークフロー

### Step 1: システムの選択

ユーザーの要件に基づき、適切な空間インデックスシステムを選択する。
`${CLAUDE_SKILL_DIR}/references/spatial-index-systems.md` を参照して、比較表・選択ガイドを確認する。

**簡易選択ガイド:**
- 日本の統計・行政メッシュデータ → **メッシュコード (JIS X 0410)**
- DB空間インデックス (Elasticsearch/DynamoDB/Redis) → **Geohash**
- データエンジニアリング (BigQuery/Snowflake/Databricks) → **H3**
- 人間可読な位置コード (Google Maps共有) → **Plus Code**
- Web地図タイルキャッシュ (Bing Maps/CARTO) → **Quadkey**
- 防災・捜索救助・軍事 → **MGRS**
- アマチュア無線 → **Maidenhead**
- 空間ソートキー・空間充填曲線 → **Morton code**
- Web地図タイル座標変換 → **XYZ タイル**
- 3D空間管理・デジタルツイン → **空間ID (ZFXY)**

### Step 2: 操作の実行

#### A. メッシュコード (JIS X 0410)

日本の標準地域メッシュ。国勢調査・都市計画・統計データで広く使用される。日本国内限定。純Python実装（外部ライブラリ不要）。

```bash
# エンコード (緯度経度 → メッシュコード)
python3 ${CLAUDE_SKILL_DIR}/scripts/mesh_code.py --lat 35.6586 --lon 139.7454 --level 3

# デコード (メッシュコード → 緯度経度・bbox)
python3 ${CLAUDE_SKILL_DIR}/scripts/mesh_code.py --code 53394525

# 隣接セル (8方向)
python3 ${CLAUDE_SKILL_DIR}/scripts/mesh_code.py --neighbors --code 53394525

# 親セル
python3 ${CLAUDE_SKILL_DIR}/scripts/mesh_code.py --parent --code 53394525

# 子セル
python3 ${CLAUDE_SKILL_DIR}/scripts/mesh_code.py --children --code 53394525

# セル境界 (GeoJSON)
python3 ${CLAUDE_SKILL_DIR}/scripts/mesh_code.py --boundary --code 53394525

# CSV一括変換
python3 ${CLAUDE_SKILL_DIR}/scripts/mesh_code.py --input coords.csv --operation encode --level 3
python3 ${CLAUDE_SKILL_DIR}/scripts/mesh_code.py --input meshes.csv --operation decode
```

#### B. Geohash

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

#### C. H3

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

#### D. Plus Code (Open Location Code)

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

#### E. Quadkey

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

#### F. MGRS

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

#### G. Maidenhead

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

#### H. Morton Code (Z-order curve)

空間充填曲線によるビットインターリーブ。Geohash や Quadkey の基盤技術。

```bash
# エンコード
python3 ${CLAUDE_SKILL_DIR}/scripts/morton_index.py --lat 35.6586 --lon 139.7454 --bits 32

# デコード
python3 ${CLAUDE_SKILL_DIR}/scripts/morton_index.py --code 3803488912476885196

# CSV一括変換
python3 ${CLAUDE_SKILL_DIR}/scripts/morton_index.py --input coords.csv --operation encode --bits 32
```

#### I. XYZ タイル

Web 地図で標準的な Slippy Map Tilenames 形式のタイル座標。緯度経度 ↔ タイル番号の相互変換。

```bash
# 緯度経度 → タイル座標
python3 ${CLAUDE_SKILL_DIR}/scripts/tile_coords.py --lat 35.6586 --lon 139.7454 --zoom 15

# タイル座標 → 緯度経度（中心座標・bbox）
python3 ${CLAUDE_SKILL_DIR}/scripts/tile_coords.py --x 29102 --y 12903 --zoom 15
```

#### J. 空間ID (Spatial ID / ZFXY)

日本の3次元空間ID (ZFXY形式)。XYZタイル座標にフロア軸(f)を追加した3Dボクセルインデックス。デジタルツイン・PLATEAU等の3D空間管理に使用。

```bash
# エンコード (緯度経度+標高 → 空間ID)
python3 ${CLAUDE_SKILL_DIR}/scripts/spatial_id_index.py --lat 35.6586 --lon 139.7454 --altitude 50.0 --zoom 20

# 標高なし (デフォルト: 海面 = altitude 0)
python3 ${CLAUDE_SKILL_DIR}/scripts/spatial_id_index.py --lat 35.6586 --lon 139.7454 --zoom 20

# デコード (空間ID → 緯度経度・高度・3Dバウンディングボックス)
python3 ${CLAUDE_SKILL_DIR}/scripts/spatial_id_index.py --zfxy "20/1/931277/412899"

# 隣接ボクセル (6方向: 東西南北上下)
python3 ${CLAUDE_SKILL_DIR}/scripts/spatial_id_index.py --neighbors --zfxy "20/1/931277/412899"

# 親ボクセル / 子ボクセル (オクツリー構造)
python3 ${CLAUDE_SKILL_DIR}/scripts/spatial_id_index.py --parent --zfxy "20/1/931277/412899"
python3 ${CLAUDE_SKILL_DIR}/scripts/spatial_id_index.py --children --zfxy "20/1/931277/412899"

# セル境界 (GeoJSON + 高度プロパティ)
python3 ${CLAUDE_SKILL_DIR}/scripts/spatial_id_index.py --boundary --zfxy "20/1/931277/412899"

# ズームレベル別解像度テーブル
python3 ${CLAUDE_SKILL_DIR}/scripts/spatial_id_index.py --zoom-table

# CSV一括変換
python3 ${CLAUDE_SKILL_DIR}/scripts/spatial_id_index.py --input coords.csv --operation encode --zoom 20
python3 ${CLAUDE_SKILL_DIR}/scripts/spatial_id_index.py --input spatial_ids.csv --operation decode
```

**ZFXY フォーマット:** `z/f/x/y`（z=ズーム, f=フロア(高度), x=東西タイル, y=南北タイル）。f は負値可（地下）。

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

- メッシュコードは日本国内限定（緯度 20〜46°、経度 122〜154°）。海外の座標には使用不可
- Geohash の辺境界問題: 隣接するセルでも prefix が完全に異なることがある。近傍検索は必ず `--neighbors` を併用する
- H3 の六角形グリッドは矩形領域と完全には対応しない。矩形バウンディングボックスには Geohash/Quadkey が適する
- Quadkey・XYZ タイル・空間ID は Web Mercator 投影 (EPSG:3857) に基づくため、極地 (緯度±85.05°以上) では利用不可
- MGRS は UTM ゾーン境界をまたぐ場合に注意が必要
- 空間ID の高度は海面基準（メートル）。地下（負の標高）もサポートする。鉛直範囲は ±33,554,432m
- polyfill の `--max-cells` パラメータでセル数上限を制御できる（デフォルト 100,000）
