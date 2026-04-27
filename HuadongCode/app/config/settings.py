"""Global runtime settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Huadong Hydro FastMCP Runtime"
    version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
