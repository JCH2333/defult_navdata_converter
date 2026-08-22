[CmdletBinding()]
param(
    [string]$Candidate,
    [string]$OutputZip
)

$ErrorActionPreference = 'Stop'
if (-not $Candidate) {
    $Candidate = Join-Path $PSScriptRoot '..\output\candidate-2608-default-r385-frozen-rebuild'
}
if (-not $OutputZip) {
    $OutputZip = Join-Path $PSScriptRoot '..\output\functional-test-navdata-2608-r385.zip'
}
$Candidate = (Resolve-Path -LiteralPath $Candidate).Path
$OutputZip = [IO.Path]::GetFullPath($OutputZip)
$stage = Join-Path ([IO.Path]::GetTempPath()) "functional-test-navdata-2608-r385_$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Force -Path $stage | Out-Null

try {
    $template = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\packaging\functional-test-2608')).Path
    Get-ChildItem -LiteralPath $template -Force | Copy-Item -Destination $stage -Recurse
    foreach ($name in @('zzz-pmdg-china-navdata', 'zzz-pmdg-china-navdata-airport-patch')) {
        $source = Join-Path $Candidate $name
        if (-not (Test-Path -LiteralPath $source -PathType Container)) {
            throw "候选缺少包: $source"
        }
        Copy-Item -LiteralPath $source -Destination (Join-Path $stage $name) -Recurse
    }

    $manifestPath = Join-Path $stage 'package-manifest.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($name in @('zzz-pmdg-china-navdata', 'zzz-pmdg-china-navdata-airport-patch')) {
        $root = Join-Path $stage $name
        $files = [ordered]@{}
        Get-ChildItem -LiteralPath $root -Recurse -File | Sort-Object FullName | ForEach-Object {
            $relative = $_.FullName.Substring($root.Length).TrimStart('\', '/').Replace('\', '/')
            $files[$relative] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
        $manifest.packages.$name.files = $files
    }
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

    if (Test-Path -LiteralPath $OutputZip) {
        Remove-Item -LiteralPath $OutputZip -Force
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $OutputZip -Parent) | Out-Null
    Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $OutputZip -CompressionLevel Optimal
    $zipHash = (Get-FileHash -LiteralPath $OutputZip -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Output "ZIP: $OutputZip"
    Write-Output "SHA256: $zipHash"
}
finally {
    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
}

