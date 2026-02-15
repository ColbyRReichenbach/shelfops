"""
ShelfOps Backend Configuration

Uses pydantic-settings for type-safe environment variable loading.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

DEFAULT_JWT_SECRET = "dev-secret-change-in-production"
DEFAULT_ENCRYPTION_KEY = "dev-encryption-key-change-in-production"

# Find .env file: check CWD first, then parent (project root)
_env_file = Path(".env")
if not _env_file.exists():
    _parent_env = Path(__file__).resolve().parent.parent.parent / ".env"
    if _parent_env.exists():
        _env_file = _parent_env


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "ShelfOps"
    app_version: str = "1.0.0"
    app_env: str = "local"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://shelfops:dev_password@localhost:5432/shelfops"
    database_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    auth0_domain: str = ""
    auth0_client_id: str = ""
    auth0_audience: str = ""
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"

    # Square Integration
    square_client_id: str = ""
    square_client_secret: str = ""
    square_webhook_secret: str = ""
    square_environment: str = "sandbox"

    # Shopify Integration (SMB tier)
    shopify_api_key: str = ""
    shopify_api_secret: str = ""

    # ── Enterprise Integrations ──────────────────────────────────────
    # SFTP — batch file ingestion from retailer systems
    sftp_host: str = ""
    sftp_port: int = 22
    sftp_username: str = ""
    sftp_key_path: str = ""
    sftp_remote_dir: str = "/outbound"
    sftp_staging_dir: str = "/data/sftp/staging"

    # EDI X12 — enterprise document exchange
    edi_input_dir: str = "/data/edi/inbound"
    edi_output_dir: str = "/data/edi/outbound"
    edi_archive_dir: str = "/data/edi/archive"

    # Kafka — real-time event streaming
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "shelfops-ingest"
    kafka_schema_registry_url: str = ""
    integration_sla_overrides: str = ""

    # Email
    sendgrid_api_key: str = ""
    alert_from_email: str = "alerts@shelfops.com"

    # GCP
    gcp_project_id: str = ""
    vertex_ai_region: str = "us-central1"

    # Encryption
    encryption_key: str = DEFAULT_ENCRYPTION_KEY

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {
        "env_file": str(_env_file),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    settings = Settings()
    _enforce_security_guardrails(settings)
    return settings


def _enforce_security_guardrails(settings: Settings) -> None:
    env = settings.app_env.strip().lower()
    is_local = env in {"", "local", "dev", "development", "test"}
    if is_local:
        return

    if settings.debug:
        raise ValueError("Refusing to start with debug=true outside local/dev/test")
    if settings.jwt_secret == DEFAULT_JWT_SECRET:
        raise ValueError("Refusing to start with default JWT secret outside local/dev/test")
    if settings.encryption_key == DEFAULT_ENCRYPTION_KEY:
        raise ValueError("Refusing to start with default encryption key outside local/dev/test")
