"""Verifica que todo esté listo para procesar los PDFs.

Uso:
  python verify_setup.py
"""

import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
PDFS_PATH = Path(os.getenv("PDFS_PATH", "D:/Trabajo/Meditec/Datos para la IA/Insertos"))


def check(name: str, ok: bool, hint: str) -> bool:
    print(f"  [{'OK' if ok else 'FALLA'}] {name}" + (f" -> {hint}" if not ok else ""))
    return ok


def main() -> None:
    print("VERIFICANDO SETUP")
    all_ok = True

    # PDFs
    if PDFS_PATH.exists():
        total = len(list(PDFS_PATH.rglob("*.pdf")))
        all_ok &= check("Carpeta de PDFs", total > 0, f"No hay PDFs en {PDFS_PATH}")
        if total > 0:
            print(f"      {total} PDFs encontrados")
    else:
        all_ok &= check("Carpeta de PDFs", False, f"No existe {PDFS_PATH}")

    # API
    try:
        import requests

        ok_api = requests.get("http://localhost:8000/health", timeout=5).status_code == 200
    except Exception:
        ok_api = False
    all_ok &= check("API corriendo", ok_api, "Ejecuta: python run.py (o docker compose up -d)")

    # Token Google Vision
    all_ok &= check(
        "Token de Google Vision",
        (PROJECT_DIR / "oauth" / "token.json").exists(),
        "Ejecuta: .\\auth.ps1 (requiere redirect URI http://localhost:8080 en la consola de Google)",
    )

    # Credenciales OAuth
    all_ok &= check(
        "client_secret.json",
        (PROJECT_DIR / "client_secret.json").exists(),
        "Copia tu archivo client_secret_*.json descargado de Google Cloud Console",
    )

    # .env
    env_path = PROJECT_DIR / ".env"
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        ok_deepseek = "DEEPSEEK_API_KEY" in content and "sk-tu_api_key_aqui" not in content
        ok_google = "GOOGLE_CLIENT_SECRET" in content
        all_ok &= check(".env - DeepSeek", ok_deepseek, "Pon tu clave real de DeepSeek en .env")
        all_ok &= check(".env - OAuth", ok_google, "Faltan GOOGLE_CLIENT_ID/SECRET en .env")
    else:
        all_ok &= check(".env", False, "No existe el archivo .env")

    # Dependencias del host
    try:
        import pandas  # noqa: F401
        import openpyxl  # noqa: F401
        import requests  # noqa: F401

        all_ok &= check("Dependencias Python", True, "")
    except ImportError:
        all_ok &= check(
            "Dependencias Python",
            False,
            "Ejecuta: python -m pip install -r requirements-host.txt",
        )

    print()
    if all_ok:
        print("TODO LISTO. Ejecuta: python run.py")
    else:
        print("FALTAN PASOS. Resuelve los puntos de arriba y vuelve a verificar.")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
