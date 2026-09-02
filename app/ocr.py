import io

from google.cloud import vision
from pdf2image import convert_from_bytes
from pypdf import PdfReader


class HybridOCR:
    """Extrae texto de un PDF.

    Estrategia híbrida:
    1. Si el PDF tiene capa de texto nativa, se usa esa (gratis y rápido).
    2. Si no (PDF escaneado/imágenes), se aplica OCR con Google Vision.
    """

    def __init__(self, min_text_chars: int = 100, max_ocr_pages: int = 15, dpi: int = 200):
        self.min_text_chars = min_text_chars
        self.max_ocr_pages = max_ocr_pages
        self.dpi = dpi
        self._vision_client = None

    @property
    def vision_client(self) -> vision.ImageAnnotatorClient:
        if self._vision_client is None:
            self._vision_client = vision.ImageAnnotatorClient()
        return self._vision_client

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
        images = convert_from_bytes(pdf_bytes, dpi=self.dpi)
        parts = []
        for i, img in enumerate(images[: self.max_ocr_pages]):
            try:
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                image = vision.Image(content=buf.getvalue())
                response = self.vision_client.text_detection(image=image)
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
