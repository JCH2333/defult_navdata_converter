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

    [ValidateRange(0, 2147483647)]
    [int]$Seed = 2608,

    [ValidateRange(0.0, 2.0)]
    [double]$Temperature = 0.0,

    [ValidateRange(1, 300)]
    [int]$StartupTimeoutSeconds = 90,

    [string]$LogRoot = (Join-Path $env:LOCALAPPDATA "default_navdata_converter\ocr-server"),

    [switch]$Restart
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

function Get-OcrProperties {
    param([Uri]$Endpoint)

    try {
        $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Uri ([Uri]::new($Endpoint, "props"))
        return $response.Content | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Test-OcrRuntime {
    param(
        [Uri]$Endpoint,
        [string]$ExpectedModel,
        [int]$ExpectedSeed,
        [double]$ExpectedTemperature
    )

    $properties = Get-OcrProperties $Endpoint
    if ($null -eq $properties) {
        return $false
    }
    $modelPath = [string]$properties.model_path
    $params = $properties.default_generation_settings.params
    if ($null -eq $params) {
        return $false
    }
    return (
        [System.IO.Path]::GetFullPath($modelPath) -eq [System.IO.Path]::GetFullPath($ExpectedModel) -and
        [int64]$params.seed -eq $ExpectedSeed -and
        [math]::Abs(([double]$params.temperature) - $ExpectedTemperature) -lt 0.000001
    )
}

function Get-OcrRuntimeDescriptor {
    param(
        [string]$Server,
        [string]$Model,
        [string]$Mmproj,
        [int]$RuntimeSeed,
        [double]$RuntimeTemperature,
        [Uri]$Endpoint
    )

    $versionStart = [System.Diagnostics.ProcessStartInfo]::new()
    $versionStart.FileName = $Server
    $versionStart.Arguments = "--version"
    $versionStart.UseShellExecute = $false
    $versionStart.CreateNoWindow = $true
    $versionStart.RedirectStandardOutput = $true
    $versionStart.RedirectStandardError = $true
    $versionProcess = [System.Diagnostics.Process]::Start($versionStart)
    $versionText = (
        $versionProcess.StandardOutput.ReadToEnd() +
        [Environment]::NewLine +
        $versionProcess.StandardError.ReadToEnd()
    )
    $versionProcess.WaitForExit()
    $match = [regex]::Match($versionText, "version:\s*(?<build>\d+)")
    if (-not $match.Success) {
        throw "无法读取 llama-server 构建号"
    }
    $build = "b$($match.Groups["build"].Value)"
    $modelName = [System.IO.Path]::GetFileNameWithoutExtension($Model).ToLowerInvariant()
    $temperatureText = $RuntimeTemperature.ToString(
        "0.################",
        [System.Globalization.CultureInfo]::InvariantCulture
    )
    $modelSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $Model).Hash.ToLowerInvariant()
    $mmprojSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $Mmproj).Hash.ToLowerInvariant()
    $runtimeProfile = (
        "$modelName-llama-$build-seed$RuntimeSeed-temp$temperatureText-" +
        "$modelSha256-$mmprojSha256"
    )
    return [PSCustomObject]@{
        schema_version = 1
        runtime_profile = $runtimeProfile
        llama_build = $build
        model_name = $modelName
        model_path = $Model
        model_sha256 = $modelSha256
        mmproj_path = $Mmproj
        mmproj_sha256 = $mmprojSha256
        seed = $RuntimeSeed
        temperature = $RuntimeTemperature
        url = $Endpoint.GetLeftPart([UriPartial]::Authority)
    }
}

