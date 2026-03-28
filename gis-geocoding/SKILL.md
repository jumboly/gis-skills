---
name: gis-geocoding
description: "ジオコーディング・逆ジオコーディングスキル。地名・住所・ランドマークから緯度経度座標を求める（正引き）、および座標から住所を求める（逆引き）。国土地理院 地名検索API（日本国内向け、APIキー不要）をデフォルトで使用し、Nominatim（OpenStreetMap、世界対応）にも切替可能。ユーザーがジオコーディング、住所から座標、地名検索、逆ジオコーディング、座標から住所、住所検索、geocode、アドレスマッチングについて言及した場合にこのスキルを使用する。"
tools: Bash, Read, Write, Glob
---

# ジオコーディング・逆ジオコーディングスキル

## ジオコーディング（地名・住所 → 座標）

### 単一クエリ

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/geocode.py --query "東京タワー"
python3 ${CLAUDE_SKILL_DIR}/scripts/geocode.py --query "東京都千代田区永田町1-7-1"
```

全候補を取得する場合:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/geocode.py --query "東京駅" --all-results
```

### バッチ処理（CSV 入力）

`query` 列を含む CSV ファイルを入力:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/geocode.py --input addresses.csv --output results.csv
```

### サービスの切替

デフォルトは国土地理院（日本国内向け）。海外の地名には Nominatim を使用:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/geocode.py --query "Eiffel Tower" --service nominatim
```

## 逆ジオコーディング（座標 → 住所）

### 単一座標

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/reverse_geocode.py --lat 35.6586 --lon 139.7454
```

### バッチ処理（CSV 入力）

`lat`, `lon` 列を含む CSV ファイルを入力:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/reverse_geocode.py --input coords.csv --output addresses.csv
```

### サービスの切替

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/reverse_geocode.py --lat 48.8584 --lon 2.2945 --service nominatim
```

## Python コードでの利用

```python
import requests

# 国土地理院 地名検索API
resp = requests.get(
    "https://msearch.gsi.go.jp/address-search/AddressSearch",
    params={"q": "東京タワー"},
)
for item in resp.json():
    lon, lat = item["geometry"]["coordinates"]
    print(f"{item['properties']['title']}: {lat}, {lon}")
```

```python
# 逆ジオコーディング
resp = requests.get(
    "https://mreversegeocoder.gsi.go.jp/reverse-geocoder/LonLatToAddress",
    params={"lat": 35.6586, "lon": 139.7454},
)
results = resp.json()["results"]
print(f"{results.get('muniCd', '')} {results.get('lv01Nm', '')}")
```

## リファレンス

- `${CLAUDE_SKILL_DIR}/references/geocoding-services.md` — 利用可能なサービスの詳細、エンドポイント、制限事項

## 注意事項

- 国土地理院APIは日本国内の地名のみ対応。海外は `--service nominatim` を使う
- Nominatim は **1リクエスト/秒** のレートリミットがある（バッチ処理時は自動で待機）
- 国土地理院APIの座標は WGS84 (EPSG:4326) で返される
- 逆ジオコーディング（国土地理院）は町字レベルまでの精度。番地レベルではない
- ジオコーディング結果は検索クエリの表記揺れにより精度が変わる。正式な住所表記を推奨
