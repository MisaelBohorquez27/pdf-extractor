"""Procesa todos los PDFs de la carpeta Insertos/ contra la API local y guarda en Excel.

Uso:
  python process_all_pdfs.py

Requisitos: la API corriendo (python run.py o docker compose up -d) y el token
de Google Vision generado (.\auth.ps1). El progreso se guarda para reanudar.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

PROJECT_DIR = Path(__file__).resolve().parent

API_URL = os.getenv("API_URL", "http://localhost:8000/extract")
PDFS_PATH = Path(os.getenv("PDFS_PATH", "D:/Trabajo/Meditec/Datos para la IA/Insertos"))
EXCEL_PATH = PROJECT_DIR / os.getenv("EXCEL_PATH", "resultados.xlsx")
LOG_PATH = PROJECT_DIR / os.getenv("LOG_PATH", "errores.log")
PROGRESS_PATH = PROJECT_DIR / os.getenv("PROGRESS_PATH", "progress.json")

COLUMNAS = [
    "Codigo", "Producto", "Fabricante", "Carpeta", "Nombre_Archivo",
    "Analito_Parametro", "Tecnologia", "Muestra", "Volumen_Muestra",
    "Rango_Medicion", "Valor_Referencia", "Tiempo_Resultado",
    "Precision_Intra", "Precision_Inter", "Correlacion",
    "Interferencias", "Especificidad", "Estabilidad", "Almacenamiento",
    "Caducidad", "Calibradores", "Controles", "Instrumento_Compatible",
    "Formato", "Numero_Lote", "Fecha_Caducidad", "Registro_Sanitario",
    "Pais_Origen", "PDF_Asociado", "URL_PDF", "Estado_Documento",
    "Observaciones_Tecnicas", "Fecha_Extraccion",
]


def cargar_progreso() -> dict:
    if PROGRESS_PATH.exists():
        with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"procesados": [], "errores": []}


def guardar_progreso(progreso: dict) -> None:
    with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
        json.dump(progreso, f, indent=2, ensure_ascii=False)


def obtener_pdfs() -> list:
    if not PDFS_PATH.exists():
        print(f"[ERROR] No existe la carpeta {PDFS_PATH}")
        sys.exit(1)
    pdfs = []
    for pdf in sorted(PDFS_PATH.rglob("*.pdf")):
        rel = pdf.parent.relative_to(PDFS_PATH)
        categoria = rel.parts[0] if rel.parts else "General"
        pdfs.append({"categoria": categoria, "filename": pdf.name, "path": str(pdf)})
    return pdfs


def procesar_pdf(pdf_info: dict, session: requests.Session):
    try:
        with open(pdf_info["path"], "rb") as f:
            response = session.post(
                API_URL,
                files={"file": (pdf_info["filename"], f, "application/pdf")},
                data={"categoria": pdf_info["categoria"], "filename": pdf_info["filename"]},
                timeout=900,
            )
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}: {response.text[:300]}"
        data = response.json()
        data["Carpeta"] = pdf_info["categoria"]
        data["Nombre_Archivo"] = pdf_info["filename"]
        if data.get("status") != "success":
            return False, data.get("error") or "Error desconocido"
        return True, data
    except Exception as exc:
        return False, str(exc)


def cargar_excel_existente() -> pd.DataFrame:
    if not EXCEL_PATH.exists():
        return pd.DataFrame()
    try:
        return pd.read_excel(EXCEL_PATH, sheet_name="Base", dtype=str)
    except Exception:
        return pd.DataFrame()


def claves_excel(df: pd.DataFrame) -> set:
    if df.empty or "Carpeta" not in df.columns or "Nombre_Archivo" not in df.columns:
        return set()
    claves = df["Carpeta"].fillna("").astype(str) + "/" + df["Nombre_Archivo"].fillna("").astype(str)
    return {k for k in claves if k not in ("/", "")}


def guardar_excel(nuevos: list) -> None:
    if not nuevos:
        return
    df_nuevos = pd.DataFrame(nuevos)
    for col in COLUMNAS:
        if col not in df_nuevos.columns:
            df_nuevos[col] = "N/A"
    df_nuevos = df_nuevos[COLUMNAS].fillna("N/A")

    df_previo = cargar_excel_existente()
    if df_previo.empty:
        df = df_nuevos
    else:
        for col in COLUMNAS:
            if col not in df_previo.columns:
                df_previo[col] = "N/A"
        df_previo = df_previo[COLUMNAS].fillna("N/A")
        df = pd.concat([df_previo, df_nuevos], ignore_index=True)
        df = df.drop_duplicates(subset=["Carpeta", "Nombre_Archivo"], keep="last")

    df.to_excel(EXCEL_PATH, index=False, sheet_name="Base")
    print(f"    [Excel actualizado: {len(df)} filas -> {EXCEL_PATH}]")


def guardar_excel_con_reintentos(nuevos: list, intentos: int = 3) -> bool:
    for intento in range(1, intentos + 1):
        try:
            guardar_excel(nuevos)
            return True
        except Exception as exc:
            print(f"    [AVISO] No se pudo escribir el Excel (intento {intento}/{intentos}): {exc}")
            time.sleep(5)
    return False


def main() -> None:
    print("INICIANDO PROCESAMIENTO DE PDFS")
    print(f"  Carpeta:  {PDFS_PATH}")
    print(f"  Excel:    {EXCEL_PATH}")

    todos = obtener_pdfs()
    print(f"  PDFs encontrados: {len(todos)}")

    if not todos:
        print("[ERROR] No se encontraron PDFs")
        sys.exit(1)

    progreso = cargar_progreso()
    previos = set(progreso.get("procesados", [])) | claves_excel(cargar_excel_existente())
    pendientes = [p for p in todos if f"{p['categoria']}/{p['filename']}" not in previos]
    print(f"  Pendientes: {len(pendientes)}")

    if not pendientes:
        print("Todos los PDFs ya fueron procesados.")
        sys.exit(0)

    session = requests.Session()
    nuevos = []
    pendientes_marcar = []
    errores = []

    for i, pdf in enumerate(pendientes, 1):
        print(f"[{i}/{len(pendientes)}] {pdf['categoria']}/{pdf['filename']}")
        ok, data = procesar_pdf(pdf, session)
        if ok:
            print(f"    OK - Producto: {data.get('Producto', 'N/A')}")
            nuevos.append(data)
            pendientes_marcar.append(f"{pdf['categoria']}/{pdf['filename']}")
        else:
            print(f"    ERROR: {data}")
            errores.append({"categoria": pdf["categoria"], "archivo": pdf["filename"], "error": data})
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()} {pdf['categoria']}/{pdf['filename']} -> {data}\n")

        if i % 10 == 0 or i == len(pendientes):
            if pendientes_marcar:
                if guardar_excel_con_reintentos(nuevos):
                    progreso["procesados"].extend(pendientes_marcar)
                    guardar_progreso(progreso)
                    nuevos = []
                    pendientes_marcar = []
                    print(f"    [checkpoint: {len(progreso['procesados'])} procesados en total]")
                else:
                    print()
                    print("NO SE PUDO GUARDAR EL EXCEL.")
                    print("Si tienes resultados.xlsx abierto en Excel, CIERRALO.")
                    print("Luego vuelve a ejecutar: python run.py")
                    print("Continuará desde el ultimo checkpoint sin perder nada.")
                    break

    if errores:
        print(f"{len(errores)} PDFs fallaron. Detalle en {LOG_PATH}")

    print("PROCESO COMPLETADO")


if __name__ == "__main__":
    main()