function Write-OcrRuntimeDescriptor {
    param(
        [string]$Root,
        [object]$Descriptor
    )

    $path = Join-Path $Root "runtime-profile.json"
    $temporary = "$path.tmp"
    $Descriptor | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $temporary -Encoding utf8
    Move-Item -LiteralPath $temporary -Destination $path -Force
    return $path
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

$resolvedServer = (Resolve-Path -LiteralPath $ServerPath).Path
$resolvedModel = (Resolve-Path -LiteralPath $ModelPath).Path
$resolvedMmproj = (Resolve-Path -LiteralPath $MmprojPath).Path
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$runtimeDescriptor = Get-OcrRuntimeDescriptor `
    -Server $resolvedServer `
    -Model $resolvedModel `
    -Mmproj $resolvedMmproj `
    -RuntimeSeed $Seed `
    -RuntimeTemperature $Temperature `
    -Endpoint $endpoint
$runtimeDescriptorPath = Join-Path $LogRoot "runtime-profile.json"
$listener = Get-NetTCPConnection -LocalPort $endpoint.Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (Test-OcrHealth $endpoint) {
    if (Test-OcrRuntime $endpoint $resolvedModel $Seed $Temperature) {
        $runtimeDescriptorPath = Write-OcrRuntimeDescriptor `
            -Root $LogRoot `
            -Descriptor $runtimeDescriptor
        [PSCustomObject]@{
            status = "already_ready"
            url = $endpoint.GetLeftPart([UriPartial]::Authority)
            started = $false
            seed = $Seed
            temperature = $Temperature
            model = $resolvedModel
            runtime_profile = $runtimeDescriptor.runtime_profile
            runtime_profile_file = $runtimeDescriptorPath
            model_sha256 = $runtimeDescriptor.model_sha256
            mmproj_sha256 = $runtimeDescriptor.mmproj_sha256
        } | ConvertTo-Json -Depth 3
        exit 0
    }
    if (-not $Restart) {
        throw "端口 $($endpoint.Port) 上的 OCR 服务配置与本次请求不一致；使用 -Restart 仅重启已验证的同一 llama-server.exe"
    }
    if (-not $listener) {
        throw "OCR 服务健康检查通过但无法定位端口 $($endpoint.Port) 的监听进程"
    }
    $running = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    if (
        $null -eq $running -or
        [System.IO.Path]::GetFullPath([string]$running.ExecutablePath) -ne [System.IO.Path]::GetFullPath($resolvedServer)
    ) {
        throw "端口 $($endpoint.Port) 不是请求的 llama-server.exe，拒绝终止未知服务"
    }
    Stop-Process -Id $listener.OwningProcess -ErrorAction Stop
    $deadline = (Get-Date).AddSeconds(15)
    do {
        Start-Sleep -Milliseconds 250
        $listener = Get-NetTCPConnection -LocalPort $endpoint.Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
    } while ($listener -and (Get-Date) -lt $deadline)
    if ($listener) {
        throw "OCR 服务进程未在 15 秒内停止"
    }
}

if ($listener) {
    throw "端口 $($endpoint.Port) 已被进程 $($listener[0].OwningProcess) 监听，但 /health 未通过；拒绝覆盖未知服务"
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$stdout = Join-Path $LogRoot "llama-server-$timestamp.stdout.log"
$stderr = Join-Path $LogRoot "llama-server-$timestamp.stderr.log"
$arguments = @(
    "--model", (Resolve-Path -LiteralPath $ModelPath),
    "--mmproj", (Resolve-Path -LiteralPath $MmprojPath),
    "--ctx-size", "$ContextSize",
    "--gpu-layers", $GpuLayers,
    "--seed", "$Seed",
    "--temp", "$Temperature",
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
        if (-not (Test-OcrRuntime $endpoint $resolvedModel $Seed $Temperature)) {
            Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
            throw "OCR 服务已响应，但模型、随机种子或温度与请求不一致。日志: $stderr"
        }
        $runtimeDescriptorPath = Write-OcrRuntimeDescriptor `
            -Root $LogRoot `
            -Descriptor $runtimeDescriptor
        [PSCustomObject]@{
            status = "ready"
            url = $endpoint.GetLeftPart([UriPartial]::Authority)
            started = $true
            process_id = $process.Id
            seed = $Seed
            temperature = $Temperature
            model = $resolvedModel
            runtime_profile = $runtimeDescriptor.runtime_profile
            runtime_profile_file = $runtimeDescriptorPath
            model_sha256 = $runtimeDescriptor.model_sha256
            mmproj_sha256 = $runtimeDescriptor.mmproj_sha256
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
