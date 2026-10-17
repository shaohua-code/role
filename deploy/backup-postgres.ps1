[CmdletBinding()]
param(
    [Parameter()]
    [string]$ComposeFile = 'compose.yaml',
    [Parameter()]
    [string]$EnvironmentFile = '.env',
    [Parameter()]
    [string]$PostgresService = 'postgres',
    [Parameter()]
    [string]$OutputDirectory,
    [Parameter()]
    [string]$DockerPath,
    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$composePath = if ([System.IO.Path]::IsPathRooted($ComposeFile)) {
    $ComposeFile
} else {
    Join-Path $projectRoot $ComposeFile
}
$environmentPath = if ([System.IO.Path]::IsPathRooted($EnvironmentFile)) {
    $EnvironmentFile
} else {
    Join-Path $projectRoot $EnvironmentFile
}

if (-not (Test-Path -LiteralPath $composePath -PathType Leaf)) {
    throw "Compose 文件不存在：$composePath"
}
if (-not (Test-Path -LiteralPath $environmentPath -PathType Leaf)) {
    throw "环境文件不存在：$environmentPath"
}
if (-not $ValidateOnly -and [string]::IsNullOrWhiteSpace($OutputDirectory)) {
    throw '正式备份必须使用 -OutputDirectory 显式指定受保护的主机目录。'
}

if ([string]::IsNullOrWhiteSpace($DockerPath)) {
    # 直接定位可执行文件，避免 Windows `docker` 应用执行别名覆盖 Docker Desktop。
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
$script:ComposePath = (Resolve-Path -LiteralPath $composePath).Path
$script:EnvironmentPath = (Resolve-Path -LiteralPath $environmentPath).Path

& $script:DockerExecutable compose version --short *> $null
if ($LASTEXITCODE -ne 0) {
    throw '需要可用的 Docker Compose V2 CLI。'
}

function Invoke-IamCompose {
    param(
        [Parameter(Mandatory)]
        [string]$Step,
        [Parameter(Mandatory)]
        [string[]]$CommandArgs
    )

    Write-Host "执行：$Step"
    $composeArgs = @(
        'compose', '-f', $script:ComposePath,
        '--env-file', $script:EnvironmentPath
    ) + $CommandArgs
    & $script:DockerExecutable @composeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "PostgreSQL 备份操作失败：$Step"
    }
}

# 只检查配置解析，不打印包含环境值的 Compose 展开结果。
Invoke-IamCompose -Step 'Compose 配置解析' -CommandArgs @('config', '--quiet')

# 所有认证都在数据库容器内完成，密码只经进程环境变量传给客户端，不进入命令参数或日志。
$connectionCheckScript = @'
set -eu
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in the postgres service}"
: "${POSTGRES_USER:?POSTGRES_USER must be set in the postgres service}"
: "${POSTGRES_DB:?POSTGRES_DB must be set in the postgres service}"
export PGPASSWORD="$POSTGRES_PASSWORD"
pg_isready --quiet --host=127.0.0.1 --port="${PGPORT:-5432}" --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"
result=$(psql --no-password --no-psqlrc --host=127.0.0.1 --port="${PGPORT:-5432}" --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --set=ON_ERROR_STOP=1 --tuples-only --no-align --command='SELECT 1')
[ "$result" = "1" ]
pg_dump --version >/dev/null
pg_restore --version >/dev/null
'@
# Windows PowerShell 5.1 的 here-string 保留 CRLF，且传参时不转义内嵌双引号；
# 因此先统一为 LF，再经 base64 编码，在容器内解码后交给 sh 执行。
$connectionCheckScript = $connectionCheckScript -replace "`r`n", "`n"
$encodedCheckScript = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($connectionCheckScript))
Invoke-IamCompose -Step '数据库连接、凭据和归档工具检查' -CommandArgs @(
    'exec', '-T', $PostgresService, 'sh', '-ec', "echo $encodedCheckScript | base64 -d | sh"
)

if ($ValidateOnly) {
    Write-Host '备份预检通过。未创建归档、未修改数据库。'
    return
}

$resolvedOutputDirectory = if ([System.IO.Path]::IsPathRooted($OutputDirectory)) {
    $OutputDirectory
} else {
    Join-Path $projectRoot $OutputDirectory
}
if (-not (Test-Path -LiteralPath $resolvedOutputDirectory -PathType Container)) {
    New-Item -ItemType Directory -Path $resolvedOutputDirectory -Force | Out-Null
}
$resolvedOutputDirectory = (Resolve-Path -LiteralPath $resolvedOutputDirectory).Path

$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$uniqueSuffix = [Guid]::NewGuid().ToString('N').Substring(0, 8)
$archiveName = "iam-postgres-$stamp-$uniqueSuffix.dump"
$archivePath = Join-Path $resolvedOutputDirectory $archiveName
$remoteArchivePath = "/tmp/$archiveName"
if (Test-Path -LiteralPath $archivePath) {
    throw "备份目标已存在，拒绝覆盖：$archivePath"
}

$backupScript = @'
set -eu
umask 077
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in the postgres service}"
: "${POSTGRES_USER:?POSTGRES_USER must be set in the postgres service}"
: "${POSTGRES_DB:?POSTGRES_DB must be set in the postgres service}"
export PGPASSWORD="$POSTGRES_PASSWORD"
pg_dump --no-password --host=127.0.0.1 --port="${PGPORT:-5432}" --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --format=custom --file="$1"
pg_restore --list "$1" >/dev/null
'@
# 同上：先转 LF，再把 $1 替换为实际归档路径，经 base64 编码后在容器内解码执行。
$backupScript = ($backupScript -replace "`r`n", "`n").Replace('$1', $remoteArchivePath)
$encodedBackupScript = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($backupScript))

$remoteArchiveCreated = $false
try {
    # 先标记，失败时也尝试清掉可能留下的半成品归档。
    $remoteArchiveCreated = $true
    Invoke-IamCompose -Step '生成并检查 PostgreSQL custom archive' -CommandArgs @(
        'exec', '-T', $PostgresService, 'sh', '-ec', "echo $encodedBackupScript | base64 -d | sh"
    )

    Invoke-IamCompose -Step '复制归档到受保护的主机目录' -CommandArgs @(
        'cp', "${PostgresService}:$remoteArchivePath", $archivePath
    )
    if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) {
        throw "Docker Compose 未生成备份文件：$archivePath"
    }
    $archiveItem = Get-Item -LiteralPath $archivePath
    if ($archiveItem.Length -le 0) {
        throw "备份归档为空：$archivePath"
    }

    $checksum = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    $checksumPath = "$archivePath.sha256"
    Set-Content -LiteralPath $checksumPath -Value "$checksum *$archiveName" -Encoding ASCII
    Write-Host "备份已创建：$archivePath"
    Write-Host "SHA-256：$checksum"
    Write-Host '归档已在 PostgreSQL 容器内通过 pg_restore --list 检查；这不等于完成恢复演练。'
}
finally {
    if ($remoteArchiveCreated) {
        try {
            Invoke-IamCompose -Step '清理容器临时归档' -CommandArgs @(
                'exec', '-T', $PostgresService, 'rm', '-f', $remoteArchivePath
            )
        } catch {
            Write-Warning "容器临时归档清理失败，请在 $PostgresService 检查 $remoteArchivePath；错误信息已省略以免输出环境数据。"
        }
    }
}
