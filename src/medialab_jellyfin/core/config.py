"""Application configuration loaded from environment variables and an optional .env file."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Application configuration parameters."""

    model_config = SettingsConfigDict(env_file=".env")

    jellyfin_host: str = Field(default="127.0.0.1")
    jellyfin_port: int = Field(default=8096)
    jellyfin_api_key: str | None = Field(default=None)

    api_key: str | None = Field(default=None)
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8001)


config: AppConfig = AppConfig()
