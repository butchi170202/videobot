"""Environment configuration management using Pydantic Settings."""

from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import VideoModel

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMP_STORAGE_DIR = BASE_DIR / "storage" / "temp"
TEMP_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = Field(default="", description="Telegram Bot Token from @BotFather")
    ALLOWED_USER_IDS: str = Field(
        default="",
        description="Comma-separated list of Telegram User IDs allowed to use the bot",
    )

    # Google Gemini / Veo API
    GEMINI_API_KEY: str = Field(default="", description="Google AI Studio Gemini API Key")
    GEMINI_MOCK_MODE: bool = Field(
        default=False,
        description="If true, simulates video generation without calling paid API",
    )

    # Optional Vertex AI support
    USE_VERTEX_AI: bool = Field(default=False)
    VERTEX_PROJECT_ID: str = Field(default="")
    VERTEX_LOCATION: str = Field(default="us-central1")

    # Model Settings
    DEFAULT_VIDEO_MODEL: str = Field(default=VideoModel.VEO_3_1_FAST.value)
    PROMPT_OPTIMIZER_MODEL: str = Field(default="gemini-2.5-flash")

    # Queue & Limits
    MAX_CONCURRENT_TASKS: int = Field(default=2, ge=1, le=10)
    POLL_INTERVAL_SECONDS: int = Field(default=10, ge=3, le=60)
    MAX_WAIT_SECONDS: int = Field(default=360, ge=60, le=900)
    MAX_IMAGE_SIZE_MB: int = Field(default=10, ge=1, le=20)
    LOG_LEVEL: str = Field(default="INFO")

    @property
    def allowed_users_set(self) -> set[int]:
        """Parse ALLOWED_USER_IDS string into a set of integer Telegram IDs."""
        if not self.ALLOWED_USER_IDS or not self.ALLOWED_USER_IDS.strip():
            return set()
        result: set[int] = set()
        for part in self.ALLOWED_USER_IDS.split(","):
            cleaned = part.strip()
            if cleaned.isdigit():
                result.add(int(cleaned))
        return result

    @field_validator("LOG_LEVEL")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        return v.upper().strip()


settings = Settings()

