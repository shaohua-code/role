[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$BackupFile,
    [Parameter()]
    [string]$ComposeFile = 'compose.yaml',
    [Parameter()]
    [string]$EnvironmentFile = '.env',
    [Parameter()]
    [string]$PostgresService = 'postgres',
    [Parameter()]
    [string]$DockerPath,
    [switch]$SkipChecksum,
    [switch]$KeepScratchDatabase
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
$backupPath = if ([System.IO.Path]::IsPathRooted($BackupFile)) {
    $BackupFile
} else {
    Join-Path $projectRoot $BackupFile
}

if (-not (Test-Path -LiteralPath $composePath -PathType Leaf)) {
    throw "Compose 文件不存在：$composePath"
}
if (-not (Test-Path -LiteralPath $environmentPath -PathType Leaf)) {
    throw "环境文件不存在：$environmentPath"
}
if (-not (Test-Path -LiteralPath $backupPath -PathType Leaf)) {
    throw "PostgreSQL 备份文件不存在：$backupPath"
}
$backupPath = (Resolve-Path -LiteralPath $backupPath).Path
$backupItem = Get-Item -LiteralPath $backupPath
if ($backupItem.Length -le 0) {
    throw '备份文件为空，拒绝恢复演练。'
}

$checksumPath = "$backupPath.sha256"
if (-not $SkipChecksum) {
    if (-not (Test-Path -LiteralPath $checksumPath -PathType Leaf)) {
        throw "缺少 SHA-256 校验文件：$checksumPath。若这是可信的旧备份，可显式传入 -SkipChecksum。"
    }
    $checksumLine = (Get-Content -LiteralPath $checksumPath -TotalCount 1).Trim()
    if ($checksumLine -notmatch '^([0-9a-fA-F]{64})\s+\*?(.+)$') {
        throw 'SHA-256 校验文件格式无效，拒绝恢复演练。'
    }
    $expectedHash = $Matches[1].ToLowerInvariant()
    $expectedName = $Matches[2].Trim()
    if ($expectedName -ne [System.IO.Path]::GetFileName($backupPath)) {
        throw 'SHA-256 校验文件中的归档名称与所选备份不一致。'
    }
    $actualHash = (Get-FileHash -LiteralPath $backupPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) {
        throw '备份 SHA-256 校验失败，拒绝恢复演练。'
    }
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
        throw "PostgreSQL 恢复演练失败：$Step。若临时库已创建，将保留它以便检查。"
    }
}

# 静默解析配置，避免把 Compose 插值后的凭据打印到控制台。
Invoke-IamCompose -Step 'Compose 配置解析' -CommandArgs @('config', '--quiet')

$runId = [Guid]::NewGuid().ToString('N')
$scratchDatabase = "iam_restore_check_$runId"
$remoteArchivePath = "/tmp/$scratchDatabase.dump"
$databaseCreated = $false
$restoreSucceeded = $false
$remoteArchiveCopied = $false

$restoreScript = @'
set -eu
umask 077
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in the postgres service}"
: "${POSTGRES_USER:?POSTGRES_USER must be set in the postgres service}"
: "${POSTGRES_DB:?POSTGRES_DB must be set in the postgres service}"
export PGPASSWORD="$POSTGRES_PASSWORD"
pg_isready --quiet --host=127.0.0.1 --port="${PGPORT:-5432}" --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"
pg_restore --list "$1" >/dev/null
createdb --no-password --username="$POSTGRES_USER" --maintenance-db="$POSTGRES_DB" "$2"
'@
# Windows PowerShell 5.1 的 here-string 保留 CRLF，且传参时不转义内嵌双引号；先转 LF 供后续 base64 编码。
$restoreScript = $restoreScript -replace "`r`n", "`n"

$verifyScript = @'
set -eu
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in the postgres service}"
: "${POSTGRES_USER:?POSTGRES_USER must be set in the postgres service}"
export PGPASSWORD="$POSTGRES_PASSWORD"
revision=$(psql --no-password --no-psqlrc --host=127.0.0.1 --port="${PGPORT:-5432}" --username="$POSTGRES_USER" --dbname="$1" --set=ON_ERROR_STOP=1 --tuples-only --no-align --command='SELECT version_num FROM alembic_version ORDER BY version_num')
[ -n "$revision" ]
schema_ok=$(psql --no-password --no-psqlrc --host=127.0.0.1 --port="${PGPORT:-5432}" --username="$POSTGRES_USER" --dbname="$1" --set=ON_ERROR_STOP=1 --tuples-only --no-align --command="SELECT to_regclass('public.users') IS NOT NULL AND to_regclass('public.tenants') IS NOT NULL AND to_regclass('public.applications') IS NOT NULL")
[ "$schema_ok" = "t" ]
printf '%s\n' "$revision"
'@
# 同上：先转 LF 供后续 base64 编码。
$verifyScript = $verifyScript -replace "`r`n", "`n"

