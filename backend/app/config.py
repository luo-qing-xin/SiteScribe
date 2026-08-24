from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'site_secretary.db'}"
    jwt_secret: str = "development-only-change-me-at-least-32-bytes"
    jwt_expire_hours: int = 24 * 7
    cookie_secure: bool = False
    frontend_origin: str = "http://localhost:3000"
    upload_dir: Path = BASE_DIR / "data" / "uploads"

    model_config = SettingsConfigDict(env_file=BASE_DIR.parent / ".env", extra="ignore")


settings = Settings()
