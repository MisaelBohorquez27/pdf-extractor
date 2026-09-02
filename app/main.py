import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, File, Form, UploadFile

from .extractor import DeepSeekExtractor
from .models import ExtractResponse
from .ocr import HybridOCR

LOG_DIR = os.getenv("LOG_DIR", "/app/logs")
try:
    os.makedirs(LOG_DIR, exist_ok=True)
    handlers = [
        logging.StreamHandler(),
        RotatingFileHandler(
            os.path.join(LOG_DIR, "extractor.log"),
            maxBytes=5_000_000,
            backupCount=3,
            encoding="utf-8",
        ),
    ]
except OSError:
    handlers = [logging.StreamHandler()]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=handlers,
)
logger = logging.getLogger("pdf-extractor")

app = FastAPI(title="PDF Extractor API", version="1.0.0")

ocr = HybridOCR()
extractor = DeepSeekExtractor()

CRITICAL_FIELDS = ("Producto", "Fabricante", "Analito_Parametro")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/extract", response_model=ExtractResponse)
async def extract_pdf(
    file: UploadFile = File(...),
    categoria: str = Form(""),
    filename: str = Form(""),
):
    try:
        pdf_bytes = await file.read()
        if not pdf_bytes:
            raise ValueError("PDF vacío")

        logger.info("Procesando %s (categoría: %s)", filename, categoria)

        result = ocr.process_pdf(pdf_bytes)
        logger.info(
            "%s: texto vía %s (%d caracteres)",
            filename,
            result["method"],
            len(result["text"]),
        )

        data = extractor.extract(result["text"], categoria, filename)
        data["Carpeta"] = categoria
        data["Nombre_Archivo"] = filename
        data["PDF_Asociado"] = filename
        data["Fecha_Extraccion"] = datetime.now(timezone.utc).isoformat()

        missing = [f for f in CRITICAL_FIELDS if data.get(f, "N/A") == "N/A"]
        if missing:
            data["Estado_Documento"] = "Requiere Revisión"
            obs = data.get("Observaciones_Tecnicas", "")
            data["Observaciones_Tecnicas"] = (
                obs + " | FALTAN: " + ", ".join(missing)
            ).strip(" |")

        logger.info("OK %s", filename)
        return ExtractResponse(**data)

    except Exception as exc:
        logger.exception("Error procesando %s", filename)
        return ExtractResponse(
            Carpeta=categoria,
            Nombre_Archivo=filename,
            PDF_Asociado=filename,
            status="error",
            error=str(exc),
            Estado_Documento="Error",
            Observaciones_Tecnicas=f"Error de procesamiento: {exc}",
        )


@app.post("/extract-mock", response_model=ExtractResponse)
async def extract_mock(
    file: UploadFile = File(...),
    categoria: str = Form(""),
    filename: str = Form(""),
):
    """Modo de prueba: no llama a Google Vision ni a DeepSeek. Devuelve datos de ejemplo."""
    await file.read()
    logger.info("MOCK %s (categoría: %s)", filename, categoria)
    return ExtractResponse(
        Producto=f"MOCK - {filename}",
        Fabricante=categoria,
        Carpeta=categoria,
        Nombre_Archivo=filename,
        PDF_Asociado=filename,
        Observaciones_Tecnicas="Fila de prueba generada en modo mock",
        Fecha_Extraccion=datetime.now(timezone.utc).isoformat(),
        status="success",
    )
