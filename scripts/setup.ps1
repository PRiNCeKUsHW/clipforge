# ClipForge one-time setup + start (Windows PowerShell).
# Run from the project folder:   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
# Safe to run again: it never overwrites values you already filled in.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function New-Secret([int]$bytes) {
    $b = New-Object byte[] $bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    # URL-safe base64 (also a valid Fernet key when $bytes = 32)
    return [Convert]::ToBase64String($b).Replace('+', '-').Replace('/', '_')
}

function Set-EnvValue([string]$key, [string]$value) {
    $lines = Get-Content .env -Encoding UTF8
    $lines = $lines | ForEach-Object { if ($_ -match "^$key=") { "$key=$value" } else { $_ } }
    Set-Content .env $lines -Encoding UTF8
}

function Get-EnvValue([string]$key) {
    $line = Get-Content .env -Encoding UTF8 | Where-Object { $_ -match "^$key=" } | Select-Object -First 1
    if ($line) { return $line.Substring($key.Length + 1) } else { return "" }
}

# 1. Docker running?
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker is not running. Start Docker Desktop, wait until it says 'Engine running', then run this again." -ForegroundColor Red
    exit 1
}

# 2. .env with secrets
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Created .env from .env.example"
}
if ((Get-EnvValue "JWT_SECRET") -in @("", "change-me-to-a-long-random-string")) {
    Set-EnvValue "JWT_SECRET" (New-Secret 48)
    Write-Host "Generated JWT_SECRET"
}
if ((Get-EnvValue "TOKEN_ENCRYPTION_KEY") -eq "") {
    Set-EnvValue "TOKEN_ENCRYPTION_KEY" (New-Secret 32)
    Write-Host "Generated TOKEN_ENCRYPTION_KEY"
}
if ((Get-EnvValue "GEMINI_API_KEY") -eq "") {
    Write-Host ""
    Write-Host "Paste your free Gemini API key (get one at https://aistudio.google.com/apikey):" -ForegroundColor Yellow
    $key = (Read-Host).Trim()
    if ($key) { Set-EnvValue "GEMINI_API_KEY" $key } else { Write-Host "Skipped. Add GEMINI_API_KEY to .env later, or clip finding will fail." -ForegroundColor Yellow }
}

# 3. GPU or CPU
$compose = @("compose", "-f", "docker-compose.yml")
$gpu = $false
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi *> $null
    if ($LASTEXITCODE -eq 0) { $gpu = $true; $compose += @("-f", "docker-compose.gpu.yml") }
}
Write-Host ""
Write-Host ("Starting ClipForge (" + ($(if ($gpu) { "NVIDIA GPU" } else { "CPU" })) + "). The first build takes 10-30 minutes...") -ForegroundColor Cyan
& docker @compose up -d --build
if ($LASTEXITCODE -ne 0) { Write-Host "docker compose failed, see the messages above." -ForegroundColor Red; exit 1 }

# 4. Wait for the API
Write-Host "Waiting for the app to come up..."
for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-WebRequest http://localhost:8000/docs -UseBasicParsing -TimeoutSec 3 | Out-Null; break } catch { Start-Sleep 5 }
}
Write-Host ""
Write-Host "ClipForge is running:  http://localhost:3000   (sign up with any email + password)" -ForegroundColor Green
Write-Host ("Next time just run:     docker " + ($compose -join " ") + " up -d")
Start-Process "http://localhost:3000"
