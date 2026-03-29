from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    discord_token: str = ""
    discord_guild_id: int = 0

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # Autonomous tick interval (seconds) — how often agents check mailbox
    tick_interval: float = 30.0

    # Maximum conversation memory per agent (recent messages kept)
    max_memory: int = 50

    # Rate-limit: minimum seconds between LLM calls per agent
    agent_cooldown: float = 5.0

    log_level: str = "INFO"


settings = Settings()
