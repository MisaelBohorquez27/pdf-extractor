import json
import os
import re
import time

import httpx

from .models import FIELDS

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

SYSTEM_PROMPT = (
    "Eres un especialista en reactivos de diagnóstico in vitro (IVD). "
    "Tu tarea es extraer información técnica de insertos médicos y devolverla "
    "únicamente como un objeto JSON válido. "
    'Si un dato no aparece en el texto, usa el valor "N/A". '
    "No inventes información ni valores aproximados: copia los valores tal como aparecen."
)

FIELD_DESCRIPTIONS = {
    "Codigo": "número de referencia o catálogo del producto",
    "Producto": "nombre comercial del producto",
    "Fabricante": "empresa fabricante",
    "Carpeta": "carpeta/marca de origen (se te indica abajo)",
    "Nombre_Archivo": "nombre del archivo PDF (se te indica abajo)",
    "Analito_Parametro": "analito o parámetro que mide (ej: Alfa-fetoproteína, TSH)",
    "Tecnologia": "método de detección (ej: quimioluminiscencia, fluorescencia, ELISA)",
    "Muestra": "tipo de muestra (suero, plasma, sangre total, orina...)",
    "Volumen_Muestra": "volumen de muestra requerido (ej: 100 µL)",
    "Rango_Medicion": "rango de medición o linealidad (ej: 5-350 ng/mL)",
    "Valor_Referencia": "valores de referencia normales (ej: ≤ 10.9 ng/mL)",
    "Tiempo_Resultado": "tiempo hasta el resultado (ej: 15 minutos)",
    "Precision_Intra": "precisión intra-ensayo (CV%)",
    "Precision_Inter": "precisión inter-ensayo (CV%)",
    "Correlacion": "correlación con método de referencia (ej: r=0.998)",
    "Interferencias": "sustancias que interfieren (bilirrubina, hemólisis, lípidos...)",
    "Especificidad": "especificidad y reactividad cruzada",
    "Estabilidad": "estabilidad del reactivo",
    "Almacenamiento": "condiciones de almacenamiento (ej: 2-8 °C)",
    "Caducidad": "vida útil del producto (ej: 18 meses)",
    "Calibradores": "indica si incluye calibradores y cuántos",
    "Controles": "indica si incluye controles y cuántos",
    "Instrumento_Compatible": "instrumento o equipo compatible",
    "Formato": "presentación (cartucho, tira, kit, cassette...)",
    "Numero_Lote": "número de lote si aparece",
    "Fecha_Caducidad": "fecha de caducidad si aparece",
    "Registro_Sanitario": "número de registro sanitario o equivalente (CE, FDA, INVIMA, COFEPRIS...)",
    "Pais_Origen": "país de origen o fabricación",
    "PDF_Asociado": "dejar vacío",
    "URL_PDF": "dejar vacío",
    "Estado_Documento": 'devolver "Vigente"',
    "Observaciones_Tecnicas": "información técnica relevante no cubierta por otros campos",
    "Fecha_Extraccion": "dejar vacío",
}


class DeepSeekExtractor:
    """Llama directamente a la API REST de DeepSeek (sin librerías de OpenAI)."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY no está configurada")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    def extract(self, text: str, categoria: str = "", filename: str = "") -> dict:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self._build_prompt(text, categoria, filename)},
            ],
            "temperature": 0.1,
            "max_tokens": 4000,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        last_error = None
        with httpx.Client(timeout=120) as client:
            for attempt in range(3):
                try:
                    response = client.post(DEEPSEEK_URL, json=payload, headers=headers)
                    response.raise_for_status()
                    content = response.json()["choices"][0]["message"]["content"] or ""
                    return self._normalize(self._parse_json(content))
                except Exception as exc:
                    last_error = exc
                    time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"DeepSeek falló tras 3 intentos: {last_error}")

    def _build_prompt(self, text: str, categoria: str, filename: str) -> str:
        fields = "\n".join(f'- "{name}": {desc}' for name, desc in FIELD_DESCRIPTIONS.items())
        return (
            "Extrae los siguientes campos del INSERTO DE REACTIVO. "
            f'Carpeta: "{categoria}". Nombre_Archivo: "{filename}".\n\n'
            f"Campos a devolver (usa exactamente estos nombres de clave):\n{fields}\n\n"
            "Devuelve únicamente un objeto JSON con TODAS esas claves.\n\n"
            f"Texto del PDF:\n{text[:12000]}"
        )

    @staticmethod
    def _parse_json(content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError("DeepSeek no devolvió un JSON válido")

    @staticmethod
    def _normalize(data: dict) -> dict:
        payload = data
        for key in ("datos", "data", "result", "resultado", "fields"):
            if isinstance(data.get(key), dict):
                payload = data[key]
                break
        lowered = {str(k).strip().lower(): v for k, v in payload.items()}
        result = {}
        for field in FIELDS:
            value = lowered.get(field.lower(), "N/A")
            if value is None or str(value).strip() == "":
                value = "N/A"
            result[field] = str(value).strip()
        return result
