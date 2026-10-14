[CmdletBinding()]
param(
    [Parameter()]
    [string]$EnvironmentFile = '.env.production.local',
    [Parameter()]
    [string]$DockerPath,
    [switch]$IncludeKeyRotation
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $projectRoot 'compose.production.yaml'
$composeFiles = @('-f', $composeFile)
if ($IncludeKeyRotation) {
    $rotationComposeFile = Join-Path $projectRoot 'compose.production.key-rotation.yaml'
    if (-not (Test-Path -LiteralPath $rotationComposeFile -PathType Leaf)) {
        throw "OIDC 轮换覆盖文件不存在：$rotationComposeFile"
    }
    $composeFiles += @('-f', $rotationComposeFile)
}
$environmentPath = if ([System.IO.Path]::IsPathRooted($EnvironmentFile)) {
    $EnvironmentFile
} else {
    Join-Path $projectRoot $EnvironmentFile
}

if (-not (Test-Path -LiteralPath $environmentPath -PathType Leaf)) {
    throw "生产环境文件不存在：$environmentPath。请先从 .env.production.example 在本机创建被忽略的环境文件。"
}

if ([string]::IsNullOrWhiteSpace($DockerPath)) {
    # Windows App Execution Alias may shadow Docker Desktop's real CLI as `docker`.
    # Resolve a concrete docker.exe file so this preflight never invokes an empty alias.
    $dockerCommand = Get-Command docker.exe -CommandType Application -All -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -and (Test-Path -LiteralPath $_.Source -PathType Leaf) } |
        Select-Object -First 1
    if (-not $dockerCommand) {
        throw '找不到可执行的 Docker CLI。请安装 Docker Compose V2，或使用 -DockerPath 指定 docker.exe 的完整路径。'
    }
    $DockerPath = $dockerCommand.Source
}
if (-not (Test-Path -LiteralPath $DockerPath -PathType Leaf)) {
    throw "Docker CLI 不存在或不可执行：$DockerPath"
}
$script:DockerExecutable = (Resolve-Path -LiteralPath $DockerPath).Path

& $script:DockerExecutable compose version --short *> $null
if ($LASTEXITCODE -ne 0) {
    throw '需要可用的 Docker Compose V2 CLI。'
}

function Invoke-IamComposeCheck {
    param(
        [Parameter(Mandatory)]
        [string]$Step,
        [Parameter(Mandatory)]
        [string[]]$CommandArgs
    )

    Write-Host "校验：$Step"
    $composeArgs = @('compose') + $composeFiles + @('--env-file', $environmentPath) + $CommandArgs
    & $script:DockerExecutable @composeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "生产预检失败：$Step。修复错误后再运行部署流程。"
    }
}

# --quiet 避免把解析后的 Compose 配置（包括注入值）写到终端或日志。
Invoke-IamComposeCheck -Step 'Compose 模板和必填变量' -CommandArgs @('config', '--quiet')

# 校验实际挂载的可选可信代理配置；此命令不会启动 Caddy 服务或申请证书。
Invoke-IamComposeCheck -Step 'Caddyfile 与可信代理 drop-in' -CommandArgs @(
    'run', '--rm', '--no-deps', '--entrypoint', 'caddy', 'caddy',
    'validate', '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile'
)

# 使用 API 实际运行镜像和用户权限校验 Pydantic 生产配置、活动及备用 OIDC RSA key；不执行 entrypoint/migration。
Invoke-IamComposeCheck -Step 'API 生产配置与 OIDC 签名私钥' -CommandArgs @(
    'run', '--rm', '--no-deps', '--entrypoint', 'python', 'api', '-c',
    'from app.core.config import get_settings; from app.core.oidc_keys import signing_private_key, previous_signing_private_key; get_settings(); signing_private_key(); previous_signing_private_key()'
)

# 要先按运维手册构建 production console 镜像；nginx -t 只解析配置，不启动长期服务。
Invoke-IamComposeCheck -Step '生产 Nginx 配置' -CommandArgs @(
    'run', '--rm', '--no-deps', 'console', 'nginx', '-t'
)

Write-Host '生产预检通过。未启动长期服务，未连接数据库，也未运行迁移。'
