# gis-skills ![version](https://img.shields.io/badge/version-0.1.0-blue)

GIS（地理情報システム）関連タスクを処理する Claude Code スキル集。座標変換・空間解析・データ変換・ジオコーディングの4つのスキルで構成される。

## Quick Start

```bash
git clone https://github.com/<owner>/gis-skills.git
cd gis-skills
./setup.sh --user    # 全プロジェクトで使用可能にする
```

Claude Code で話しかけるだけで使える:

- 「東京タワーの緯度経度を調べて」
- 「この Shapefile を GeoJSON に変換して」
- 「東京駅の 3 次メッシュコードを教えて」

## スキル一覧

| スキル | ディレクトリ | 主な依存 | 用途 |
|--------|-------------|----------|------|
| gis-coord-transform | `gis-coord-transform/` | pyproj, jgdtrans | 座標変換・投影法変換・測地系変換・タイル座標・メッシュコード |
| gis-spatial-analysis | `gis-spatial-analysis/` | shapely, geopandas, pyproj | バッファ・オーバーレイ・距離計算・空間結合 |
| gis-data-convert | `gis-data-convert/` | fiona, geopandas, pyproj | GeoJSON/Shapefile/KML/GeoPackage/CSV 間の変換 |
| gis-geocoding | `gis-geocoding/` | geopy, requests | 住所・地名→座標、座標→住所 |

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

## 依存パッケージ

各スクリプトは初回実行時に依存パッケージを自動インストールする。手動でのセットアップは不要。

`gis-data-convert` は GDAL が必要になる場合がある。自動インストールに失敗した場合は OS に応じてインストールする:

```bash
# macOS
brew install gdal

# Linux (Debian/Ubuntu)
sudo apt install gdal-bin libgdal-dev

# Linux (Fedora/RHEL)
sudo dnf install gdal gdal-devel

# Windows (conda 推奨)
conda install -c conda-forge gdal
# または OSGeo4W (https://trac.osgeo.org/osgeo4w/) を利用
```

> GeoJSON/CSV 間の変換は GDAL がなくても純 Python フォールバックで動作する。

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

**メッシュコード**

- 「東京スカイツリーの 3 次メッシュコードを教えて」
- 「メッシュコード 53394611 の範囲（南西・北東の緯度経度）を教えて」
- 「渋谷駅の 1/8 メッシュコード（レベル6）を求めて」
- 「名古屋駅の 1 次メッシュコードを教えて」

---

### gis-spatial-analysis — 空間解析

**バッファ解析**

- 「points.geojson の各ポイントの周囲 500m にバッファを作成して」
- 「道路の line.geojson から 100m バッファのポリゴンを生成して」
- 「公園ポリゴン parks.geojson の外周に 200m のバッファを追加して」

**オーバーレイ解析**

- 「area_a.geojson と area_b.geojson の重なる部分だけ抽出して」
- 「2 つの行政区域ポリゴンの和集合（union）を作って」
- 「土地利用データから河川区域を差し引いて（difference）」
- 「2 つのエリアの対称差（どちらか一方にだけ含まれる領域）を求めて」

**距離計算**

- 「stations.geojson の各駅から hospitals.geojson の最寄りの病院までの距離を計算して」
- 「2 つの GeoJSON ファイルの全組み合わせの距離行列を作って」
- 「schools.geojson と parks.geojson で対応するペア同士の距離を計算して」
- 「地球の曲率を考慮した測地線距離で最近傍計算して」
- 「stations.geojson の中で、各駅の最寄りの別の駅との距離を求めて」

---

### gis-data-convert — データ変換

**フォーマット検出・メタデータ確認**

- 「data.shp のフォーマット・CRS・フィーチャ数を確認して」
- 「buildings.geojson のメタデータを表示して」
- 「この GeoPackage にどんなレイヤーが入っているか調べて」
- 「locations.csv が GIS データとして使えるか確認して」

**Shapefile ↔ GeoJSON 変換**

- 「buildings.shp を GeoJSON に変換して」
- 「この日本語の Shapefile を GeoJSON に変換して」
- 「buildings.geojson を Shapefile に変換して」

**CSV → GeoJSON**

- 「locations.csv を GeoJSON に変換して（緯度経度列は自動検出で）」
- 「この CSV から GeoJSON を作って」

**GeoJSON → KML**

- 「route.geojson を Google Earth 用の KML に変換して」

**GeoJSON ↔ GeoPackage**

- 「buildings.geojson を GeoPackage に変換して、レイヤー名は buildings にして」
- 「data.gpkg の buildings レイヤーを GeoJSON に変換して」

**CRS 変換付きフォーマット変換**

- 「平面直角座標系の Shapefile を WGS84 の GeoJSON に変換して」
- 「この GeoJSON を WGS84 に変換しつつ GeoPackage に出力して」

---

### gis-geocoding — ジオコーディング

**住所・地名から座標を取得**

- 「東京タワーの緯度経度を調べて」
- 「東京都千代田区永田町1-7-1 の座標を教えて」
- 「"東京駅" で検索して候補を全件表示して」
- 「大阪城の座標を調べて」

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

## GIS 作業の注意事項

- **座標順序**: pyproj の `Transformer` には必ず `always_xy=True` を指定する（経度→緯度の順序を統一）
- **距離・面積計算**: 投影座標系（平面直角座標系等）で行う。地理座標系 (EPSG:4326) のまま計算してはいけない
- **GeoJSON 出力**: WGS84 (EPSG:4326) にする（RFC 7946 準拠）
- **Shapefile エンコーディング**: 日本の Shapefile は cp932 エンコーディングが多い
- **測地系変換**: 旧測地系→JGD2011 の高精度変換は TKY2JGD → PatchJGD の二段階で行う

### 主要な座標系 (EPSG コード)

| EPSG | 名称 | 用途 |
|------|------|------|
| 4326 | WGS84 | GPS・Web 標準 |
| 6668 | JGD2011 | 日本の現行測地系 |
| 4301 | Tokyo Datum | 旧日本測地系（2002年以前） |
| 6669-6687 | 平面直角座標系 I-XIX | 測量・設計（JGD2011） |
| 3857 | Web メルカトル | Web 地図タイル |

### 主要都市の平面直角座標系

| 都市 | 系番号 | EPSG |
|------|--------|------|
| 東京 | IX 系 | 6677 |
| 大阪 | VI 系 | 6674 |
| 名古屋 | VII 系 | 6675 |
| 福岡 | II 系 | 6670 |
| 札幌 | XII 系 | 6680 |
| 仙台 | X 系 | 6678 |
| 広島 | III 系 | 6671 |
| 那覇 | XV 系 | 6683 |

## ライセンス

各スキルが利用する外部 API の利用規約に従うこと:

- **国土地理院 API**: [利用規約](https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html)
- **Nominatim**: [Usage Policy](https://operations.osmfoundation.org/policies/nominatim/)（1リクエスト/秒の制限あり）
