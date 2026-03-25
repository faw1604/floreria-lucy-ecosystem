# Application configuration
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Florería Lucy Ecosystem"
    DATABASE_URL: str = "sqlite:///./floreria_lucy.db"
    SECRET_KEY: str = "change-me-in-production"

    class Config:
        env_file = ".env"


settings = Settings()
