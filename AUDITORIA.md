# Auditoría del Proyecto — Extractor de Insertos PDF

**Fecha de auditoría:** 02/09/2026 (actualizada a versión 4.0 — procesamiento local sin n8n)
**Ubicación:** `D:\Trabajo\Meditec\pdf-extractor`
**Estado general:** 🟢 Pipeline completo validado de punta a punta — pendiente token OAuth2 para PDFs escaneados

---

## 1. Resumen ejecutivo

| Componente | Estado | Detalle |
|---|---|---|
| API FastAPI (código) | ✅ Completo | 5 módulos, 3 endpoints |
| Imagen Docker | ✅ Construida y probada | `pdf-extractor-pdf-extractor-api:latest` |
| Endpoints API | ✅ Probados | `/health`, `/extract`, `/extract-mock` OK |
| OCR híbrido (texto nativo + Vision) | ✅ Probado | PDF con texto: extrae sin Google; PDF escaneado: pide token |
| Autenticación OAuth2 (v3.0) | ✅ Implementada | Cliente tipo "web" + token persistente con auto-refresh |
| Sin dependencia OpenAI | ✅ Confirmado | Llamada REST directa a DeepSeek con `httpx` |
| Procesador local (v4.0, sin n8n) | ✅ Probado | `process_all_pdfs.py` + `run.py` + `verify_setup.py` |
| Prueba real de punta a punta | ✅ Exitosa | 5 PDFs Afias extraídos y guardados en `resultados.xlsx` |
| Script de despliegue | ✅ Listo | `setup.ps1` (todo) y `auth.ps1` (solo token OAuth2) |
| Token OAuth2 generado | ❌ Pendiente | Falta ejecutar `auth.ps1` (login interactivo, 1 vez) |
| Redirect URI en consola Google | ❌ Pendiente | Falta registrar `http://localhost:8080` |
| Clave DeepSeek | ✅ Real | Verificada con llamada exitosa a la API |
| PDFs | ✅ Localizados | 923 PDFs en 15 subcarpetas de `Datos para la IA\Insertos` |

---

## 2. Inventario de archivos

```
pdf-extractor/
├── .env                    (114 B)  Variables de entorno (falta clave DeepSeek real)
├── docker-compose.yml      (495 B)  Orquestación del contenedor API (monta client_secret + oauth)
├── Dockerfile              (450 B)  Imagen Python 3.10 + poppler-utils + generar_token.py
├── n8n-workflow.json     (7,516 B)  Workflow n8n importable (7 nodos)
├── requirements.txt        (243 B)  12 dependencias Python (incluye google-auth-oauthlib)
├── setup.ps1             (6,050 B)  Despliegue automatizado (build + token OAuth2 + n8n)
├── generar_token.py      (4,800 B)  Login OAuth2 interactivo (se ejecuta UNA vez)
├── client_secret.json                Credenciales OAuth2 tipo "web" (del Google Cloud Console)
├── oauth/                            Contiene token.json tras la autenticación (gitignored)
├── app/
│   ├── __init__.py           (0 B)
│   ├── main.py           (3,400 B)  Endpoints /health, /extract, /extract-mock
│   ├── models.py         (1,863 B)  33 campos de ExtractResponse
│   ├── ocr.py            (2,600 B)  OCR híbrido (texto nativo + Vision con OAuth2)
│   ├── oauth2_client.py  (3,300 B)  Carga/refresca token OAuth2 para Vision
│   └── extractor.py      (5,746 B)  Extracción con DeepSeek (httpx directo)
├── logs/                          Logs rotativos del contenedor
├── test_pdfs/                     Vacía — para PDFs de prueba
└── .vscode/settings.json          Configuración del editor
```

---

## 3. Arquitectura implementada

```
Google Drive Desktop (sync local)
        │
        ▼
n8n (Docker) ── lista PDFs recursivamente por marca
        │        omite carpetas Procesados/ y Errores/
        ▼
POST http://host.docker.internal:8000/extract   (multipart: file, categoria, filename)
        │
        ▼
API FastAPI (Docker)
  ├─ 1. OCR híbrido (app/ocr.py):
  │     · Si el PDF tiene capa de texto → pypdf (GRATIS, sin Google, sin token)
  │     · Si es escaneado → pdf2image + Google Vision con OAuth2 (app/oauth2_client.py:
  │       token generado 1 vez con generar_token.py, refresco automático al expirar)
  ├─ 2. DeepSeek (app/extractor.py):
  │     · POST directo a https://api.deepseek.com/chat/completions
  │     · response_format json_object + 3 reintentos con backoff
  │     · Normaliza las 33 claves con valores N/A por defecto
  └─ 3. Validación: si faltan Producto/Fabricante/Analito → "Requiere Revisión"
        │
        ▼
n8n ── mapea JSON a fila (33 encabezados) → Google Sheets "Base"
        └─ guarda progreso en ~/.n8n/estado/procesados.json
        └─ mueve PDF a Procesados/<marca>/ o Errores/<marca>/ (DENTRO del Drive)
```

