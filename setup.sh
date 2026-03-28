#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS=(gis-coord-transform gis-geocoding gis-spatial-index gis-elevation)
NEW_VERSION="$(cat "$SCRIPT_DIR/VERSION" 2>/dev/null | tr -d '[:space:]')"
[[ -z "$NEW_VERSION" ]] && { echo "エラー: VERSION ファイルが見つかりません"; exit 1; }

usage() {
  cat <<'EOF'
使い方: ./setup.sh [install|uninstall] [--user|--project <path>] [--force]

操作:
  install     スキルをインストール（デフォルト）
  uninstall   スキルをアンインストール

インストール先:
  --user              ~/.claude/skills/ にインストール（全プロジェクトで使用可能）
  --project <path>    指定プロジェクトの .claude/skills/ にインストール

オプション:
  --force    確認なしでインストール/更新

例:
  ./setup.sh --user
  ./setup.sh --project /path/to/my-project
  ./setup.sh uninstall --user
  ./setup.sh uninstall --project /path/to/my-project
EOF
  exit 1
}

ACTION=install
SCOPE=""
PROJECT_PATH=""
FORCE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    install)   ACTION=install; shift ;;
    uninstall) ACTION=uninstall; shift ;;
    --user)    SCOPE=user; shift ;;
    --project)
      SCOPE=project
      [[ $# -lt 2 ]] && { echo "エラー: --project にはパスの指定が必要です"; exit 1; }
      PROJECT_PATH="$2"; shift 2 ;;
    --force) FORCE=true; shift ;;
    *) echo "エラー: 不明な引数 '$1'"; usage ;;
  esac
done

[[ -z "$SCOPE" ]] && usage

if [[ "$SCOPE" == "user" ]]; then
  DEST="$HOME/.claude/skills"
else
  [[ ! -d "$PROJECT_PATH" ]] && { echo "エラー: ディレクトリ '$PROJECT_PATH' が存在しません"; exit 1; }
  DEST="$PROJECT_PATH/.claude/skills"
fi

VERSION_FILE="$DEST/.gis-skills-version"

get_installed_version() {
  if [[ -f "$VERSION_FILE" ]]; then
    cat "$VERSION_FILE" | tr -d '[:space:]'
  else
    echo ""
  fi
}

# インストール済みスキルが1つでもあるか
has_installed_skills() {
  for skill in "${SKILLS[@]}"; do
    [[ -d "$DEST/$skill" ]] && return 0
  done
  return 1
}

show_deps() {
  echo ""
  echo "依存パッケージ（初回実行時に自動インストールされます）:"
  for skill in "${SKILLS[@]}"; do
    local deps_script="$SCRIPT_DIR/$skill/scripts/ensure_deps.py"
    if [[ -f "$deps_script" ]]; then
      local pkgs
      pkgs="$(python3 -c "
import ast, sys
tree = ast.parse(open(sys.argv[1]).read())
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == 'REQUIRED':
                d = ast.literal_eval(node.value)
                print(', '.join(d.values()))
" "$deps_script" 2>/dev/null)" || true
      echo "  $skill: $pkgs"
    fi
  done
}

copy_skills() {
  local label="$1"
  for skill in "${SKILLS[@]}"; do
    local src="$SCRIPT_DIR/$skill"
    local dst="$DEST/$skill"

    if [[ ! -d "$src" ]]; then
      echo "  警告: $src が見つかりません、スキップします"
      continue
    fi

    mkdir -p "$dst"
    rm -rf "$dst"
    cp -r "$src" "$dst"
    echo "  ${label}: $skill"
  done

  # バージョンを記録
  echo "$NEW_VERSION" > "$VERSION_FILE"
}

do_install() {
  local installed_version
  installed_version="$(get_installed_version)"

  if has_installed_skills; then
    local from="${installed_version:-不明}"

    # 同一バージョンかつ --force でない場合はスキップ
    if [[ "$installed_version" == "$NEW_VERSION" && "$FORCE" == false ]]; then
      echo "gis-skills は最新です (v${NEW_VERSION})"
      return
    fi

    # 更新確認
    if [[ "$FORCE" == false ]]; then
      read -rp "gis-skills を更新しますか？ (v${from} → v${NEW_VERSION}) [y/N] " ans
      [[ "$ans" != [yY] ]] && { echo "中止しました"; return; }
    fi

    copy_skills "更新"
    show_deps

    if [[ "$installed_version" == "$NEW_VERSION" ]]; then
      echo ""
      echo "完了! gis-skills v${NEW_VERSION} を再インストールしました"
    else
      echo ""
      echo "完了! gis-skills を v${from} → v${NEW_VERSION} に更新しました"
    fi
  else
    # 新規インストール
    copy_skills "インストール"
    show_deps
    echo ""
    echo "完了! gis-skills v${NEW_VERSION} をインストールしました"
  fi
}

do_uninstall() {
  local removed=0

  for skill in "${SKILLS[@]}"; do
    local dst="$DEST/$skill"
    if [[ -d "$dst" ]]; then
      rm -rf "$dst"
      echo "  削除: $skill"
      removed=$((removed + 1))
    fi
  done

  if [[ $removed -eq 0 ]]; then
    echo "$DEST にスキルが見つかりません"
    return
  fi

  # バージョンファイルも削除
  rm -f "$VERSION_FILE"

  # skills/ が空なら削除（.claude/ は残す）
  if [[ -d "$DEST" ]] && [[ -z "$(ls -A "$DEST" 2>/dev/null)" ]]; then
    rmdir "$DEST"
  fi

  echo ""
  echo "完了! $DEST から ${removed} 個のスキルを削除しました"
}

if [[ "$ACTION" == "install" ]]; then
  do_install
else
  do_uninstall
fi
