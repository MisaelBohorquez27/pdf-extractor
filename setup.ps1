[CmdletBinding()]
param(
    [string]$DriveFolder = "",
    [string]$SheetId = "",
    [string]$ProjectDir = ""
)

$ErrorActionPreference = "Stop"
if (-not $ProjectDir) { $ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
Write-Host "Directorio del proyecto: $ProjectDir"

if (-not $DriveFolder) { $DriveFolder = Read-Host "Ruta local de 'Material para ventas\Insertos' (carpeta sincronizada con Google Drive Desktop)" }
if (-not $SheetId) { $SheetId = Read-Host "ID del Google Sheet 'base enriquecida' (código largo en la URL)" }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop no está instalado. Instálalo desde https://www.docker.com/products/docker-desktop/"
}
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop no está corriendo. Ábrelo y reintenta." }

if (-not (Test-Path -LiteralPath $DriveFolder)) { throw "No existe la carpeta de PDFs: $DriveFolder" }

# 1. Preparar credenciales OAuth2 (client_secret.json)
$secretFile = Get-ChildItem -LiteralPath $ProjectDir -Filter "client_secret*.json" -File | Select-Object -First 1
$secretPath = Join-Path $ProjectDir "client_secret.json"
if (-not $secretFile) {
    throw "No se encontró el archivo client_secret_*.json (descargado de Google Cloud Console). Cópialo a $ProjectDir"
}
if ($secretFile.Name -ne "client_secret.json") {
    Copy-Item -LiteralPath $secretFile.FullName -Destination $secretPath -Force
    Write-Host "Credenciales copiadas a client_secret.json"
}

# 2. Verificar redirect_uris
$secretJson = Get-Content -LiteralPath $secretPath -Raw | ConvertFrom-Json
$uris = @()
if ($secretJson.web) { $uris = $secretJson.web.redirect_uris }
elseif ($secretJson.installed) { $uris = $secretJson.installed.redirect_uris }
if (-not ($uris | Where-Object { $_ -match 'localhost|127\.0\.0\.1' })) {
    Write-Warning "Tu cliente OAuth NO tiene 'http://localhost:8080' registrado."
    Write-Host "Antes de continuar, ve a: https://console.cloud.google.com/apis/credentials" -ForegroundColor Yellow
    Write-Host "  -> tu cliente OAuth 2.0 (Web) -> URIs de redireccionamiento autorizados" -ForegroundColor Yellow
    Write-Host "  -> agrega: http://localhost:8080" -ForegroundColor Yellow
    $cont = Read-Host "¿Ya lo agregaste? (s/n)"
    if ($cont -notmatch '^s') { throw "Agrega el redirect URI y vuelve a ejecutar setup.ps1" }
}

# 3. Reemplazar el ID de la hoja en el workflow de n8n
$wfPath = Join-Path $ProjectDir "n8n-workflow.json"
if (Test-Path -LiteralPath $wfPath) {
    (Get-Content -LiteralPath $wfPath -Raw) -replace 'TU_SHEET_ID', $SheetId | Set-Content -LiteralPath $wfPath -NoNewline -Encoding UTF8
    Write-Host "Workflow actualizado con el ID de la hoja."
}

# 4. Construir y levantar la API
Write-Host "Construyendo la API (la primera vez puede tardar varios minutos)..."
Push-Location $ProjectDir
try {
    docker compose up -d --build
    if ($LASTEXITCODE -ne 0) { throw "docker compose falló" }
} finally {
    Pop-Location
}

# 5. Health check
Write-Host "Esperando a que la API esté lista..."
$ok = $false
foreach ($i in 1..12) {
    try {
        $r = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get -TimeoutSec 3
        if ($r.status -eq "ok") { $ok = $true; break }
    } catch {
        Start-Sleep -Seconds 5
    }
}
if (-not $ok) { throw "La API no respondió en http://localhost:8000/health" }
Write-Host "API lista en http://localhost:8000"

# 6. Generar token OAuth2 (solo si no existe)
$tokenPath = Join-Path $ProjectDir "oauth\token.json"
if (-not (Test-Path -LiteralPath $tokenPath)) {
    Write-Host ""
    Write-Host "================ AUTENTICACIÓN OAuth2 (una sola vez) ================" -ForegroundColor Cyan
    Write-Host "Se abrirá (o copiarás) una URL de Google. Acepta los permisos." -ForegroundColor Cyan
    Write-Host "Si el navegador no se abre solo, copia la URL que aparezca abajo." -ForegroundColor Cyan
    Write-Host "=====================================================================" -ForegroundColor Cyan
    docker run --rm -it `
        -p 8080:8080 `
        -v "${ProjectDir}\client_secret.json:/app/client_secret.json:ro" `
        -v "${ProjectDir}\oauth:/app/oauth" `
        pdf-extractor-pdf-extractor-api `
        python /app/generar_token.py
    if ($LASTEXITCODE -ne 0) { throw "Falló la generación del token OAuth2" }
    if (-not (Test-Path -LiteralPath $tokenPath)) { throw "No se generó oauth/token.json" }
    Write-Host "Token OAuth2 generado. Reiniciando la API para que lo cargue..."
    docker restart pdf-extractor-api | Out-Null
} else {
    Write-Host "Token OAuth2 ya existente, se omite la autenticación."
}

# 7. Levantar n8n con acceso a la carpeta de PDFs
docker rm -f n8n 2>$null
docker run -d --name n8n `
    -p 5678:5678 `
    -v "${env:USERPROFILE}\.n8n:/home/node/.n8n" `
    -v "${DriveFolder}:/pdfs:rw" `
    -e N8N_SECURE_COOKIE=false `
    -e WEBHOOK_URL=http://localhost:5678 `
    n8nio/n8n
if ($LASTEXITCODE -ne 0) { throw "No se pudo levantar n8n" }

Write-Host ""
Write-Host "================ LISTO ================"
Write-Host "1. API:  http://localhost:8000/docs"
Write-Host "2. n8n:  http://localhost:5678"
Write-Host "3. En n8n: Settings > Credentials > Google Sheets (OAuth2) con tu cuenta de Google"
Write-Host "4. Importa el workflow: Workflows > ... > Import from File > n8n-workflow.json"
Write-Host "5. Abre el nodo 'Append a Base Enriquecida' y verifica documento y hoja"
Write-Host "6. Ejecuta el workflow. El progreso se guarda y puedes reanudar donde quedó."
Write-Host ""
Write-Host "Prueba rápida de la API:"
Write-Host '  Invoke-RestMethod -Uri http://localhost:8000/extract-mock -Method Post -Form @{ file = Get-Item "un_pdf.pdf"; categoria = "Afias"; filename = "un_pdf.pdf" }'
