[CmdletBinding()]
param(
    [Parameter()]
    [string]$DockerPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$environmentPath = Join-Path $projectRoot '.env'
$composePath = Join-Path $projectRoot 'compose.yaml'

if (-not (Test-Path -LiteralPath $environmentPath -PathType Leaf)) {
    throw "本地环境文件不存在：$environmentPath。请先复制 .env.compose.example 为 .env 并填写本地配置。"
}
if (-not (Test-Path -LiteralPath $composePath -PathType Leaf)) {
    throw "Compose 文件不存在：$composePath"
}

if ([string]::IsNullOrWhiteSpace($DockerPath)) {
    # 使用真实 docker.exe，避免 Windows App Execution Alias 遮蔽 Docker Desktop CLI。
    $dockerCommand = Get-Command docker.exe -CommandType Application -All -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -and (Test-Path -LiteralPath $_.Source -PathType Leaf) } |
        Select-Object -First 1
    if (-not $dockerCommand) {
        throw '找不到 Docker CLI。请启动 Docker Desktop，或用 -DockerPath 指定 docker.exe 的完整路径。'
    }
    $DockerPath = $dockerCommand.Source
}
if (-not (Test-Path -LiteralPath $DockerPath -PathType Leaf)) {
    throw "Docker CLI 不存在：$DockerPath"
}
$dockerExecutable = (Resolve-Path -LiteralPath $DockerPath).Path

& $dockerExecutable compose version --short *> $null
if ($LASTEXITCODE -ne 0) {
    throw '需要可用的 Docker Compose V2。请确认 Docker Desktop 已启动。'
}

Push-Location $projectRoot
try {
    Write-Host '检查 Compose 配置…'
    & $dockerExecutable compose config --quiet
    if ($LASTEXITCODE -ne 0) {
        throw 'Compose 配置检查失败；请核对 .env 中的必填项。'
    }

    Write-Host '构建并启动 PostgreSQL、API 和管理台…'
    & $dockerExecutable compose up -d --build
    if ($LASTEXITCODE -ne 0) {
        throw 'Compose 启动失败。可运行 docker compose logs --tail 100 postgres api console 查看日志。'
    }

    Write-Host ''
    Write-Host '当前服务状态：'
    & $dockerExecutable compose ps
    if ($LASTEXITCODE -ne 0) {
        throw '读取 Compose 服务状态失败。'
    }

    $apiPort = 8002
    $consolePort = 5175
    foreach ($line in Get-Content -LiteralPath $environmentPath) {
        if ($line -match '^\s*IAM_API_PORT\s*=\s*(\d+)\s*(?:#.*)?$') {
            $apiPort = [int]$Matches[1]
        }
        if ($line -match '^\s*IAM_CONSOLE_PORT\s*=\s*(\d+)\s*(?:#.*)?$') {
            $consolePort = [int]$Matches[1]
        }
    }

    Write-Host "管理台：http://localhost:$consolePort/"
    $readinessUrl = "http://127.0.0.1:$apiPort/api/v1/ready"
    Write-Host "API readiness：http://localhost:$apiPort/api/v1/ready"
    $httpClient = [System.Net.Http.HttpClient]::new()
    # 容器已启动不等于 API 已监听；有限重试连接拒绝与反向代理 502。
    # 数据库故障/迁移待处理是可诊断的 503，应立即显示而不是重复探测。
    $httpClient.Timeout = [TimeSpan]::FromSeconds(2)
    $maxReadinessAttempts = 12
    $readinessReady = $false
    $stopReadinessRetry = $false
    $lastReadinessIssue = 'API readiness 未返回成功响应'
    try {
        for ($attempt = 1; $attempt -le $maxReadinessAttempts; $attempt++) {
            $readinessAttemptsCompleted = $attempt
            $response = $null
            try {
                $response = $httpClient.GetAsync($readinessUrl).GetAwaiter().GetResult()
                if ($response.IsSuccessStatusCode) {
                    Write-Host 'API readiness：HTTP 200，数据库与迁移均已就绪。'
                    $readinessReady = $true
                } else {
                    $httpStatus = [int]$response.StatusCode
                    $detailCode = $null
                    try {
                        $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
                        $payload = ConvertFrom-Json -InputObject $body -ErrorAction Stop
                        $detailProperty = $payload.PSObject.Properties['detail']
                        if ($detailProperty) {
                            if ($detailProperty.Value -is [string]) {
                                $detailCode = $detailProperty.Value
                            } else {
                                $codeProperty = $detailProperty.Value.PSObject.Properties['code']
                                if ($codeProperty) { $detailCode = [string]$codeProperty.Value }
                            }
                        }
                    } catch {
                        # readiness body 仅用于显示稳定错误码；不能解析时只显示 HTTP 状态。
                    }

                    if ($httpStatus -eq 502) {
                        $lastReadinessIssue = 'HTTP 502（API 启动中或暂不可达）'
                    } else {
                        if ($detailCode) {
                            $lastReadinessIssue = "HTTP $httpStatus，错误码 $detailCode"
                        } else {
                            $lastReadinessIssue = "HTTP $httpStatus"
                        }
                        # 例如 database_not_ready/database_migration_pending 均是 API 的明确诊断。
                        $stopReadinessRetry = $true
                    }
                }
            } catch {
                # 连接拒绝/启动期间的短暂网络错误会重试，超时次数有上限。
                $lastReadinessIssue = "暂时无法连接（$($_.Exception.GetType().Name)）"
            } finally {
                if ($response) { $response.Dispose() }
            }

            if ($readinessReady -or $stopReadinessRetry) {
                break
            }
            if ($attempt -lt $maxReadinessAttempts) {
                Start-Sleep -Seconds 1
            }
        }

        if (-not $readinessReady) {
            Write-Warning "API readiness 未就绪：$lastReadinessIssue；已探测 $readinessAttemptsCompleted/$maxReadinessAttempts 次。可稍后重试或查看 API 日志。"
        }
    } finally {
        $httpClient.Dispose()
    }
    Write-Host '此脚本不会执行数据库迁移或创建管理员。若 API 报 database_migration_pending，请查看 docs/部署与运维.md 并按授权流程处理。'
} finally {
    Pop-Location
}
