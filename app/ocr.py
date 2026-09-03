import io
import logging

from google.cloud import vision
from pdf2image import convert_from_bytes
from pypdf import PdfReader

from .oauth2_client import OAuth2VisionClient

logger = logging.getLogger("pdf-extractor")


class GoogleVisionOCR:
    """Extrae texto de un PDF.

    Estrategia híbrida:
    1. Si el PDF tiene capa de texto nativa, se usa esa (gratis, sin
       autenticación ni llamadas a Google).
    2. Si es un PDF escaneado (imágenes), se aplica OCR con Google Vision
       autenticado por OAuth2 (token generado con generar_token.py).
    """

    def __init__(self, min_text_chars: int = 100, max_ocr_pages: int = 15, dpi: int = 200):
        self.min_text_chars = min_text_chars
        self.max_ocr_pages = max_ocr_pages
        self.dpi = dpi
        self.oauth = OAuth2VisionClient()
        if not self.oauth.configured:
            logger.warning(
                "OAuth2 sin configurar: los PDFs escaneados no se podrán procesar. "
                "Revisa GOOGLE_CLIENT_SECRET_FILE o GOOGLE_CLIENT_ID/SECRET."
            )

    def extract_native_text(self, pdf_bytes: bytes) -> str:
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            pages = []
            for i, page in enumerate(reader.pages):
                text = (page.extract_text() or "").strip()
                if text:
                    pages.append(f"=== PÁGINA {i + 1} ===\n{text}")
            return "\n\n".join(pages)
        except Exception:
            return ""

    def ocr_pdf(self, pdf_bytes: bytes) -> str:
        if not self.oauth.configured:
            raise RuntimeError(
                "Faltan credenciales OAuth2 (GOOGLE_CLIENT_SECRET_FILE o "
                "GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET)."
            )
        client = self.oauth.get_client()

        images = convert_from_bytes(pdf_bytes, dpi=self.dpi)
        parts = []
        for i, img in enumerate(images[: self.max_ocr_pages]):
            try:
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                image = vision.Image(content=buf.getvalue())
                response = client.text_detection(image=image)
                if response.error.message:
                    raise RuntimeError(response.error.message)
                text = response.text_annotations[0].description if response.text_annotations else ""
                parts.append(f"=== PÁGINA {i + 1} (OCR) ===\n{text}")
            except Exception as exc:
                parts.append(f"=== PÁGINA {i + 1} (ERROR OCR) ===\n{exc}")
        return "\n\n".join(parts)

    def process_pdf(self, pdf_bytes: bytes, force_ocr: bool = False) -> dict:
        if not force_ocr:
            text = self.extract_native_text(pdf_bytes)
            if len(text.strip()) >= self.min_text_chars:
                return {"text": text, "method": "texto_nativo"}
        return {"text": self.ocr_pdf(pdf_bytes), "method": "google_vision"}
