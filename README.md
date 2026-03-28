# gis-skills ![version](https://img.shields.io/badge/version-0.4.0-blue)

> A collection of Claude Code skills for GIS tasks: coordinate transformation, geocoding, elevation, and spatial indexing for Japan and worldwide.

GIS（地理情報システム）関連タスクを処理する Claude Code スキル集。自然言語の指示だけで座標変換やジオコーディングを実行できる。

## Quick Start

### 1. インストール

```bash
git clone https://github.com/jumboly/gis-skills.git
cd gis-skills
./setup.sh --user           # 全プロジェクトで使用可能にする
.\setup.ps1 -Scope User    # Windows の場合
```

### 2. 使ってみる

Claude Code で話しかけるだけで使える:

- 「東京タワーの緯度経度を調べて」
- 「東京タワーの座標を平面直角座標系に変換して」
- 「東京駅の 3 次メッシュコードを教えて」
- 「東京タワーの Geohash を教えて」
- 「この座標を H3 セルに変換して」

## 機能一覧

- EPSG コード間の座標変換（4,000+ 座標系対応）
- 旧日本測地系 → JGD2011 の高精度変換（TKY2JGD / PatchJGD パラメータ対応）
- 住所・地名 → 座標の変換（国土地理院 API、キー不要）
- 座標 → 住所の逆ジオコーディング
- XYZ タイル座標変換、バウンディングボックス計算
- JIS X 0410 標準地域メッシュコード変換（Level 1〜6）
- CSV 一括バッチ処理、海外対応（Nominatim / OpenStreetMap）
- 空間インデックス変換（Geohash / H3 / Plus Code / Quadkey / MGRS / Maidenhead / Morton code）
- セルの近傍検索、親子セル、境界ポリゴン取得、ポリフィル、コンパクト化
- 国土地理院 DEM タイルから標高取得（5m/10m DEM 自動フォールバック）
- 標高断面図データ生成、CSV 一括標高付与
- ランダムポイント・ライン・ポリゴン生成（bbox / GeoJSON マスク指定、GeoJSON 出力）
- Overpass API から行政界ポリゴン取得（都道府県・市区町村・町丁目）

## スキル一覧

| スキル | ディレクトリ | 主な依存 | 用途 |
|--------|-------------|----------|------|
| gis-coord-transform | `gis-coord-transform/` | pyproj, jgdtrans | 座標変換・投影法変換・測地系変換・タイル座標・メッシュコード |
| gis-geocoding | `gis-geocoding/` | requests | 住所・地名→座標、座標→住所 |
| gis-spatial-index | `gis-spatial-index/` | h3, openlocationcode, mgrs | Geohash/H3/Plus Code/Quadkey/MGRS/Maidenhead/Morton 空間インデックス |
| gis-elevation | `gis-elevation/` | Pillow, requests | 国土地理院 DEM タイルから標高取得・断面図 |
| gis-data-gen | `gis-data-gen/` | scipy, shapely | ランダム GIS テストデータ生成・行政界取得 |

## インストール

```bash
# ユーザーレベル（全プロジェクトで使用可能）
./setup.sh --user

# 特定プロジェクトにインストール
./setup.sh --project /path/to/my-project

# アンインストール
./setup.sh uninstall --user
./setup.sh uninstall --project /path/to/my-project
```

Windows (PowerShell):

```powershell
# ユーザーレベル
.\setup.ps1 -Scope User

# 特定プロジェクトにインストール
.\setup.ps1 -Scope Project -ProjectPath C:\path\to\my-project

# アンインストール
.\setup.ps1 -Action Uninstall -Scope User
```

## 必要条件

- **Python 3.10+** 推奨（macOS 標準の Python 3.9 は LibreSSL でビルドされており SSL 警告が出る場合がある）
- macOS の場合: `brew install python`

## 依存パッケージ

各スクリプトは初回実行時に依存パッケージを自動インストールする。手動でのセットアップは不要。

| スキル | 自動インストールされるパッケージ |
|--------|-------------------------------|
| gis-coord-transform | pyproj, jgdtrans |
| gis-geocoding | requests |
| gis-spatial-index | h3, openlocationcode, mgrs |
| gis-elevation | Pillow, requests |
| gis-data-gen | scipy, shapely |

> **Note:** GIS データ変換（GeoJSON/Shapefile/KML/GeoPackage/CSV 間）はスキル化していない。Claude が geopandas/fiona のコードを直接生成すれば十分なため。

---

## スキル使用例

各スキルは Claude Code のスキルとして登録して使用する。自然言語で指示するだけで、適切なスクリプトが自動的に選択・実行される。

---

### gis-coord-transform — 座標変換

**座標系の検索**

- 「JGD2011 に関連する座標系の一覧を見せて」
- 「EPSG:6677 がどの座標系か調べて」
- 「日本で使われる投影座標系を一覧表示して」

**座標変換**

- 「東京タワーの座標を平面直角座標系に変換して」
- 「新宿駅の緯度経度を Web メルカトル (EPSG:3857) に変換して」
- 「EPSG:6677 の座標 (-21166.68, -7926.34) を WGS84 の緯度経度に逆変換して」

