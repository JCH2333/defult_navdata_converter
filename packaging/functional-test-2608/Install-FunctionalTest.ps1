[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$CommunityPath,
    [string]$BackupRoot
)

$ErrorActionPreference = 'Stop'
$PackageNames = @('zzz-pmdg-china-navdata', 'zzz-pmdg-china-navdata-airport-patch')
$OfficialPackageNames = @('navigraph-nav-base', 'navigraph-nav-jepp')
$PackageRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path

function Get-FileHashes([string]$Root) {
    $result = @{}
    Get-ChildItem -LiteralPath $Root -Recurse -File | ForEach-Object {
        $relative = $_.FullName.Substring($Root.Length).TrimStart('\', '/').Replace('\', '/')
        $result[$relative] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    return $result
}

function Assert-CommunityPath([string]$Path) {
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    if ((Split-Path -Leaf $resolved) -ne 'Community') {
        throw "CommunityPath 必须指向名为 Community 的现有目录: $resolved"
    }
    if ($resolved -eq [IO.Path]::GetPathRoot($resolved)) {
        throw "拒绝把磁盘根目录作为 CommunityPath: $resolved"
    }
    return $resolved
}

if (Get-Process -Name 'FlightSimulator2024' -ErrorAction SilentlyContinue) {
    throw 'FlightSimulator2024.exe 正在运行。请完全退出 MSFS 2024 后重新执行。'
}

$CommunityPath = Assert-CommunityPath $CommunityPath
$manifestPath = Join-Path $PackageRoot 'package-manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "缺少 package-manifest.json: $manifestPath"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json

foreach ($name in $OfficialPackageNames) {
    $official = Join-Path $CommunityPath $name
    if (-not (Test-Path -LiteralPath $official -PathType Container)) {
        throw "缺少官方 2608 包 $name。请先安装/启用官方 Navigraph 2608 数据。"
    }
}

foreach ($name in $PackageNames) {
    $source = Join-Path $PackageRoot $name
    foreach ($required in @('manifest.json', 'layout.json', 'bglIndex.bout')) {
        if (-not (Test-Path -LiteralPath (Join-Path $source $required) -PathType Leaf)) {
            throw "自定义包不完整，缺少 $name/$required"
        }
    }
    if (-not (Get-ChildItem -LiteralPath $source -Recurse -Filter '*.bgl' -File)) {
        throw "自定义包不完整，未找到 BGL: $name"
    }
    $expected = $manifest.packages.$name.files
    $actual = Get-FileHashes $source
    foreach ($property in $expected.PSObject.Properties) {
        if ($actual[$property.Name] -ne $property.Value) {
            throw "文件校验失败: $name/$($property.Name)"
        }
    }
}

if (-not $BackupRoot) {
    $BackupRoot = Join-Path (Split-Path $CommunityPath -Parent) 'backups'
}
$BackupRoot = [IO.Path]::GetFullPath($BackupRoot)
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = Join-Path $BackupRoot "functional-test-2608-r385_$stamp"
$suffix = 2
while (Test-Path -LiteralPath $backup) {
    $backup = Join-Path $BackupRoot "functional-test-2608-r385_${stamp}_$suffix"
    $suffix++
}
New-Item -ItemType Directory -Force -Path $backup | Out-Null

$backupPackages = @{}
$previousPackageNames = @()
try {
    foreach ($name in $PackageNames) {
        $destination = Join-Path $backup $name
        $existing = Join-Path $CommunityPath $name
        if (Test-Path -LiteralPath $existing -PathType Container) {
            Copy-Item -LiteralPath $existing -Destination $destination -Recurse
            $backupPackages[$name] = Get-FileHashes $destination
            $previousPackageNames += $name
        }
    }

    foreach ($name in $PackageNames) {
        $source = Join-Path $PackageRoot $name
        $temporary = Join-Path $CommunityPath ".${name}.functional-test-new"
        $destination = Join-Path $CommunityPath $name
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Recurse -Force
        }
        Copy-Item -LiteralPath $source -Destination $temporary -Recurse
        if (Test-Path -LiteralPath $destination) {
            Remove-Item -LiteralPath $destination -Recurse -Force
        }
        Move-Item -LiteralPath $temporary -Destination $destination
    }

    $stage = [ordered]@{
        kind = 'functional-test-package-install'
        installed_at = (Get-Date).ToString('o')
        community_path = $CommunityPath
        backup_path = $backup
        official_packages_preserved = $OfficialPackageNames
        custom_packages_installed = $PackageNames
        previous_custom_packages = $previousPackageNames
        package_manifest_sha256 = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
        previous_custom_package_hashes = $backupPackages
    }
    $stage | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $backup 'install-manifest.json') -Encoding UTF8
}
catch {
    foreach ($name in $PackageNames) {
        $destination = Join-Path $CommunityPath $name
        $saved = Join-Path $backup $name
        if (Test-Path -LiteralPath $destination) {
            Remove-Item -LiteralPath $destination -Recurse -Force
        }
        if (Test-Path -LiteralPath $saved) {
            Copy-Item -LiteralPath $saved -Destination $destination -Recurse
        }
    }
    throw
}

Write-Host '安装完成。官方包未修改。'
Write-Host "备份路径: $backup"
Write-Host '测试结束后使用 Restore-FunctionalTest.ps1 恢复。'

