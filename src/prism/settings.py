"""PRISM configuration loader using pydantic-settings."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Variables prefixed with PRISM_ are read automatically.
    GITHUB_PAT is read without prefix (it's a standard GitHub convention).
    """

    model_config = SettingsConfigDict(
        env_prefix="PRISM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # GitHub PAT — no PRISM_ prefix, reads from GITHUB_PAT env var
    github_pat: str = Field(validation_alias="GITHUB_PAT")

    # Postgres connection
    postgres_user: str = Field(default="prism", validation_alias="POSTGRES_USER")
    postgres_password: str = Field(default="changeme", validation_alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="prism", validation_alias="POSTGRES_DB")
    postgres_host: str = Field(default="localhost", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")

    # Collection tuning
    log_level: str = "INFO"
    default_page_size: int = 100
    min_page_size: int = 5
    snapshot_batch_size: int = 10
    rate_limit_buffer: int = 300
    rate_limit_sleep_secs: int = 60
    polite_sleep_secs: float = 0.5
    max_retries: int = 10
    retry_backoff_base: int = 2
    request_timeout: int = 90

    # Date window for collection
    date_start: str = "2019-01-01T00:00:00Z"
    date_end: str | None = None

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection URL for SQLAlchemy."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sql_init_path(self) -> Path:
        """Path to the SQL init script."""
        return Path(__file__).resolve().parent.parent.parent / "sql" / "001_init.sql"
