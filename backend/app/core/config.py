"""Validated settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings; local defaults are safe for development only."""

    app_name: str = "Secure Multi-Modal RAG"
    environment: str = "development"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'secure_rag.db').as_posix()}"
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    upload_dir: Path = BACKEND_DIR / "uploads"
    max_upload_size_bytes: int = Field(default=10 * 1024 * 1024, gt=0, le=100 * 1024 * 1024)
    min_extracted_text_chars: int = Field(default=30, ge=1, le=1000)
    max_image_pixels: int = Field(default=25_000_000, gt=0)
    ocr_languages: str = "eng"
    tesseract_cmd: str | None = None
    jwt_secret_key: str
    jwt_access_token_minutes: int = 1440
    embedding_model_name: str = "all-MiniLM-L6-v2"
    vector_store_dir: Path = BACKEND_DIR / "vector_store"
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    openai_api_base: str = "https://api.openai.com/v1"
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_provider: str = "auto"
    llm_model_name: str = "openai/gpt-4o-mini"

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        """Reject missing-looking and short signing secrets."""
        if len(value.strip()) < 32 or value.startswith("replace-this"):
            raise ValueError("JWT_SECRET_KEY must be a unique value of at least 32 characters")
        return value

    @field_validator("jwt_access_token_minutes")
    @classmethod
    def validate_token_lifetime(cls, value: int) -> int:
        if not 1 <= value <= 43200:
            raise ValueError("JWT_ACCESS_TOKEN_MINUTES must be between 1 and 43200")
        return value

    @property
    def cors_origins(self) -> list[str]:
        """Return configured browser origins as a normalized list."""
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings instance for dependency injection."""
    return Settings()