**Punto clave:** los PDFs se mueven a `Procesados/` y `Errores/` dentro de la misma
carpeta sincronizada del Drive, por lo que **nada se borra de la nube**. El checkpoint
permite reanudar la ejecución desde donde quedó sin duplicar filas.

---

## 4. Validaciones realizadas (con evidencia)

| # | Prueba | Resultado |
|---|---|---|
| 1 | Build Docker de la imagen | ✅ OK (instaló poppler + 12 paquetes Python) |
| 2 | `GET /health` | ✅ `{"status": "ok"}` |
| 3 | `POST /extract-mock` | ✅ Devuelve fila de ejemplo con categoria y filename |
| 4 | `POST /extract` con PDF de texto nativo | ✅ OCR por `texto_nativo` sin Google ni token; llegó a DeepSeek (401 por key placeholder, esperado) |
| 5 | `POST /extract` con PDF sin texto (escaneado) | ✅ Error claro: "No hay token OAuth2 válido. Ejecuta setup.ps1..." |
| 6 | `generar_token.py` carga el client_secret web | ✅ Config OK, client_id `57557273767-...` |
| 7 | `Flow.from_client_config` con cliente web | ✅ Genera auth_uri correctamente |
| 8 | JSON del workflow n8n | ✅ Sintaxis válida, 7 nodos, conexiones consistentes |
| 9 | Imagen sin paquete `openai` | ✅ Solo `httpx` (DeepSeek por REST directo) |

### Incidencias encontradas y corregidas durante el desarrollo

1. **`openai==1.6.1` incompatible con `httpx 0.28`** (error `unexpected keyword argument 'proxies'`).
   → Solución final: se eliminó la librería `openai` por completo y se llama a la API
   REST de DeepSeek con `httpx==0.27.2` (0 líneas de OpenAI en todo el proyecto).
2. **Nodo `readBinaryFiles` de n8n no existe** → reemplazado por nodo Code que lista
   recursivamente los PDFs y omite carpetas ya procesadas.
3. **Nodo `moveBinaryFile` de n8n no existe** → reemplazado por nodo Code con
   `fs.renameSync` (mueve a `Procesados/` o `Errores/`).
4. **Nodo "Esperar 2s" omitido** → innecesario: cada PDF tarda segundos en la API,
   el rate limiting ya es implícito.

---

## 5. Estado de credenciales (PENDIENTE — acción tuya)

### 5.1 Google Vision — OAuth2 con cliente tipo "web" (v3.0)

La empresa bloqueó la creación de service account keys, así que el proyecto usa
**OAuth2 con un cliente de aplicación web** (`client_secret.json`, ya copiado al
proyecto desde el archivo descargado del Google Cloud Console).

**Autenticación:** se ejecuta UNA sola vez. `setup.ps1` levanta un contenedor
temporal con `generar_token.py` que:
1. Muestra una URL de Google (o la abre en el navegador)
2. Tú aceptas los permisos de Vision
3. El token se guarda en `oauth/token.json` y la API lo refresca solo cuando expira

**Requisito previo (bloqueante):** tu cliente OAuth tiene `redirect_uris` vacío.
Debes registrar en https://console.cloud.google.com/apis/credentials → tu cliente
OAuth 2.0 (Web) → "URIs de redireccionamiento autorizados":
```
http://localhost:8080
```
Sin esto, Google rechazará el login con `redirect_uri_mismatch` (setup.ps1 lo
verifica y te lo recuerda).

**Otros requisitos de la consola de Google:**
- Pantalla de consentimiento OAuth configurada con el scope `cloud-vision`
- Si la app está en modo "Pruebas", agrega tu cuenta como usuario de prueba.
  ⚠️ En modo pruebas los refresh tokens caducan a los 7 días; publica la app
  (o ponla en Producción) para evitar re-autenticar cada semana.

### 5.2 DeepSeek (`DEEPSEEK_API_KEY`) — ⚠️ placeholder confirmado

El `.env` contiene literalmente `sk-tu_api_key_aqui`. Reemplázalo por tu clave
real de https://platform.deepseek.com antes de procesar PDFs de verdad.

---

## 6. Estado de datos (PENDIENTE)

