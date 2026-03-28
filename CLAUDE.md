# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

GIS（地理情報システム）関連タスクを処理する4つの Claude Code スキルのコレクション。各スキルは独立したディレクトリに `SKILL.md`、`scripts/`、`references/` を持つ。

| スキル | ディレクトリ | 主な依存 | 用途 |
|--------|-------------|----------|------|
| gis-coord-transform | `gis-coord-transform/` | pyproj, jgdtrans | 座標変換・投影法変換・測地系変換・タイル座標・メッシュコード |
| gis-geocoding | `gis-geocoding/` | requests | 住所・地名→座標、座標→住所（国土地理院API/Nominatim） |
| gis-spatial-index | `gis-spatial-index/` | h3, openlocationcode, mgrs | Geohash/H3/Plus Code/Quadkey/MGRS/Maidenhead/Morton 空間インデックス |
| gis-elevation | `gis-elevation/` | Pillow, requests | 国土地理院 DEM タイルから標高取得（5m/10mフォールバック）・断面図 |

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
- 各スクリプトにも `_auto_install()` を内蔵する（スキル経由でなく単体実行されるケースに対応）
- scripts/ の出力は JSON 形式を基本とする（Claude がパースしやすい）
- 型ヒントで `str | None` 等の union 構文を使う場合は `from __future__ import annotations` を入れる（Python 3.9 互換）
- SKILL.md の `description` はトリガーキーワードを網羅的に含める（ユーザーがどんな言い回しでも発火するように）
- references/ には Claude の生成精度を上げるルックアップテーブルや仕様を置く（コードではなく知識）
- SKILL.md 内のパス参照には `${CLAUDE_SKILL_DIR}` を使う

## バージョン管理

- バージョンは `VERSION` ファイル（ルート直下）で管理する（セマンティックバージョニング）
- リリース時は `VERSION` と `README.md` のバッジ (`img.shields.io/badge/version-X.Y.Z-blue`) を同時に更新する

## Git Worktree による並行開発

複数スキルを同時に開発する場合、git worktree で各フィーチャーブランチを並行作業する。

### ディレクトリ構成

```
gis-skills/                                        ← main ブランチ（メインワークツリー）
├── .claude/
│   └── worktrees/
│       ├── feat-gis-elevation/                    ← feat/gis-elevation
│       ├── feat-gis-geocoding/                    ← feat/gis-geocoding
│       └── fix-gis-spatial-index/                 ← fix/gis-spatial-index
```

`.claude/` は `.gitignore` 済みのため、worktree ディレクトリは git に無視される。

### 命名規則

- **worktree ディレクトリ名**: ブランチ名の `/` を `-` に置換（例: `feat/gis-elevation` → `feat-gis-elevation`）
- **ブランチ名**: `feat/gis-*`、`fix/gis-*` 等のプレフィックス付き

### ワークフロー

```bash
# 新規ブランチで worktree を作成
git worktree add .claude/worktrees/feat-gis-elevation -b feat/gis-elevation

# 既存ブランチで worktree を作成
git worktree add .claude/worktrees/feat-gis-elevation feat/gis-elevation

# worktree 内で作業
cd .claude/worktrees/feat-gis-elevation

# worktree 内でスキルをテストインストール
./setup.sh --user

# 一覧確認
git worktree list

# PR マージ後にクリーンアップ
git worktree remove .claude/worktrees/feat-gis-elevation

# 不要な worktree 参照を掃除
git worktree prune
```

### 注意事項

- メインワークツリー（リポジトリルート）は常に `main` ブランチを維持する
- 同じブランチを複数の worktree で checkout できない（git の制約）
- worktree 内で `./setup.sh --user` を実行すると開発版スキルがインストールされる。テスト後は main に戻って `./setup.sh --user` で安定版に戻すこと
