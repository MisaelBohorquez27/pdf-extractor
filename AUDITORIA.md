# Auditoría del Proyecto — Extractor de Insertos PDF

**Fecha de auditoría:** 02/09/2026
**Ubicación:** `D:\Trabajo\Meditec\pdf-extractor`
**Estado general:** 🟡 Código completo y validado — pendiente solo credenciales y datos

---

## 1. Resumen ejecutivo

| Componente | Estado | Detalle |
|---|---|---|
| API FastAPI (código) | ✅ Completo | 4 módulos, 3 endpoints |
| Imagen Docker | ✅ Construida y probada | `pdf-extractor-pdf-extractor-api:latest` (417 MB) |
| Endpoints API | ✅ Probados | `/health`, `/extract`, `/extract-mock` OK |
| Sin dependencia OpenAI | ✅ Confirmado | Llamada REST directa a DeepSeek con `httpx` |
| Workflow n8n | ✅ Importable | JSON válido, 7 nodos |
| Script de despliegue | ✅ Listo | `setup.ps1` automatiza todo |
| Credencial Google Vision | ❌ Pendiente | Falta `service-account.json` |
| Clave DeepSeek | ⚠️ Dudosa | La del `.env` tiene 18 caracteres (parece placeholder) |
| PDFs | ❌ Pendiente | 0 archivos en `test_pdfs/` |
| Google Sheet destino | ❌ Pendiente | Falta ID de la hoja "base enriquecida" |
| Prueba con PDF real | ❌ Pendiente | No ejecutada aún |

---

## 2. Inventario de archivos

```
pdf-extractor/
├── .env                    (164 B)  Variables de entorno (necesita 2 correcciones)
├── docker-compose.yml      (390 B)  Orquestación del contenedor API
├── Dockerfile              (362 B)  Imagen Python 3.10 + poppler-utils
├── n8n-workflow.json     (7,516 B)  Workflow n8n importable (7 nodos)
├── requirements.txt        (211 B)  11 dependencias Python
├── setup.ps1             (4,054 B)  Despliegue automatizado en Windows
├── app/
│   ├── __init__.py           (0 B)
│   ├── main.py           (3,452 B)  Endpoints /health, /extract, /extract-mock
│   ├── models.py         (1,863 B)  33 campos de ExtractResponse
│   ├── ocr.py            (2,445 B)  OCR híbrido (texto nativo + Google Vision)
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
  │     · Si el PDF tiene capa de texto → pypdf (GRATIS, sin Vision)
  │     · Si es escaneado → pdf2image + Google Vision (OCR por página, máx. 15 págs.)
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
| 1 | Build Docker de la imagen | ✅ OK (instaló poppler + 11 paquetes Python) |
| 2 | `GET /health` | ✅ `{"status": "ok"}` |
| 3 | `POST /extract-mock` | ✅ Devuelve fila de ejemplo con categoria y filename |
| 4 | `POST /extract` (PDF inválido) | ✅ Responde `status:"error"` estructurado, no crashea |
| 5 | JSON del workflow n8n | ✅ Sintaxis válida, 7 nodos, conexiones consistentes |
| 6 | Imagen sin paquete `openai` | ✅ `pip list` dentro del contenedor: solo `httpx 0.27.2` |

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

### 5.1 Google Vision (`service-account.json`) — ❌ no existe

El `.env` actual apunta a una ruta placeholder:
```
GOOGLE_APPLICATION_CREDENTIALS=C:\Users\TuUsuario\Desktop\pdf-extractor\service-account.json
```

**Pasos:**
1. https://console.cloud.google.com → crear/eligir proyecto → habilitar **Cloud Vision API**
2. IAM y administración → Cuentas de servicio → Crear cuenta de servicio
3. Rol: **Usuario de API de Vision** → Crear clave → **JSON** → descargar
4. Renombrar a `service-account.json` y copiar a `D:\Trabajo\Meditec\pdf-extractor\`
5. Corregir el `.env`:
   ```
   GOOGLE_APPLICATION_CREDENTIALS=D:\Trabajo\Meditec\pdf-extractor\service-account.json
   ```

> Nota: `setup.ps1` crea un placeholder vacío si el archivo no existe (para poder
> levantar la API en modo mock), pero los PDFs escaneados NO se procesarán hasta
> colocar las credenciales reales.

### 5.2 DeepSeek (`DEEPSEEK_API_KEY`) — ⚠️ verificar

La clave actual en el `.env` tiene **18 caracteres**, longitud atípica para una clave
real de DeepSeek (suelen empezar con `sk-` y tener ~35). Verificarla en
https://platform.deepseek.com y reemplazar si es placeholder.

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

## 8. Checklist de arranque (orden recomendado)

1. ☐ Crear `service-account.json` en Google Cloud (sección 5.1)
2. ☐ Corregir `GOOGLE_APPLICATION_CREDENTIALS` en `.env`
3. ☐ Verificar `DEEPSEEK_API_KEY` en `.env`
4. ☐ Sincronizar `Material para ventas\Insertos` con Google Drive Desktop
5. ☐ Preparar la hoja "Base" con los 33 encabezados (sección 6)
6. ☐ Ejecutar `.\setup.ps1` (pide ruta del Drive e ID del Sheet)
7. ☐ En n8n (http://localhost:5678): crear credencial Google Sheets OAuth2
8. ☐ Importar `n8n-workflow.json` y verificar el nodo "Append a Base Enriquecida"
9. ☐ Prueba piloto: copiar 3–5 PDFs de distintas marcas y ejecutar
10. ☐ Revisar filas generadas y ajustar prompt si la extracción flojea
11. ☐ Ejecución completa de los 900

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
