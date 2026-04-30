import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings.

    Field names map to upper-cased env vars automatically (e.g. ``llm_model``
    reads ``LLM_MODEL``). Don't put real secrets in source — values come from
    Railway/`.env` at runtime.

    LLM routing is handled by LiteLLM (CrewAI's default). The ``llm_model``
    string is passed straight through, so its prefix selects the provider:
      - ``gemini/gemini-2.5-flash``  -> Google Gemini  (needs ``GEMINI_API_KEY``)
      - ``gpt-4o``                    -> OpenAI         (needs ``OPENAI_API_KEY``)
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    llm_model: str = "gemini/gemini-2.5-flash"
    gemini_api_key: str = ""
    openai_api_key: str = ""
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
    s = Settings()
    # LiteLLM (used by CrewAI) reads provider keys from os.environ, not from
    # this Settings object. When the keys come from .env via pydantic-settings,
    # they don't reach os.environ on their own — push them through here.
    if s.gemini_api_key and not os.environ.get("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = s.gemini_api_key
    if s.openai_api_key and not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = s.openai_api_key
    return s
