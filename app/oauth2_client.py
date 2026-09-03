import json
import logging
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

logger = logging.getLogger("pdf-extractor")

SCOPES = ["https://www.googleapis.com/auth/cloud-vision"]


class OAuth2VisionClient:
    """Autenticación OAuth2 con cliente tipo 'web' para Google Vision.

    El token se genera UNA sola vez de forma interactiva con generar_token.py
    y se guarda en TOKEN_FILE. La API solo lo carga y lo refresca si expira.
    """

    def __init__(self):
        self.token_file = os.getenv("TOKEN_FILE", "oauth/token.json")
        self.client_config = self._load_client_config()
        self._credentials = None
        self._client = None

    def _load_client_config(self) -> dict:
        secret_file = os.getenv("GOOGLE_CLIENT_SECRET_FILE", "")
        if secret_file and os.path.isfile(secret_file):
            with open(secret_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key in ("web", "installed"):
                if key in data:
                    return data[key]
            raise ValueError(f"{secret_file} no contiene una clave 'web' ni 'installed'")
        client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
        if client_id and client_secret:
            return {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        return {}

    @property
    def configured(self) -> bool:
        return bool(self.client_config)

    def get_client(self):
        if self._client is None:
            from google.cloud import vision

            self._client = vision.ImageAnnotatorClient(credentials=self.get_credentials())
        return self._client

    def get_credentials(self) -> Credentials:
        if self._credentials and self._credentials.valid:
            return self._credentials

        token_data = self._read_token()
        if token_data:
            self._credentials = Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=self.client_config.get("client_id"),
                client_secret=self.client_config.get("client_secret"),
                scopes=SCOPES,
            )
            if self._credentials.expired and self._credentials.refresh_token:
                try:
                    self._credentials.refresh(Request())
                    self._save_token()
                    logger.info("Token OAuth2 refrescado y guardado")
                except Exception as exc:
                    logger.error("No se pudo refrescar el token OAuth2: %s", exc)
                    raise RuntimeError(
                        "El token OAuth2 expiró y no se pudo refrescar. "
                        "Vuelve a ejecutar setup.ps1 (o generar_token.py) para autenticarte de nuevo."
                    ) from exc

        if not self._credentials or not self._credentials.valid:
            raise RuntimeError(
                "No hay token OAuth2 válido. Ejecuta setup.ps1 (o generar_token.py) "
                "una vez para autenticarte con Google."
            )
        return self._credentials

    def _read_token(self) -> dict | None:
        if not os.path.isfile(self.token_file):
            return None
        try:
            with open(self.token_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def _save_token(self) -> None:
        if not self._credentials:
            return
        os.makedirs(os.path.dirname(os.path.abspath(self.token_file)), exist_ok=True)
        data = {
            "token": self._credentials.token,
            "refresh_token": self._credentials.refresh_token,
            "expiry": self._credentials.expiry.isoformat() if self._credentials.expiry else None,
            "token_uri": self._credentials.token_uri,
            "scopes": list(self._credentials.scopes or []),
        }
        with open(self.token_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
