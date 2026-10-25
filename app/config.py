"""Environment-specific application configuration."""

from __future__ import annotations

import os

MAX_RESUME_BYTES = 5 * 1024 * 1024


class Config:
    """Shared settings for all environments."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "development-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///ai_career_assistant.sqlite3"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_ENABLED = True
    MAX_RESUME_BYTES = MAX_RESUME_BYTES
    MAX_CONTENT_LENGTH = MAX_RESUME_BYTES + 64 * 1024
    UPLOAD_FOLDER: str | None = None
    EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    EMBEDDING_CACHE_DIR = os.environ.get("EMBEDDING_CACHE_DIR")


class DevelopmentConfig(Config):
    """Local development settings."""

    DEBUG = True


class TestingConfig(Config):
    """Isolated settings for the automated test suite."""

    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Settings suitable for deployment."""

    DEBUG = False
    SESSION_COOKIE_SECURE = True

    @classmethod
    def validate(cls) -> None:
        """Fail fast when production is missing its session secret."""
        if not os.environ.get("SECRET_KEY"):
            raise RuntimeError("SECRET_KEY must be set in production.")


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
