from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Environment
    environment: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"

    # Database (Supabase Postgres — currently unused by app logic;
    # sessions are stateless SQLite. Reserved for future session/history persistence.)
    database_url: str | None = None

    # LLM provider keys
    google_api_key: str = ""
    anthropic_api_key: str = ""

    # LLM model selection
    planner_model: str = "gemini-3.5-flash-lite"
    explainer_model: str = "gemini-3.5-flash-lite"
    planner_temperature: float = 0.1  # low temp: plan selection should be near-deterministic

    # Storage / sessions
    storage_dir: str = str(Path(__file__).parent / "storage")

    # Upload validation
    max_upload_size_mb: int = 50
    allowed_extensions: tuple[str, ...] = (".csv", ".xlsx", ".xls")

    # Safety limits
    max_rows_dataset: int = 1_000_000       # hard ceiling before rejecting/sampling a dataset
    max_rows_to_planner: int = 100          # rows/sample summary size shown to planner LLM
    max_rows_to_chart: int = 50
    analysis_timeout_seconds: int = 5       # guards pathological Pandas ops (e.g. huge groupby)


settings = Settings()

_storage_root = Path(settings.storage_dir)
for _sub in ("uploads", "datasets", "charts", "reports", "sessions"):
    (_storage_root / _sub).mkdir(parents=True, exist_ok=True)