[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ServerPath,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ModelPath,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$MmprojPath,

    [ValidateNotNullOrEmpty()]
    [string]$Url = "http://127.0.0.1:8090",

    [ValidateRange(1024, 65536)]
    [int]$ContextSize = 8192,

    [ValidateNotNullOrEmpty()]
    [string]$GpuLayers = "all",

    [ValidateRange(1, 8)]
    [int]$Parallel = 1,

    [ValidateRange(1, 300)]
    [int]$StartupTimeoutSeconds = 90,

    [string]$LogRoot = (Join-Path $env:LOCALAPPDATA "default_navdata_converter\ocr-server")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-OcrHealth {
    param([Uri]$Endpoint)

    try {
        $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Uri ([Uri]::new($Endpoint, "health"))
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

foreach ($path in @($ServerPath, $ModelPath, $MmprojPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "找不到 OCR 运行时或模型文件: $path"
    }
}

$endpoint = [Uri]$Url
if ($endpoint.Scheme -ne "http" -or $endpoint.Host -notin @("127.0.0.1", "localhost")) {
    throw "本脚本只允许启动本机 HTTP OCR 服务: $Url"
}

if (Test-OcrHealth $endpoint) {
    [PSCustomObject]@{
        status = "already_ready"
        url = $endpoint.GetLeftPart([UriPartial]::Authority)
        started = $false
    } | ConvertTo-Json -Depth 3
    exit 0
}

$listener = Get-NetTCPConnection -LocalPort $endpoint.Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw "端口 $($endpoint.Port) 已被进程 $($listener[0].OwningProcess) 监听，但 /health 未通过；拒绝覆盖未知服务"
}

New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$stdout = Join-Path $LogRoot "llama-server-$timestamp.stdout.log"
$stderr = Join-Path $LogRoot "llama-server-$timestamp.stderr.log"
$arguments = @(
    "--model", (Resolve-Path -LiteralPath $ModelPath),
    "--mmproj", (Resolve-Path -LiteralPath $MmprojPath),
    "--ctx-size", "$ContextSize",
    "--gpu-layers", $GpuLayers,
    "--host", $endpoint.Host,
    "--port", "$($endpoint.Port)",
    "--parallel", "$Parallel",
    "--no-webui"
)
$process = Start-Process `
    -FilePath (Resolve-Path -LiteralPath $ServerPath) `
    -ArgumentList $arguments `
    -WorkingDirectory (Split-Path -Parent (Resolve-Path -LiteralPath $ServerPath)) `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -WindowStyle Hidden `
    -PassThru

$deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 1
    if (Test-OcrHealth $endpoint) {
        [PSCustomObject]@{
            status = "ready"
            url = $endpoint.GetLeftPart([UriPartial]::Authority)
            started = $true
            process_id = $process.Id
            stdout = $stdout
            stderr = $stderr
        } | ConvertTo-Json -Depth 3
        exit 0
    }
    if ($process.HasExited) {
        throw "OCR 服务启动后退出，退出代码 $($process.ExitCode)。日志: $stderr"
    }
}

throw "OCR 服务未在 $StartupTimeoutSeconds 秒内通过健康检查。日志: $stderr"