- **PDFs:** ninguno en el proyecto. El flujo lee de la carpeta local sincronizada
  con Google Drive Desktop (`...\Material para ventas\Insertos\` con las 10 marcas).
- **Google Sheet:** falta el ID de "base enriquecida". `setup.ps1` lo pide y lo
  inyecta en el workflow reemplazando `TU_SHEET_ID`.
- **Encabezados de la hoja:** la fila 1 de la pestaña "Base" debe tener estos nombres
  exactos para que el auto-mapeo funcione:

  `Código, Producto, Fabricante, Carpeta, Nombre Archivo, Analito/Parámetro,
  Tecnología, Muestra, Volumen Muestra, Rango de Medición, Valor Referencia,
  Tiempo Resultado, Precisión Intra, Precisión Inter, Correlación, Interferencias,
  Especificidad, Estabilidad, Almacenamiento, Caducidad, Calibradores, Controles,
  Instrumento Compatible, Formato, Número de Lote, Fecha Caducidad, Registro
  Sanitario, País Origen, PDF Asociado, URL PDF, Estado Documento, Observaciones,
  Fecha Extracción`

---

## 7. Estado de Docker

| Elemento | Estado |
|---|---|
| Docker Desktop | ✅ Instalado y corriendo (v29.1.2, Compose v2.40.3) |
| Imagen `pdf-extractor-pdf-extractor-api:latest` | ✅ Construida (417 MB) |
| Contenedor `pdf-extractor-api` | Detenido (se baja tras cada validación) |
| Contenedor `n8nProduction` | ⚠️ **Contenedor viejo**: exit 137 (OOM) hace 6 meses, monta `D:\dev\n8n_data` |

> **Observación:** hay un n8n antiguo con datos en `D:\dev\n8n_data`. `setup.ps1`
> crea un contenedor nuevo (`n8n`) con volumen fresco en `%USERPROFILE%\.n8n`.
> Si querías conservar credenciales/workflows del n8n viejo, avísame y ajusto el
> script para montar `D:\dev\n8n_data` en su lugar.

---

## 8. Checklist de arranque (v4.0 — procesamiento local sin n8n)

1. ☐ Registrar `http://localhost:8080` como redirect URI en Google Cloud Console
2. ☐ Configurar pantalla de consentimiento OAuth (scope cloud-vision) y publicar la app
3. ☐ Ejecutar `.\auth.ps1` → login de Google una vez → genera `oauth/token.json`
4. ☐ Ejecutar `python verify_setup.py` → debe dar TODO LISTO
5. ☐ Ejecutar `python run.py` → levanta la API y procesa los 923 PDFs
6. ☐ Revisar `resultados.xlsx` y `errores.log`
7. ☐ Re-ejecutar `python run.py` si se interrumpió (reanuda desde `progress.json`)

### Comandos v4.0

```powershell
python verify_setup.py        # diagnostica qué falta
.\auth.ps1                    # token OAuth2 de Google (una sola vez)
python run.py                 # levanta API + procesa todo
python process_all_pdfs.py    # solo procesar (API ya corriendo)
```

**Flujo v4.0 (sin n8n):**
```
Insertos/ (923 PDFs) → process_all_pdfs.py → API local (/extract)
  → OCR híbrido (texto nativo gratis / Vision OAuth2 para escaneados)
  → DeepSeek (JSON 33 campos)
  → resultados.xlsx (merge incremental, sin duplicados) + errores.log + progress.json
```

> El workflow `n8n-workflow.json` queda como opción alternativa, ya no es necesario.

### Comandos útiles

```powershell
# Despliegue completo
.\setup.ps1

# Probar la API sin gastar dinero
Invoke-RestMethod -Uri http://localhost:8000/extract-mock -Method Post `
  -Form @{ file = Get-Item "prueba.pdf"; categoria = "Afias"; filename = "prueba.pdf" }

# Logs de la API
docker logs -f pdf-extractor-api

# Reanudar una ejecución interrumpida: basta con volver a ejecutar el workflow
# (los PDFs en Procesados/Errores y el archivo procesados.json evitan duplicados)
```

---

## 9. Costos estimados

| Servicio | Estimación |
|---|---|
| DeepSeek (900 PDFs × ~5K tokens) | ~$0.60 USD |
| Google Vision (solo PDFs escaneados, $1.50/1,000 págs) | $0 – $6.75 según % de escaneados |
| **Total** | **≈ $1 – $7 USD** |

El OCR híbrido (texto nativo primero) es la palanca principal de ahorro: los insertos
digitales (no escaneados) no consumen Vision.

---

## 10. Riesgos y notas

1. **Encabezados de la hoja:** si no coinciden exactamente, el nodo Google Sheets no
   encontrará columnas (el auto-mapeo es por nombre exacto).
2. **Mover archivos en Drive:** el movimiento a `Procesados/Errores` se replica a la
   nube por sincronización. Es intencional y reversible, pero tenlo presente.
3. **PDFs corruptos o protegidos:** la API responde `status:"error"` y el archivo va
   a `Errores/<marca>/` para revisión manual; no detiene el lote.
4. **Filas "Requiere Revisión":** cuando DeepSeek no encuentra Producto, Fabricante o
   Analito, la fila se marca así en `Estado Documento` para revisión humana.
5. **Reanudación:** el checkpoint está en `~/.n8n/estado/procesados.json` (dentro del
   volumen del contenedor n8n). Si se borra ese volumen, se pierde el progreso.
6. **Modo "Pruebas" de la app OAuth:** si la app de Google está en testing, el
   refresh token caduca a los 7 días y tendrás que re-autenticar. Publícala en
   Producción (o Interna si es Workspace) para evitarlo.
7. **Seguridad:** `client_secret.json`, `oauth/token.json` y `.env` están en
   `.gitignore` — nunca los subas al repositorio. El client_secret se compartió
   en un chat; si quedó expuesto a terceros, rótalo desde la consola de Google.
