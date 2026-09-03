"""Genera el token OAuth2 para Google Vision (se ejecuta UNA sola vez).

Uso:
  - En Docker (recomendado, desde setup.ps1):
      docker run --rm -it -p 8080:8080 ^
        -v "<proyecto>/client_secret.json:/app/client_secret.json:ro" ^
        -v "<proyecto>/oauth:/app/oauth" ^
        pdf-extractor-pdf-extractor-api python /app/generar_token.py

  - En el host (si tienes Python + dependencias):
      pip install google-auth-oauthlib google-cloud-vision
      python generar_token.py

El flujo abre una URL en el navegador, el usuario acepta los permisos y el
token se guarda en oauth/token.json para que la API lo use y refresque.
"""

import http.server
import json
import os
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

from google_auth_oauthlib.flow import Flow

SCOPES = ["https://www.googleapis.com/auth/cloud-vision"]
PORT = int(os.getenv("OAUTH_PORT", "8080"))


def load_client_config() -> tuple[dict, dict]:
    secret_file = os.getenv("GOOGLE_CLIENT_SECRET_FILE", "")
    candidates = [secret_file, "client_secret.json"]
    for path in candidates:
        if path and Path(path).is_file():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key in ("web", "installed"):
                if key in data:
                    return data[key], {"type": key, key: data[key]}
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    if client_id and client_secret:
        config = {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        return config, {"type": "web", "web": config}
    raise SystemExit(
        "No se encontraron credenciales OAuth2. Coloca client_secret.json en la "
        "carpeta del proyecto o define GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET."
    )


def pick_redirect_uri(config: dict) -> str:
    uris = config.get("redirect_uris") or []
    for uri in uris:
        if "localhost" in uri or "127.0.0.1" in uri:
            return uri
    print("=" * 60)
    print("IMPORTANTE: tu cliente OAuth no tiene redirect_uris registrados.")
    print(f"Agrega esta URI en Google Cloud Console -> Credenciales ->")
    print(f"tu cliente OAuth (Web) -> 'URIs de redireccionamiento autorizados':")
    print(f"    http://localhost:{PORT}")
    print("=" * 60)
    return f"http://localhost:{PORT}"


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    code: str | None = None

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        code = urllib.parse.parse_qs(query).get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        if code:
            type(self).code = code
            self.wfile.write(
                b"Autenticacion completada. Ya puedes cerrar esta pestana."
            )
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        else:
            self.wfile.write(b"Esperando codigo de autorizacion...")

    def log_message(self, *args):
        pass


def main() -> None:
    config, client_config = load_client_config()
    redirect_uri = pick_redirect_uri(config)
    if "localhost" not in redirect_uri and "127.0.0.1" not in redirect_uri:
        raise SystemExit(
            "Tu redirect_uris registrado no es local. Agrega "
            f"http://localhost:{PORT} en Google Cloud Console y vuelve a ejecutar."
        )
    host, _, port_str = redirect_uri.replace("http://", "").replace("https://", "").partition(":")
    port = int(port_str or PORT)

    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

    print()
    print("=" * 60)
    print("Abre esta URL en tu navegador (si no se abrio sola):")
    print(auth_url)
    print("=" * 60)
    webbrowser.open(auth_url)

    server = http.server.HTTPServer((host or "localhost", port), _CallbackHandler)
    print(f"Esperando la autorizacion en http://localhost:{port} ...")
    server.serve_forever()
    code = _CallbackHandler.code
    server.server_close()

    if not code:
        raise SystemExit("No se recibio el codigo de autorizacion.")

    flow.fetch_token(code=code)
    credentials = flow.credentials

    token_file = os.getenv("TOKEN_FILE", "oauth/token.json")
    token_path = Path(token_file)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(
        json.dumps(
            {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
                "token_uri": credentials.token_uri,
                "scopes": list(credentials.scopes or []),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Token guardado en {token_path}")

    try:
        from google.cloud import vision

        client = vision.ImageAnnotatorClient(credentials=credentials)
        response = client.annotate_image(
            {
                "image": {"content": b""},
                "features": [{"type_": vision.Feature.Type.TEXT_DETECTION}],
            }
        )
        if response.error.message:
            print(f"Advertencia de verificacion: {response.error.message}")
        else:
            print("Autenticacion verificada: el token funciona contra Google Vision.")
    except Exception as exc:
        print(f"No se pudo verificar el token (puede no afectar el uso real): {exc}")


if __name__ == "__main__":
    main()
