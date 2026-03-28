<#
.SYNOPSIS
    GIS スキルを Claude Code にインストール/アンインストールする。

.EXAMPLE
    .\setup.ps1 -Scope User
    .\setup.ps1 -Scope Project -ProjectPath C:\path\to\my-project
    .\setup.ps1 -Action Uninstall -Scope User
#>
[CmdletBinding()]
param(
    [ValidateSet("Install", "Uninstall")]
    [string]$Action = "Install",

    [Parameter(Mandatory)]
    [ValidateSet("User", "Project")]
    [string]$Scope,

    [string]$ProjectPath,

    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Skills = @("gis-coord-transform", "gis-spatial-analysis", "gis-data-convert", "gis-geocoding")

$VersionFile = Join-Path $PSScriptRoot "VERSION"
if (-not (Test-Path $VersionFile)) {
    Write-Error "VERSION ファイルが見つかりません"
    exit 1
}
$NewVersion = (Get-Content $VersionFile -Raw).Trim()

if ($Scope -eq "Project" -and -not $ProjectPath) {
    Write-Error "-Scope Project には -ProjectPath の指定が必要です"
    exit 1
}

if ($Scope -eq "User") {
    $Dest = Join-Path $HOME ".claude" "skills"
} else {
    if (-not (Test-Path $ProjectPath -PathType Container)) {
        Write-Error "ディレクトリ '$ProjectPath' が存在しません"
        exit 1
    }
    $Dest = Join-Path $ProjectPath ".claude" "skills"
}

$InstalledVersionFile = Join-Path $Dest ".gis-skills-version"

function Get-InstalledVersion {
    if (Test-Path $InstalledVersionFile) {
        return (Get-Content $InstalledVersionFile -Raw).Trim()
    }
    return ""
}

function Test-HasInstalledSkills {
    foreach ($skill in $Skills) {
        if (Test-Path (Join-Path $Dest $skill)) { return $true }
    }
    return $false
}

function Install-Deps {
    Write-Host ""
    Write-Host "依存パッケージを確認しています..."
    $hasError = $false

    foreach ($skill in $Skills) {
        $depsScript = Join-Path $PSScriptRoot $skill "scripts" "ensure_deps.py"
        if (Test-Path $depsScript) {
            try {
                $output = & python3 $depsScript 2>$null
                $result = $output | ConvertFrom-Json

                if ($result.status -eq "ok") {
                    if ($result.installed -and $result.installed.Count -gt 0) {
                        Write-Host "  ${skill}: インストール済み ($($result.installed -join ', '))"
                    } else {
                        Write-Host "  ${skill}: OK"
                    }
                } elseif ($result.status -eq "partial") {
                    $hasError = $true
                    Write-Host "  ${skill}: 一部失敗"
                    if ($result.hint) {
                        Write-Host "    → $($result.hint)"
                    }
                } else {
                    Write-Host "  ${skill}: 確認完了"
                }
            } catch {
                Write-Host "  ${skill}: 確認完了"
            }
        }
    }

    if ($hasError) {
        Write-Host ""
        Write-Host "※ 一部パッケージのインストールに失敗しました。上記のヒントを参照してください。"
    }
}

function Copy-Skills {
    param([string]$Label)

    foreach ($skill in $Skills) {
        $src = Join-Path $PSScriptRoot $skill
        $dst = Join-Path $Dest $skill

        if (-not (Test-Path $src -PathType Container)) {
            Write-Warning "$src が見つかりません、スキップします"
            continue
        }

        if (Test-Path $dst) {
            Remove-Item -Recurse -Force $dst
        }
        New-Item -ItemType Directory -Path $dst -Force | Out-Null
        Copy-Item -Recurse -Force (Join-Path $src "*") $dst
        Write-Host "  ${Label}: $skill"
    }

    # バージョンを記録
    New-Item -ItemType Directory -Path $Dest -Force | Out-Null
    Set-Content -Path $InstalledVersionFile -Value $NewVersion -NoNewline
}

function Do-Install {
    $installedVersion = Get-InstalledVersion

    if (Test-HasInstalledSkills) {
        $from = if ($installedVersion) { $installedVersion } else { "不明" }

        # 同一バージョンかつ -Force でない場合はスキップ
        if ($installedVersion -eq $NewVersion -and -not $Force) {
            Write-Host "gis-skills は最新です (v${NewVersion})"
            return
        }

        # 更新確認
        if (-not $Force) {
            $ans = Read-Host "gis-skills を更新しますか？ (v${from} → v${NewVersion}) [y/N]"
            if ($ans -ne "y" -and $ans -ne "Y") {
                Write-Host "中止しました"
                return
            }
        }

        Copy-Skills -Label "更新"
        Install-Deps

        if ($installedVersion -eq $NewVersion) {
            Write-Host ""
            Write-Host "完了! gis-skills v${NewVersion} を再インストールしました"
        } else {
            Write-Host ""
            Write-Host "完了! gis-skills を v${from} → v${NewVersion} に更新しました"
        }
    } else {
        # 新規インストール
        Copy-Skills -Label "インストール"
        Install-Deps
        Write-Host ""
        Write-Host "完了! gis-skills v${NewVersion} をインストールしました"
    }
}

function Do-Uninstall {
    $removed = 0

    foreach ($skill in $Skills) {
        $dst = Join-Path $Dest $skill
        if (Test-Path $dst) {
            Remove-Item -Recurse -Force $dst
            Write-Host "  削除: $skill"
            $removed++
        }
    }

    if ($removed -eq 0) {
        Write-Host "$Dest にスキルが見つかりません"
        return
    }

    # バージョンファイルも削除
    if (Test-Path $InstalledVersionFile) {
        Remove-Item $InstalledVersionFile
    }

    # skills/ が空なら削除（.claude/ は残す）
    if ((Test-Path $Dest) -and @(Get-ChildItem $Dest).Count -eq 0) {
        Remove-Item $Dest
    }

    Write-Host ""
    Write-Host "完了! $Dest から $removed 個のスキルを削除しました"
}

if ($Action -eq "Install") {
    Do-Install
} else {
    Do-Uninstall
}
