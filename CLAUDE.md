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

## スキル設計のベストプラクティス

### スキル化しない（Claude が直接コードを書けばよい場合）

- Claude が既知のライブラリ（geopandas, fiona, shapely 等）のコードを直接生成すれば十分な場合
- ライブラリ API の薄いラッパーにしかならない場合（例: 削除済みの gis-spatial-analysis, gis-data-convert）
- 単発の変換・計算で、判断分岐やフォールバックロジックが不要な場合

### スキル化する条件

以下のいずれかに該当する場合、スキルとしての付加価値がある:

- **非自明な判断ロジック** — どの座標系・サービス・変換手法を選ぶか、条件分岐が複雑
- **専門知識の補完** — Claude の学習データだけでは不十分な情報を references/ で提供する必要がある（日本固有の座標系定義、API 仕様、パラメータファイル形式等）
- **複数手法の使い分けとフォールバック** — サービス障害時の代替手段、精度要件による手法切替など
- **再利用性の高い CLI ツール** — バッチ処理・CSV 入出力など、繰り返し使われるワークフローを scripts/ で提供

### スキル修正時の注意

- **常にこのリポジトリのソースを編集する**。`~/.claude/skills/` や `<project>/.claude/skills/` にあるファイルはインストール済みコピーであり、直接編集してはいけない
- 修正後は `setup.sh` で再インストールしてコピーを更新する

### スキル実装時の設計指針

- scripts/ の各スクリプトは単体で `python3 scripts/xxx.py --help` で実行可能にする
- 依存パッケージは `ensure_deps.py` パターンで実行時に自動インストールする（手動セットアップ不要）
- SKILL.md の `description` はトリガーキーワードを網羅的に含める（ユーザーがどんな言い回しでも発火するように）
- references/ には Claude の生成精度を上げるルックアップテーブルや仕様を置く（コードではなく知識）
- SKILL.md 内のパス参照には `${CLAUDE_SKILL_DIR}` を使う

## バージョン管理

- バージョンは `VERSION` ファイル（ルート直下）で管理する（セマンティックバージョニング）
- リリース時は `VERSION` と `README.md` のバッジ (`img.shields.io/badge/version-X.Y.Z-blue`) を同時に更新する
