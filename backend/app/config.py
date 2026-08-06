from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):

     # Database
    database_url: str
    
    # LLM provider keys
    google_api_key: str = ""
    anthropic_api_key: str = ""

    # Storage / sessions
    storage_dir: str = str(Path(__file__).parent / "storage")

    # LLM model selection
    planner_model: str = "gemini-2.5-flash-lite"
    explainer_model: str = "gemini-2.5-flash-lite"

    # Safety limits
    max_rows_to_model: int = 100
    max_rows_to_chart: int = 50
    max_loop_iterations: int = 5
    query_timeout_seconds: int = 5

    class Config:
        env_file = ".env"


settings = Settings()

# Ensure storage directories exist at import time
_storage_root = Path(settings.storage_dir)
(_storage_root / "uploads").mkdir(parents=True, exist_ok=True)
(_storage_root / "datasets").mkdir(parents=True, exist_ok=True)
(_storage_root / "charts").mkdir(parents=True, exist_ok=True)
(_storage_root / "reports").mkdir(parents=True, exist_ok=True)
(_storage_root / "sessions").mkdir(parents=True, exist_ok=True)