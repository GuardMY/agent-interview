from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Search for .env: 1) backend/.env  2) project-root/.env
_env_path = Path(__file__).resolve().parent.parent / ".env"  # backend/.env
if not _env_path.exists():
    _env_path = Path(__file__).resolve().parent.parent.parent / ".env"  # project/.env


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_env_path) if _env_path.exists() else ".env"
    )

    # Database
    # MySQL 8.0 async URL. Set DATABASE_URL with the deployment credentials.
    database_url: str = "mysql+asyncmy://:@localhost:3306/interview"
    redis_url: str = "redis://localhost:6379/0"

    # LLM Provider: "anthropic" | "deepseek" | "openai"
    llm_provider: str = "deepseek"

    # Anthropic API
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"

    # DeepSeek API
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # LLM common
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.7
    llm_request_timeout: int = 60

    # Interview defaults
    default_total_questions: int = 5
    default_time_limit_minutes: int = 30
    answer_timeout_seconds: int = 120
    timeout_grace_period_seconds: int = 30
    max_skip_count: int = 3
    sliding_window_size: int = 10

    # Scoring
    scoring_consecutive_good: int = 2
    scoring_consecutive_poor: int = 2

    # Admin
    master_admin_token: str = ""

    # Logging (relative to backend/ dir; use ../logs to avoid uvicorn reload loops)
    log_dir: str = "../logs"
    log_max_bytes: int = 10 * 1024 * 1024  # 10 MB
    log_backup_count: int = 5


settings = Settings()
