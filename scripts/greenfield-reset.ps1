﻿# Greenfield one-shot reset: wipe volumes -> migrate -> seed -> start services
# WARNING: Deletes all data in iam-postgres-data and iam-oidc-signing-data volumes.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\greenfield-reset.ps1 -IUnderstand [-SkipDemo]
# Also accepts: ...\greenfield-reset.ps1 --i-understand
param(
    [switch]$SkipDemo,
    [switch]$IUnderstand,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Accept bash-style confirmation flag via RemainingArgs
if (-not $IUnderstand) {
    foreach ($arg in @($RemainingArgs)) {
        if ($arg -eq "--i-understand" -or $arg -eq "-i-understand") {
            $IUnderstand = $true
        }
    }
}
if (-not $IUnderstand) {
    Write-Host "[greenfield] refused: pass -IUnderstand or --i-understand (wipes all compose volumes)" -ForegroundColor Red
    Write-Host "[greenfield] example: powershell -ExecutionPolicy Bypass -File scripts\greenfield-reset.ps1 -IUnderstand" -ForegroundColor Yellow
    exit 2
}

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path "$root\.env")) {
    Write-Host "[greenfield] missing root .env (IAM_POSTGRES_PASSWORD / IAM_ADMIN_EMAIL / IAM_ADMIN_PASSWORD)" -ForegroundColor Red
    exit 1
}

Write-Host "[greenfield] 1/4 stop and remove compose named volumes (down -v)" -ForegroundColor Cyan
docker compose down -v

Write-Host "[greenfield] 2/4 apply greenfield migration (0001_greenfield_iam)" -ForegroundColor Cyan
docker compose --profile migrate run --build --rm migrate
if ($LASTEXITCODE -ne 0) { Write-Host "[greenfield] migrate failed" -ForegroundColor Red; exit 1 }

Write-Host "[greenfield] 3/4 seed greenfield (permission catalog + L1 + platform tenant)" -ForegroundColor Cyan
$seedArgs = @("--profile", "seed", "run", "--build", "--rm", "seed-greenfield", "python", "manage.py", "seed-greenfield")
if (-not $SkipDemo) { $seedArgs += "--demo-tenant" }
docker compose @seedArgs
if ($LASTEXITCODE -ne 0) { Write-Host "[greenfield] seed failed" -ForegroundColor Red; exit 1 }

Write-Host "[greenfield] 4/4 start api and console" -ForegroundColor Cyan
docker compose up -d --build api console
if ($LASTEXITCODE -ne 0) { Write-Host "[greenfield] start failed" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "[greenfield] done. Login console with IAM_ADMIN_EMAIL / IAM_ADMIN_PASSWORD from .env" -ForegroundColor Green
Write-Host "[greenfield] ALLOW_BOOTSTRAP_EMAIL_BYPASS defaults to false; platform power is role-bound only" -ForegroundColor Green
Write-Host "[greenfield] without Docker: DROP DATABASE + alembic upgrade head + python manage.py seed-greenfield" -ForegroundColor Green
