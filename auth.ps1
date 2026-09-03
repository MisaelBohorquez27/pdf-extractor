[CmdletBinding()]
param(
    [string]$ProjectDir = ""
)

$ErrorActionPreference = "Stop"
if (-not $ProjectDir) { $ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path }

$secretPath = Join-Path $ProjectDir "client_secret.json"
if (-not (Test-Path -LiteralPath $secretPath)) {
    throw "Falta client_secret.json en $ProjectDir. Copia tu archivo client_secret_*.json descargado de Google Cloud Console."
}

# Verificar redirect URIs
$secretJson = Get-Content -LiteralPath $secretPath -Raw | ConvertFrom-Json
$uris = @()
if ($secretJson.web) { $uris = $secretJson.web.redirect_uris }
elseif ($secretJson.installed) { $uris = $secretJson.installed.redirect_uris }
if (-not ($uris | Where-Object { $_ -match 'localhost|127\.0\.0\.1' })) {
    Write-Warning "Tu cliente OAuth no tiene 'http://localhost:8080' registrado."
    Write-Host "Ve a: https://console.cloud.google.com/apis/credentials" -ForegroundColor Yellow
    Write-Host "  -> tu cliente OAuth 2.0 (Web) -> URIs de redireccionamiento autorizados" -ForegroundColor Yellow
    Write-Host "  -> agrega: http://localhost:8080" -ForegroundColor Yellow
    $cont = Read-Host "Ya lo agregaste? (s/n)"
    if ($cont -notmatch '^s') { exit 1 }
}

# Asegurar imagen de la API
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop no está corriendo." }
Push-Location $ProjectDir
try {
    docker compose build 2>&1 | Select-Object -Last 1
    if ($LASTEXITCODE -ne 0) { throw "docker compose build falló" }
} finally {
    Pop-Location
}

# Generar token (login interactivo, una sola vez)
Write-Host ""
Write-Host "Se abrirá (o copiarás) una URL de Google. Acepta los permisos." -ForegroundColor Cyan
docker run --rm -it `
    -p 8080:8080 `
    -v "${ProjectDir}\client_secret.json:/app/client_secret.json:ro" `
    -v "${ProjectDir}\oauth:/app/oauth" `
    pdf-extractor-pdf-extractor-api `
    python /app/generar_token.py
if ($LASTEXITCODE -ne 0) { throw "Falló la generación del token OAuth2" }

$tokenPath = Join-Path $ProjectDir "oauth\token.json"
if (-not (Test-Path -LiteralPath $tokenPath)) { throw "No se generó oauth/token.json" }
Write-Host "Token guardado. Ya puedes ejecutar: python run.py"
