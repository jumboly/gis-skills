# ジオコーディングサービス一覧

## 国土地理院 地名検索API（デフォルト）

日本国内の住所・地名・ランドマークに特化。APIキー不要。

### ジオコーディング（正引き）

| 項目 | 内容 |
|------|------|
| エンドポイント | `https://msearch.gsi.go.jp/address-search/AddressSearch` |
| メソッド | GET |
| パラメータ | `q` = 検索文字列 |
| レスポンス | GeoJSON FeatureCollection |
| レートリミット | 明示的な公式制限なし。バッチ処理では 0.5〜1秒の間隔を推奨 |

レスポンス例:
```json
[
  {
    "type": "Feature",
    "geometry": {
      "type": "Point",
      "coordinates": [139.7454, 35.6586]
    },
    "properties": {
      "title": "東京タワー"
    }
  }
]
```

### 逆ジオコーディング（逆引き）

| 項目 | 内容 |
|------|------|
| エンドポイント | `https://mreversegeocoder.gsi.go.jp/reverse-geocoder/LonLatToAddress` |
| メソッド | GET |
| パラメータ | `lat`, `lon` |
| レスポンス | JSON（市区町村コード + 町字名） |

レスポンス例:
```json
{
  "results": {
    "muniCd": "13103",
    "lv01Nm": "芝公園四丁目"
  }
}
```

- `muniCd` は全国地方公共団体コード（5桁）
- `lv01Nm` は町字レベルの地名

## Nominatim（OpenStreetMap）

世界中の住所・地名に対応。APIキー不要だが利用規約の遵守が必要。

| 項目 | 内容 |
|------|------|
| ジオコーディング | `https://nominatim.openstreetmap.org/search` |
| 逆ジオコーディング | `https://nominatim.openstreetmap.org/reverse` |
| レートリミット | **最大 1リクエスト/秒**（必須） |
| User-Agent | **必須**（アプリ名を設定すること） |
| 利用規約 | https://operations.osmfoundation.org/policies/nominatim/ |

### 利用上の注意

- バッチ処理では必ず 1秒以上の間隔を空ける
- 大量リクエスト（1日数千件以上）は自前の Nominatim インスタンスを推奨
- 結果の精度は OSM のデータ品質に依存する（日本は比較的充実、地方は薄い場合あり）
- User-Agent は必ず設定する（例: `gis-skills-geocoder/1.0`）。未設定だとブロックされる
- 座標が海上や無人地域の場合、逆ジオコーディングは結果を返さないことがある

## サービス選択ガイド

| ケース | 推奨サービス |
|--------|-------------|
| 日本国内の住所・地名 | 国土地理院（`gsi`） |
| 海外の住所・地名 | Nominatim（`nominatim`） |
| 大量バッチ処理 | 国土地理院（レートリミットが緩い） |
| 建物名・POI の詳細検索 | Nominatim（OSM のデータが豊富） |
