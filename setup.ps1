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

# Revisar archivo de credenciales de Google Vision
$envFile = Join-Path $ProjectDir ".env"
$gac = ""
if (Test-Path -LiteralPath $envFile) {
    $gac = (Get-Content $envFile | Where-Object { $_ -match '^GOOGLE_APPLICATION_CREDENTIALS=' } | ForEach-Object { ($_ -split '=', 2)[1] }).Trim()
}
if (-not $gac -or -not (Test-Path -LiteralPath $gac)) {
    Write-Warning "No existe el archivo de credenciales de Google Vision: $gac"
    Write-Warning "Crea un service account en Google Cloud (API Vision habilitada) y actualiza GOOGLE_APPLICATION_CREDENTIALS en el .env"
    try {
        New-Item -ItemType File -Path $gac -Force | Out-Null
        Write-Warning "Se creó un placeholder vacío para poder levantar la API. Los PDFs escaneados NO se procesarán hasta colocar las credenciales reales."
    } catch {
        throw "No se pudo crear el placeholder de credenciales. Ajusta GOOGLE_APPLICATION_CREDENTIALS a una ruta válida en el .env"
    }
}

# Reemplazar el ID de la hoja en el workflow de n8n
$wfPath = Join-Path $ProjectDir "n8n-workflow.json"
if (Test-Path -LiteralPath $wfPath) {
    (Get-Content -LiteralPath $wfPath -Raw) -replace 'TU_SHEET_ID', $SheetId | Set-Content -LiteralPath $wfPath -NoNewline -Encoding UTF8
    Write-Host "Workflow actualizado con el ID de la hoja."
}

# Construir y levantar la API
Write-Host "Construyendo la API (la primera vez puede tardar varios minutos)..."
Push-Location $ProjectDir
try {
    docker compose up -d --build
    if ($LASTEXITCODE -ne 0) { throw "docker compose falló" }
} finally {
    Pop-Location
}

# Health check
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

# Levantar n8n con acceso a la carpeta de PDFs
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
