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
    throw "本地环境文件不存在：$environmentPath。请先复制 .env.compose.example 为 .env。"
}
if (-not (Test-Path -LiteralPath $composePath -PathType Leaf)) {
    throw "Compose 文件不存在：$composePath"
}

if ([string]::IsNullOrWhiteSpace($DockerPath)) {
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
    Write-Host '1/2 运行后端完整 PostgreSQL 套件（仅创建并删除 iam_test_<随机值> 临时库）…'
    # 显式禁用启动脚本中的 OIDC key 初始化；此一次性容器只运行测试，不迁移 iam 主库。
    $composeArgs = @(
        'compose', 'run', '--build', '--rm', '-e', 'IAM_ENSURE_OIDC_KEY=false',
        'api', 'python', '-B', '/app/tests/run_isolated_postgres_suite.py'
    )
    & $dockerExecutable @composeArgs
    if ($LASTEXITCODE -ne 0) {
        throw '后端隔离 PostgreSQL 套件失败。测试 runner 会清理它创建的随机测试库；请依据输出定位失败。'
    }

    Write-Host '2/2 构建锁定依赖的前端镜像（Dockerfile 内执行 Vue/TypeScript 检查和 Vite 生产构建）…'
    $frontendArgs = @('compose', 'build', 'console')
    $frontendBuildOutput = & $dockerExecutable @frontendArgs 2>&1
    $frontendBuildExitCode = $LASTEXITCODE
    foreach ($outputLine in $frontendBuildOutput) {
        Write-Host $outputLine
    }

    if ($frontendBuildExitCode -ne 0) {
        $frontendBuildText = $frontendBuildOutput -join "`n"
        $dockerHubRegistryHost = ($frontendBuildText -match 'registry-1\.docker\.io') -or
            ($frontendBuildText -match 'auth\.docker\.io')
        $nodeRegistryEof = $dockerHubRegistryHost -and
            ($frontendBuildText -match 'node:22-alpine') -and
            ($frontendBuildText -match 'EOF')
        if (-not $nodeRegistryEof) {
            throw '前端生产镜像构建失败，且错误不属于可安全离线回退的 Node 基础镜像拉取 EOF。'
        }

        Write-Warning 'Docker Hub 暂时无法提供 node:22-alpine；检查本地 console 镜像的依赖锁文件是否与工作区完全一致，再尝试离线验证。'
        $fingerprintFiles = @('package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml')
        $fingerprintCommand = 'cd /app && sha256sum ' + ($fingerprintFiles -join ' ')
        $fingerprintArgs = @('compose', 'run', '--rm', '--no-deps', 'console', 'sh', '-lc', $fingerprintCommand)
        $fingerprintOutput = & $dockerExecutable @fingerprintArgs 2>&1
        if ($LASTEXITCODE -ne 0) {
            foreach ($outputLine in $fingerprintOutput) {
                Write-Host $outputLine
            }
            throw '无法读取本地 console 镜像；请先启动 Docker Desktop 并确保前端镜像已存在，或恢复 Docker Hub 连接。'
        }

        $imageFingerprint = @{}
        foreach ($hashLine in $fingerprintOutput) {
            $hashParts = ([string]$hashLine).Trim() -split '\s+', 2
            if ($hashParts.Count -lt 2) {
                continue
            }
            $imagePath = $hashParts[1].TrimStart('*').TrimStart('/') -replace '^app/', ''
            $imageFingerprint[$imagePath] = $hashParts[0].ToUpperInvariant()
        }
        foreach ($relativePath in $fingerprintFiles) {
            $workspacePath = Join-Path $projectRoot (Join-Path 'frontend' $relativePath)
            if (-not (Test-Path -LiteralPath $workspacePath -PathType Leaf)) {
                throw "前端构建输入不存在：$workspacePath"
            }
            $workspaceHash = (Get-FileHash -LiteralPath $workspacePath -Algorithm SHA256).Hash.ToUpperInvariant()
            if (-not $imageFingerprint.ContainsKey($relativePath) -or $imageFingerprint[$relativePath] -ne $workspaceHash) {
                throw "本地 console 镜像构建输入与工作区不一致（$relativePath）；不能使用离线回退。请恢复 Docker Hub 连接后重试。"
            }
        }

        $offlineBuildCommand = 'cd /app && pnpm exec vue-tsc -b && pnpm exec vite build --outDir /tmp/iam-console-build --emptyOutDir'
        $offlineBuildArgs = @('compose', 'run', '--rm', '--no-deps', 'console', 'sh', '-lc', $offlineBuildCommand)
        & $dockerExecutable @offlineBuildArgs
        if ($LASTEXITCODE -ne 0) {
            throw '本地 console 镜像离线 Vue/TypeScript 检查或 Vite 生产构建失败。'
        }
        Write-Host '离线回退已通过：镜像依赖锁与工作区一致，Vue/TypeScript 检查和 Vite 生产构建成功。'
    }

    Write-Host ''
    Write-Host '本地代码验证完成。该结果不代表 SMTP、浏览器真实注册、生产镜像或 TLS 部署已经验收。'
} finally {
    Pop-Location
}
