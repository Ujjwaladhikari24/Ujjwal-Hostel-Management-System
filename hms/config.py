"""Application configuration.

All secrets are read from environment variables (or a local .env file).
Nothing sensitive is hardcoded; see .env.example.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    # --- Core ---------------------------------------------------------
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'hostel.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- Session / cookies -------------------------------------------
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool(os.environ.get("SESSION_COOKIE_SECURE"), False)
    PERMANENT_SESSION_LIFETIME = int(os.environ.get("SESSION_MINUTES", 120)) * 60
    REMEMBER_COOKIE_HTTPONLY = True

    # --- CSRF ---------------------------------------------------------
    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_ENABLED = _bool(os.environ.get("WTF_CSRF_ENABLED"), True)

    # --- Uploads ------------------------------------------------------
    UPLOAD_FOLDER = BASE_DIR / "hms" / "static" / "uploads"
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024  # 4 MB
    ALLOWED_PHOTO_EXT = {"png", "jpg", "jpeg", "webp"}
    ALLOWED_DOC_EXT = {"png", "jpg", "jpeg", "webp", "pdf"}

    # --- App behaviour ------------------------------------------------
    STUDENT_SELF_REGISTRATION = _bool(
        os.environ.get("STUDENT_SELF_REGISTRATION"), True
    )
    HOSTEL_NAME = os.environ.get("HOSTEL_NAME", "Ujjwal Hostel")
    ITEMS_PER_PAGE = int(os.environ.get("ITEMS_PER_PAGE", 12))

    @staticmethod
    def init_app(app):
        Path(app.config["UPLOAD_FOLDER"], "photos").mkdir(parents=True, exist_ok=True)
        Path(app.config["UPLOAD_FOLDER"], "complaints").mkdir(parents=True, exist_ok=True)
