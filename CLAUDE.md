# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

GIS（地理情報システム）関連タスクを処理する2つの Claude Code スキルのコレクション。各スキルは独立したディレクトリに `SKILL.md`、`scripts/`、`references/` を持つ。

| スキル | ディレクトリ | 主な依存 | 用途 |
|--------|-------------|----------|------|
| gis-coord-transform | `gis-coord-transform/` | pyproj, jgdtrans | 座標変換・投影法変換・測地系変換・タイル座標・メッシュコード |
| gis-geocoding | `gis-geocoding/` | geopy, requests | 住所・地名→座標、座標→住所（国土地理院API/Nominatim） |

> **Note:** GIS データ変換（GeoJSON/Shapefile/KML/GeoPackage/CSV 間）はスキル化していない。Claude が geopandas/fiona のコードを直接生成すれば十分なため。

## 依存パッケージ

各スクリプトは実行時に依存パッケージの有無を確認し、未インストールの場合は自動で `pip install` する。手動でのセットアップは不要。

## アーキテクチャ

各スキルは同一構造:
- `SKILL.md` — スキル定義（メタデータ + ワークフロー手順）。Claude Code がスキルとしてロードする
- `scripts/` — Python CLI ツール群。各スクリプトは独立して `python3 scripts/xxx.py --help` で実行可能
- `references/` — Markdown リファレンス資料。スキル実行時に参照する座標系定義、フォーマット仕様等

## GIS 作業で守るべきルール

- pyproj の `Transformer` には必ず `always_xy=True` を指定する（経度・緯度の順序を統一）
- 距離・面積計算は投影座標系（平面直角座標系等）で行う。地理座標系 (EPSG:4326) のまま計算してはいけない
- GeoJSON 出力は WGS84 (EPSG:4326) にする（RFC 7946 準拠）
- 日本の Shapefile は cp932 エンコーディングが多い
- 旧測地系→JGD2011 の高精度変換は TKY2JGD → PatchJGD の二段階で行う

## バージョン管理

- バージョンは `VERSION` ファイル（ルート直下）で管理する（セマンティックバージョニング）
- リリース時は `VERSION` と `README.md` のバッジ (`img.shields.io/badge/version-X.Y.Z-blue`) を同時に更新する
