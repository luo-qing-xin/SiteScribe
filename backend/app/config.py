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
    knowledge_dir: Path = BASE_DIR / "data" / "knowledge"
    asr_provider: str = "faster_whisper"
    asr_model: str = "small"
    asr_device: str = "cpu"
    asr_compute_type: str = "int8"
    asr_default_language: str | None = "zh"
    audio_max_bytes: int = 50 * 1024 * 1024
    audio_max_duration_seconds: float = 300
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    event_extraction_provider: str = "openai_compatible"
    event_extraction_base_url: str = ""
    event_extraction_api_key: str = ""
    event_extraction_model: str = ""
    event_extraction_timeout_seconds: float = 60
    event_extraction_max_retries: int = 1
    ai_provider: str = "openai"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    event_extraction_image_max_dimension: int = 1600
    event_extraction_image_quality: int = 82
    rag_provider: str = "mock"
    rag_model: str = "mock-grounded-v1"
    rag_base_url: str = ""
    rag_api_key: str = ""
    rag_timeout_seconds: float = 60

    model_config = SettingsConfigDict(env_file=BASE_DIR.parent / ".env", extra="ignore")


settings = Settings()
