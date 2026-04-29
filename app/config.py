from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings.

    Field names map to upper-cased env vars automatically (e.g. ``openai_model``
    reads ``OPENAI_MODEL``). Don't put real secrets in source — values come from
    Railway/`.env` at runtime.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    tavily_api_key: str = ""

    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_jwt_secret: str = ""

    allowed_origins: str = "http://localhost:8080,https://*.vercel.app"
    log_level: str = "info"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
