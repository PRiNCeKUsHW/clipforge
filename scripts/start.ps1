# ClipForge daily start (Windows PowerShell). Run setup.ps1 once first.
# Run from anywhere:   powershell -ExecutionPolicy Bypass -File scripts\start.ps1
#   -Cpu        start without the NVIDIA GPU override
#   -NoBrowser  don't open http://localhost:3000 at the end
#
# Starts Docker Desktop if needed, then the app. If Docker Desktop was not shut down cleanly it
# leaves a dead socket (AppData\Local\docker-secrets-engine\engine.sock) that Windows can't open
# or delete, and the next start crashes with "initializing Secrets Engine ... cannot be accessed".
# This script moves that folder aside before launching Docker so a fresh one is created.

param([switch]$Cpu, [switch]$NoBrowser)

# Not "Stop": on Windows PowerShell 5.1 that turns docker's stderr (e.g. "engine not running") into
# a terminating error. Exit codes are checked instead.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Test-Engine {
    docker info *> $null
    return ($LASTEXITCODE -eq 0)
}

function Wait-Engine([int]$seconds) {
    for ($i = 0; $i -lt ($seconds / 5); $i++) {
        if (Test-Engine) { return $true }
        Start-Sleep 5
    }
    return $false
}

# 1. Docker engine
if (-not (Test-Engine)) {
    $desktop = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
    if ($desktop) {
        Write-Host "Docker Desktop is starting, waiting for the engine..."
    } else {
        $secrets = Join-Path $env:LOCALAPPDATA "docker-secrets-engine"
        if (Test-Path (Join-Path $secrets "engine.sock")) {
            $aside = "docker-secrets-engine.stale-" + (Get-Date -Format "yyyyMMdd-HHmmss")
            try { Rename-Item $secrets $aside -ErrorAction Stop }
            catch { Write-Host "Couldn't move $secrets aside: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }
            Write-Host "Moved Docker's leftover socket folder aside ($aside)."
        }
        # Earlier leftovers usually become deletable after a reboot; ignore the ones that aren't.
        Get-ChildItem $env:LOCALAPPDATA -Directory -Filter "docker-secrets-engine.*" -Force -ErrorAction SilentlyContinue |
            ForEach-Object { try { Remove-Item $_.FullName -Recurse -Force -ErrorAction Stop } catch {} }

        $exe = @(
            (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"),
            (Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\Docker Desktop.exe")
        ) | Where-Object { Test-Path $_ } | Select-Object -First 1
        if (-not $exe) {
            Write-Host "Docker Desktop not found. Start it yourself, then run this again." -ForegroundColor Red
            exit 1
        }
        Write-Host "Starting Docker Desktop..."
        Start-Process $exe
    }
    if (-not (Wait-Engine 240)) {
        Write-Host "Docker's engine didn't come up within 4 minutes." -ForegroundColor Red
        Write-Host "If Docker shows 'An unexpected error occurred', click Quit (NOT 'Reset to factory defaults') and run this again."
        exit 1
    }
}
Write-Host "Docker engine is running." -ForegroundColor Green

# 2. GPU or CPU (same check as setup.ps1)
$compose = @("compose", "-f", "docker-compose.yml")
$gpu = $false
if (-not $Cpu -and (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi *> $null
    if ($LASTEXITCODE -eq 0) { $gpu = $true; $compose += @("-f", "docker-compose.gpu.yml") }
}

# 3. Start the app. Right after Docker starts its API can briefly answer 500, so retry.
Write-Host ("Starting ClipForge (" + $(if ($gpu) { "NVIDIA GPU" } else { "CPU" }) + ")...") -ForegroundColor Cyan
$started = $false
for ($i = 0; $i -lt 6; $i++) {
    & docker @compose up -d
    if ($LASTEXITCODE -eq 0) { $started = $true; break }
    Write-Host "Docker isn't ready yet, retrying in 10 s..."
    Start-Sleep 10
}
if (-not $started) { Write-Host "docker compose failed, see the messages above." -ForegroundColor Red; exit 1 }

# 4. Wait for the web app and API
Write-Host "Waiting for the app to come up..."
$up = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        Invoke-WebRequest http://localhost:8000/docs -UseBasicParsing -TimeoutSec 5 | Out-Null
        Invoke-WebRequest http://localhost:3000 -UseBasicParsing -TimeoutSec 30 | Out-Null
        $up = $true; break
    } catch { Start-Sleep 5 }
}
if (-not $up) {
    Write-Host "The app didn't answer within 5 minutes. Check:  docker compose logs backend frontend" -ForegroundColor Red
    exit 1
}
Write-Host ""
Write-Host "ClipForge is running:  http://localhost:3000" -ForegroundColor Green
if (-not $NoBrowser) { Start-Process "http://localhost:3000" }
