[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$CommunityPath,
    [Parameter(Mandatory = $true)]
    [string]$BackupPath
)

$ErrorActionPreference = 'Stop'
$PackageNames = @('zzz-pmdg-china-navdata', 'zzz-pmdg-china-navdata-airport-patch')

function Assert-CommunityPath([string]$Path) {
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    if ((Split-Path -Leaf $resolved) -ne 'Community') {
        throw "CommunityPath 必须指向名为 Community 的现有目录: $resolved"
    }
    return $resolved
}

if (Get-Process -Name 'FlightSimulator2024' -ErrorAction SilentlyContinue) {
    throw 'FlightSimulator2024.exe 正在运行。请完全退出 MSFS 2024 后重新执行。'
}

$CommunityPath = Assert-CommunityPath $CommunityPath
$BackupPath = (Resolve-Path -LiteralPath $BackupPath).Path
$installManifestPath = Join-Path $BackupPath 'install-manifest.json'
if (-not (Test-Path -LiteralPath $installManifestPath -PathType Leaf)) {
    throw "备份中缺少安装清单: $installManifestPath"
}
$installManifest = Get-Content -LiteralPath $installManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$previousPackageNames = @($installManifest.previous_custom_packages)

foreach ($name in $PackageNames) {
    $destination = Join-Path $CommunityPath $name
    $saved = Join-Path $BackupPath $name
    if (Test-Path -LiteralPath $destination) {
        Remove-Item -LiteralPath $destination -Recurse -Force
    }
    if ($name -in $previousPackageNames) {
        if (-not (Test-Path -LiteralPath $saved -PathType Container)) {
            throw "备份中缺少原有自定义包: $saved"
        }
        Copy-Item -LiteralPath $saved -Destination $destination -Recurse
    }
}

Write-Host '自定义中国区域包已恢复。官方 Navigraph 包未修改。'