出力例:
```
変換結果 (EPSG:4326 → EPSG:6677):
  入力: 経度 139.7454, 緯度 35.6586 (WGS84)
  出力: X = -21166.68 m, Y = -7926.34 m (平面直角座標系 IX系)
```

**CSV 一括変換**

- 「coords.csv の座標を平面直角座標系に一括変換して」
- 「この CSV ファイルの緯度経度を EPSG:3857 に変換して result.csv に保存して」

**測地系変換**

- 「旧日本測地系の座標を JGD2011 に変換して」
- 「TKY2JGD.par を使って coords.csv を旧測地系から JGD2011 に高精度変換して」
- 「PatchJGD で JGD2000 の座標を JGD2011 に変換して（東日本大震災の地殻変動補正）」
- 「PatchJGD で JGD2011 から JGD2000 へ逆変換して」

**バウンディングボックス計算**

- 「大阪城を中心に縮尺 1:2000、1000×1000px の表示範囲を計算して」
- 「新宿駅を中心に縮尺 1:5000、800×600px、72dpi での Bounding Box を求めて」

**タイル座標**

- 「東京タワーのズームレベル 15 での XYZ タイル座標を教えて」
- 「タイル座標 (x=29102, y=12903, z=15) の緯度経度と範囲を求めて」
- 「この地点のタイル URL（国土地理院標準地図）を組み立てて」

出力例:
```
タイル座標 (zoom=15):
  タイル: x=29102, y=12903
  URL: https://cyberjapandata.gsi.go.jp/xyz/std/15/29102/12903.png
  範囲: [139.7324, 35.6572, 139.7446, 35.6677]
```

**メッシュコード**

- 「東京スカイツリーの 3 次メッシュコードを教えて」
- 「メッシュコード 53394611 の範囲（南西・北東の緯度経度）を教えて」
- 「渋谷駅の 1/8 メッシュコード（レベル6）を求めて」
- 「名古屋駅の 1 次メッシュコードを教えて」

出力例:
```
メッシュコード (Level 3):
  コード: 53394525
  南西角: 緯度 35.6500, 経度 139.7500
  北東角: 緯度 35.6583, 経度 139.7625
  辺の長さ: 約 1km
```

---

### gis-geocoding — ジオコーディング

**住所・地名から座標を取得**

- 「東京タワーの緯度経度を調べて」
- 「東京都千代田区永田町1-7-1 の座標を教えて」
- 「"東京駅" で検索して候補を全件表示して」
- 「大阪城の座標を調べて」

出力例:
```
東京タワー:
  緯度: 35.6586  経度: 139.7454 (WGS84 / EPSG:4326)
```

**海外の地名検索**

- 「エッフェル塔の座標を Nominatim で検索して」
- 「Statue of Liberty の緯度経度を調べて」
- 「"Big Ben, London" の座標を教えて」

**CSV 一括ジオコーディング**

- 「addresses.csv の住所一覧を一括でジオコーディングして」
- 「このランドマーク一覧の CSV から座標付きデータを作って」

**逆ジオコーディング（座標→住所）**

- 「東京タワー付近の住所を逆ジオコーディングで調べて」
- 「この座標リストの各地点の住所を逆ジオコーディングで取得して」
- 「パリのエッフェル塔付近の住所を Nominatim で調べて」
- 「coords.csv の座標から住所を一括取得して」

---

### gis-spatial-index — 空間インデックス

**Geohash**

- 「東京タワーの Geohash（precision 7）を教えて」
- 「Geohash xn76urx の範囲と隣接セルを表示して」
- 「この GeoJSON ポリゴン内の Geohash 一覧を出して（precision 6）」

**H3**

- 「東京タワーの H3 セル（resolution 9）を教えて」
- 「この H3 セルの k-ring（k=2）を取得して」
- 「この GeoJSON ポリゴンを H3 セルで埋めて（resolution 8）」

**Plus Code**

- 「東京タワーの Plus Code を教えて」
- 「Plus Code 8Q7XMM5G+QV の座標を教えて」

**Quadkey**

- 「東京タワーの Quadkey（zoom 15）を教えて」
- 「Quadkey 133010110110001 の範囲を表示して」

**MGRS**

- 「東京タワーの MGRS 座標を教えて」
- 「MGRS 54SUE8553 の範囲を教えて」

**Maidenhead**

- 「東京タワーのグリッドロケーターを教えて」

**Morton code**

- 「この座標の Morton code を計算して」

---

### gis-elevation — 標高取得

**単一座標の標高取得**

- 「富士山山頂の標高を調べて」
- 「東京タワーの地点の標高を取得して」
- 「この座標の 5m メッシュ DEM の標高を教えて」

**CSV 一括標高付与**

- 「この CSV の座標リストに標高を付与して」
- 「points.csv の各地点の標高を取得して result.csv に保存して」

**標高断面図**

- 「東京駅から新宿駅までの標高断面図のデータを作って」
- 「この2点間の標高プロファイルを50分割で取得して」

---

### gis-data-gen — GIS テストデータ生成

**ランダムポイント生成**

