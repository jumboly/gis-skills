# よく使う EPSG コード一覧

## 地理座標系（Geographic CRS）

| EPSG | 名称 | 測地系 | 楕円体 | 用途 |
|------|------|--------|--------|------|
| 4326 | WGS 84 | WGS84 | WGS84 | GPS、世界標準、Web地図 |
| 4301 | Tokyo | 旧日本測地系 | Bessel 1841 | 旧測地系データ |
| 4612 | JGD2000 | JGD2000 | GRS80 | 2002〜2011年の日本測量 |
| 6668 | JGD2011 | JGD2011 | GRS80 | 2011年〜現在の日本測量 |

## 投影座標系（Projected CRS）

### 日本の平面直角座標系（JGD2011）
EPSG 6669〜6687（I系〜XIX系）→ `japanese-plane-rect.md` を参照

### 日本の平面直角座標系（JGD2000）
EPSG 2443〜2461（I系〜XIX系）

### UTM（Universal Transverse Mercator）

| EPSG | UTMゾーン | 対応地域（日本） |
|------|-----------|------------------|
| 32651 | 51N (WGS84) | 沖縄西部 |
| 32652 | 52N (WGS84) | 九州・沖縄 |
| 32653 | 53N (WGS84) | 中国・四国・近畿 |
| 32654 | 54N (WGS84) | 中部・関東・東北 |
| 32655 | 55N (WGS84) | 北海道・東北 |
| 32656 | 56N (WGS84) | 北海道東部 |

### Web 地図

| EPSG | 名称 | 用途 |
|------|------|------|
| 3857 | Web Mercator | Google Maps、OpenStreetMap、地理院タイル |

## 測地系の関係

```
Tokyo Datum (EPSG:4301)
  ├── TKY2JGD (.par) ──→ JGD2000 (EPSG:4612)
  │                         ├── PatchJGD (.par) ──→ JGD2011 (EPSG:6668)
  │                         └── pyproj 変換 ────→ JGD2011 (EPSG:6668)
  └── pyproj 変換 ────────→ JGD2011 (EPSG:6668)
```

## EPSG コードの調べ方

- pyproj: `pyproj.database.query_crs_info(auth_name="EPSG", area_of_use_contains=...)`
- Web: https://epsg.io/
