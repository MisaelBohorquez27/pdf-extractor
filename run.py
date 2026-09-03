"""Levanta la API (si no está corriendo) y ejecuta el procesamiento de PDFs.

Uso:
  python run.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import requests

PROJECT_DIR = Path(__file__).resolve().parent
API_HEALTH = os.getenv("API_HEALTH", "http://localhost:8000/health")


def check_api() -> bool:
    try:
        return requests.get(API_HEALTH, timeout=5).status_code == 200
    except Exception:
        return False


def start_api() -> bool:
    print("Levantando la API con Docker Compose...")
    result = subprocess.run(
        ["docker", "compose", "up", "-d"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        return False
    for _ in range(60):
        if check_api():
            return True
        time.sleep(2)
    return False


def main() -> None:
    if not check_api():
        if not start_api():
            print("No se pudo levantar la API. Prueba manualmente: docker compose up -d")
            sys.exit(1)
        print("API lista en http://localhost:8000")
    else:
        print("API ya estaba corriendo")

    token = PROJECT_DIR / "oauth" / "token.json"
    if not token.exists():
        print("Falta el token de Google Vision. Ejecuta: .\\auth.ps1")
        sys.exit(1)

    print("Iniciando procesamiento de PDFs...")
    subprocess.run([sys.executable, str(PROJECT_DIR / "process_all_pdfs.py")])


if __name__ == "__main__":
    main()
