from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://predictions:predictions_dev@localhost:5432/future_prediction"
    redis_url: str = "redis://localhost:6379/0"
    anthropic_api_key: str = ""

    # Celery schedule intervals (seconds)
    collection_interval: int = 3600  # 1 hour
    scoring_interval: int = 86400  # 24 hours

    model_config = {"env_file": ".env"}


settings = Settings()