$restoreIntoScratchScript = @'
set -eu
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in the postgres service}"
: "${POSTGRES_USER:?POSTGRES_USER must be set in the postgres service}"
export PGPASSWORD="$POSTGRES_PASSWORD"
pg_restore --no-password --host=127.0.0.1 --port="${PGPORT:-5432}" --username="$POSTGRES_USER" --dbname="$2" --no-owner --no-privileges "$1"
'@
# 同上：先转 LF 供后续 base64 编码。
$restoreIntoScratchScript = $restoreIntoScratchScript -replace "`r`n", "`n"

$dropScratchScript = @'
set -eu
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in the postgres service}"
: "${POSTGRES_USER:?POSTGRES_USER must be set in the postgres service}"
export PGPASSWORD="$POSTGRES_PASSWORD"
dropdb --no-password --if-exists --username="$POSTGRES_USER" "$1"
'@
# 同上：先转 LF 供后续 base64 编码。
$dropScratchScript = $dropScratchScript -replace "`r`n", "`n"

try {
    # 即使 docker compose cp 中途失败，也尝试移除这个随机命名的临时文件。
    $remoteArchiveCopied = $true
    Invoke-IamCompose -Step '将指定归档复制到 PostgreSQL 容器临时目录' -CommandArgs @(
        'cp', $backupPath, "${PostgresService}:$remoteArchivePath"
    )

    Invoke-IamCompose -Step '检查归档并创建随机隔离数据库' -CommandArgs @(
        'exec', '-T', $PostgresService, 'sh', '-ec',
        "echo $([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($restoreScript.Replace('$1', $remoteArchivePath).Replace('$2', $scratchDatabase)))) | base64 -d | sh"
    )
    $databaseCreated = $true

    Invoke-IamCompose -Step '恢复备份到隔离数据库' -CommandArgs @(
        'exec', '-T', $PostgresService, 'sh', '-ec',
        "echo $([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($restoreIntoScratchScript.Replace('$1', $remoteArchivePath).Replace('$2', $scratchDatabase)))) | base64 -d | sh"
    )

    $revisionOutput = Invoke-IamCompose -Step '检查恢复后的 migration revision 与关键表' -CommandArgs @(
        'exec', '-T', $PostgresService, 'sh', '-ec',
        "echo $([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($verifyScript.Replace('$1', $scratchDatabase)))) | base64 -d | sh"
    )
    $revisionLines = @($revisionOutput | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($revisionLines.Count -eq 0) {
        throw '恢复后的数据库没有报告 Alembic revision。隔离数据库将保留以便检查。'
    }
    $restoredRevision = ($revisionLines | Select-Object -Last 1).Trim()
    $restoreSucceeded = $true
    Write-Host "恢复验证通过；Alembic revision：$restoredRevision"
    if ($KeepScratchDatabase) {
        Write-Host "按 -KeepScratchDatabase 保留隔离数据库：$scratchDatabase"
    } else {
        Invoke-IamCompose -Step '删除本脚本创建的隔离恢复数据库' -CommandArgs @(
            'exec', '-T', $PostgresService, 'sh', '-ec',
            "echo $([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($dropScratchScript.Replace('$1', $scratchDatabase)))) | base64 -d | sh"
        )
        $databaseCreated = $false
        Write-Host '隔离恢复数据库已删除；原业务数据库未被修改。'
    }
} finally {
    if ($remoteArchiveCopied) {
        try {
            Invoke-IamCompose -Step '清理容器临时备份文件' -CommandArgs @(
                'exec', '-T', $PostgresService, 'rm', '-f', $remoteArchivePath
            )
        } catch {
            Write-Warning "容器临时归档清理失败，请检查 $PostgresService 内的 $remoteArchivePath。"
        }
    }
    if ($databaseCreated -and -not $restoreSucceeded) {
        Write-Warning "恢复未通过；临时数据库 $scratchDatabase 已保留供诊断。原业务数据库未被修改。"
    }
}
