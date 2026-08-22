[CmdletBinding()]
param(
    [string]$PackageZip
)

$ErrorActionPreference = 'Stop'
if (-not $PackageZip) {
    $PackageZip = Join-Path $PSScriptRoot '..\output\functional-test-navdata-2608-r385.zip'
}
$PackageZip = (Resolve-Path -LiteralPath $PackageZip).Path
$root = Join-Path ([IO.Path]::GetTempPath()) "navdata-functional-test-verify_$([guid]::NewGuid().ToString('N'))"
$community = Join-Path $root 'Community'
$extract = Join-Path $root 'package'
$backups = Join-Path $root 'backups'
$custom = @('zzz-pmdg-china-navdata', 'zzz-pmdg-china-navdata-airport-patch')

try {
    New-Item -ItemType Directory -Force -Path $community, $extract, $backups | Out-Null
    Expand-Archive -LiteralPath $PackageZip -DestinationPath $extract
    foreach ($name in @('navigraph-nav-base', 'navigraph-nav-jepp')) {
        $official = Join-Path $community $name
        New-Item -ItemType Directory -Force -Path $official | Out-Null
        Set-Content -LiteralPath (Join-Path $official 'official.txt') -Value $name -NoNewline
    }
    foreach ($name in $custom) {
        $old = Join-Path $community $name
        New-Item -ItemType Directory -Force -Path $old | Out-Null
        Set-Content -LiteralPath (Join-Path $old 'old.txt') -Value 'old' -NoNewline
    }

    & (Join-Path $extract 'Install-FunctionalTest.ps1') -CommunityPath $community -BackupRoot $backups
    $backup = (Get-ChildItem -LiteralPath $backups -Directory | Select-Object -First 1).FullName
    if (-not $backup) { throw '安装脚本未创建备份目录' }
    foreach ($name in $custom) {
        if (-not (Test-Path -LiteralPath (Join-Path $community "$name\manifest.json") -PathType Leaf)) {
            throw "安装后缺少自定义包: $name"
        }
    }
    foreach ($name in @('navigraph-nav-base', 'navigraph-nav-jepp')) {
        if ((Get-Content -LiteralPath (Join-Path $community "$name\official.txt") -Raw) -ne $name) {
            throw "官方包被修改: $name"
        }
    }

    & (Join-Path $extract 'Restore-FunctionalTest.ps1') -CommunityPath $community -BackupPath $backup
    foreach ($name in $custom) {
        if ((Get-Content -LiteralPath (Join-Path $community "$name\old.txt") -Raw) -ne 'old') {
            throw "恢复后未找回原有自定义包: $name"
        }
    }

    foreach ($name in $custom) {
        $old = Join-Path $community $name
        Remove-Item -LiteralPath $old -Recurse -Force
    }
    & (Join-Path $extract 'Install-FunctionalTest.ps1') -CommunityPath $community -BackupRoot $backups | Out-Null
    $emptyBackup = (Get-ChildItem -LiteralPath $backups -Directory | Sort-Object Name | Select-Object -Last 1).FullName
    & (Join-Path $extract 'Restore-FunctionalTest.ps1') -CommunityPath $community -BackupPath $emptyBackup | Out-Null
    foreach ($name in $custom) {
        if (Test-Path -LiteralPath (Join-Path $community $name)) {
            throw "恢复后错误保留了原本不存在的自定义包: $name"
        }
    }
    [pscustomobject]@{
        verified = $true
        package_zip = $PackageZip
        extracted_files = (Get-ChildItem -LiteralPath $extract -Recurse -File).Count
        backup_manifest = (Test-Path -LiteralPath (Join-Path $backup 'install-manifest.json') -PathType Leaf)
        official_packages_preserved = $true
        custom_packages_restored = $true
        empty_original_state_restored = $true
    } | ConvertTo-Json -Compress
}
finally {
    if (Test-Path -LiteralPath $root) {
        Remove-Item -LiteralPath $root -Recurse -Force
    }
}



