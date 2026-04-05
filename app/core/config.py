from pydantic_settings import BaseSettings
from zoneinfo import ZoneInfo

class Settings(BaseSettings):
    APP_NAME: str = "Florería Lucy — Ecosistema"
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = ""
    DATABASE_URL: str = "sqlite+aiosqlite:///./floreria.db"
    TIMEZONE: str = "America/Chihuahua"
    PANEL_PASSWORD: str = ""
    SESSION_SECRET: str = ""
    SESION_DURACION: int = 43200  # 12 horas en segundos

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
TZ = ZoneInfo(settings.TIMEZONE)
