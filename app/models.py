from typing import Optional

from pydantic import BaseModel

FIELDS = [
    "Codigo",
    "Producto",
    "Fabricante",
    "Carpeta",
    "Nombre_Archivo",
    "Analito_Parametro",
    "Tecnologia",
    "Muestra",
    "Volumen_Muestra",
    "Rango_Medicion",
    "Valor_Referencia",
    "Tiempo_Resultado",
    "Precision_Intra",
    "Precision_Inter",
    "Correlacion",
    "Interferencias",
    "Especificidad",
    "Estabilidad",
    "Almacenamiento",
    "Caducidad",
    "Calibradores",
    "Controles",
    "Instrumento_Compatible",
    "Formato",
    "Numero_Lote",
    "Fecha_Caducidad",
    "Registro_Sanitario",
    "Pais_Origen",
    "PDF_Asociado",
    "URL_PDF",
    "Estado_Documento",
    "Observaciones_Tecnicas",
    "Fecha_Extraccion",
]


class ExtractResponse(BaseModel):
    Codigo: str = "N/A"
    Producto: str = "N/A"
    Fabricante: str = "N/A"
    Carpeta: str = "N/A"
    Nombre_Archivo: str = "N/A"
    Analito_Parametro: str = "N/A"
    Tecnologia: str = "N/A"
    Muestra: str = "N/A"
    Volumen_Muestra: str = "N/A"
    Rango_Medicion: str = "N/A"
    Valor_Referencia: str = "N/A"
    Tiempo_Resultado: str = "N/A"
    Precision_Intra: str = "N/A"
    Precision_Inter: str = "N/A"
    Correlacion: str = "N/A"
    Interferencias: str = "N/A"
    Especificidad: str = "N/A"
    Estabilidad: str = "N/A"
    Almacenamiento: str = "N/A"
    Caducidad: str = "N/A"
    Calibradores: str = "N/A"
    Controles: str = "N/A"
    Instrumento_Compatible: str = "N/A"
    Formato: str = "N/A"
    Numero_Lote: str = "N/A"
    Fecha_Caducidad: str = "N/A"
    Registro_Sanitario: str = "N/A"
    Pais_Origen: str = "N/A"
    PDF_Asociado: str = ""
    URL_PDF: str = ""
    Estado_Documento: str = "Vigente"
    Observaciones_Tecnicas: str = "N/A"
    Fecha_Extraccion: str = ""
    status: str = "success"
    error: Optional[str] = None
