from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///data/future_prediction.db"
    # No Anthropic API key needed - all LLM reasoning handled by Claude Code scheduled tasks

    model_config = {"env_file": ".env"}


settings = Settings()