- 「東京都の範囲にランダムな100個のポイントを生成して」
- 「この GeoJSON ポリゴン内にクラスター分布で50点を生成して」

**ランダムライン生成**

- 「大阪府の範囲にランダムなラインを20本生成して」
- 「bbox 指定でランダムウォークのラインを生成して」

**ランダムポリゴン生成**

- 「渋谷区の範囲を Voronoi 分割で10個のポリゴンに分けて」
- 「この範囲に穴あきポリゴンをランダムに5個生成して」

**行政界ポリゴン取得**

- 「渋谷区の行政界ポリゴンを取得して」
- 「大阪府の境界ポリゴンを取得して、その中にランダムポイントを生成して」

---

### 複合ワークフロー例

複数のスキルを組み合わせて使うこともできる:

**geocoding + coord-transform**

- 「東京タワーの座標を調べて、平面直角座標系（IX系）に変換して」
- 「addresses.csv の住所をジオコーディングして、結果の座標をメッシュコードに変換して」
- 「那覇市役所の座標を調べて、平面直角座標系に変換して」（自動的に XV 系が選択される）
- 「この旧測地系の座標リストを JGD2011 に変換してから逆ジオコーディングで住所を取得して」

**geocoding + spatial-index**

- 「東京タワーの座標を調べて、Geohash（precision 7）と H3 セル（resolution 9）を教えて」
- 「addresses.csv の住所をジオコーディングして、結果に Plus Code を付与して」

**coord-transform + spatial-index**

- 「この平面直角座標系の座標を WGS84 に変換して、MGRS 座標を求めて」
- 「この Geohash の中心座標を UTM 座標に変換して」

**3スキル連携**

- 「addresses.csv の住所をジオコーディングして、H3 セル（resolution 8）とメッシュコード（3次メッシュ）を付与して」

**geocoding + elevation**

- 「東京タワーの座標を調べて、その地点の標高を取得して」
- 「addresses.csv の住所をジオコーディングして、各地点の標高を付与して」

**elevation + coord-transform**

- 「この CSV の座標に標高を付与して、平面直角座標系に変換して」

**data-gen + spatial-index**

- 「渋谷区の行政界内にランダムポイントを100個生成して、各ポイントの H3 セルを付与して」
- 「この範囲にランダムポリゴンを生成して、各ポリゴンの重心の Geohash を求めて」

**data-gen + elevation**

- 「東京都の範囲にランダムポイントを50個生成して、各地点の標高を付与して」

**スキル + Claude 直接処理**

Claude 自身も geopandas・shapely・fiona 等のコードを直接生成・実行して GIS 処理を行えるため、スキルと組み合わせることでより高度なワークフローが可能になる:

- 「buildings.shp の各建物の重心座標を求めて、Geohash を付与した CSV を出力して」（Claude が geopandas/shapely で重心計算 → gis-spatial-index で Geohash 付与）
- 「この2つの GeoJSON ポリゴンの交差領域を求めて、その範囲を H3 セルでポリフィルして」（Claude が shapely で交差演算 → gis-spatial-index でポリフィル）
- 「この CSV の座標を GeoJSON に変換して、各ポイントの最寄り駅までの距離も計算して」（Claude が geopandas で GeoJSON 生成・距離計算 → gis-geocoding で駅名検索）

---

## API レートリミット

| API | レートリミット | APIキー | 備考 |
|-----|-------------|---------|------|
| 国土地理院 地名検索 | 明示なし（バッチ時 0.5秒間隔） | 不要 | 日本国内のみ |
| 国土地理院 逆ジオコーディング | 明示なし（バッチ時 0.5秒間隔） | 不要 | 町字レベル精度 |
| Nominatim | 1リクエスト/秒（必須） | 不要 | User-Agent 必須 |

## トラブルシューティング

**setup.sh 実行後にスキルが認識されない**

Claude Code を再起動してください。スキルの読み込みは起動時に行われます。

**Python 3.9 で SSL 警告が出る**

macOS 標準の Python 3.9 は LibreSSL でビルドされているため、urllib3 が警告を出す場合があります。動作に問題はありませんが、警告を解消するには `brew install python` で Python 3.10+ をインストールしてください。

**pip install が失敗する（企業プロキシ環境）**

プロキシ環境では自動インストールが失敗する場合があります。事前に手動でインストールしてください:
```bash
pip install pyproj jgdtrans requests h3 openlocationcode mgrs Pillow
```

**Nominatim のバッチ処理が遅い**

Nominatim は利用規約で 1リクエスト/秒に制限されています。1,000件のバッチ処理には約18分かかります。日本国内のデータであれば `--service gsi`（デフォルト）の方が高速です。

**同名の地名で意図しない結果が返る**

`--all-results` フラグで候補を全件表示し、目的の地点を特定してください:
```
「"中央公園" で検索して候補を全件表示して」
```

---
## ライセンス

MIT License. 各スキルが利用する外部 API の利用規約に従うこと:

- **国土地理院 API**: [利用規約](https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html)
- **Nominatim**: [Usage Policy](https://operations.osmfoundation.org/policies/nominatim/)（1リクエスト/秒の制限あり）
