from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    database_url: str | None = None
    google_api_key: str = "test-key-not-real"
    anthropic_api_key: str = ""
    planner_model: str = "gemini-3.5-flash-lite"
    explainer_model: str = "gemini-3.5-flash-lite"
    planner_temperature: float = 0.1
    storage_dir: str = str(Path(__file__).parent / "storage")
    max_upload_size_mb: int = 50
    allowed_extensions: tuple = (".csv", ".xlsx", ".xls")
    max_rows_dataset: int = 1_000_000
    max_columns_dataset: int = 200
    max_rows_to_planner: int = 100
    max_rows_to_chart: int = 50
    analysis_timeout_seconds: int = 5
    suggested_questions_count: int = 8
    # How long an uploaded/confirmed session's data sticks around before an
    # opportunistic sweep can delete it (see sessions/store.py's
    # cleanup_expired_sessions()). Portfolio-scope alternative to a real
    # background job/cron -- there's no long-running worker process here,
    # so cleanup piggybacks on every new /upload/inspect call instead.
    session_ttl_hours: float = 24


settings = Settings()

_storage_root = Path(settings.storage_dir)
for _sub in ("uploads", "datasets", "charts", "reports", "sessions"):
    (_storage_root / _sub).mkdir(parents=True, exist_ok=True)