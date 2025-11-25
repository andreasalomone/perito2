from typing import Optional, Set

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    GEMINI_API_KEY: Optional[str] = None
    FLASK_SECRET_KEY: str
    DATABASE_URL: Optional[str] = None
    REDIS_URL: str = "redis://localhost:6379/0"

    AUTH_USERNAME: str = Field(default="admin", validation_alias="BASIC_AUTH_USERNAME")
    AUTH_PASSWORD: str = Field(
        default="defaultpassword", validation_alias="BASIC_AUTH_PASSWORD"
    )

    # Multi-user authentication (JSON format: {"user1": "pass1", "user2": "pass2"})
    # If set, overrides AUTH_USERNAME/AUTH_PASSWORD for multiple user support
    ALLOWED_USERS_JSON: Optional[str] = None

    ALLOWED_EXTENSIONS: Set[str] = {
        "png",
        "jpg",
        "jpeg",
        "xlsx",
        "pdf",
        "docx",
        "txt",
        "eml",
    }
    MAX_FILE_SIZE_MB: int = 50  # Maximum size for a single uploaded file in MB
    MAX_TOTAL_UPLOAD_SIZE_MB: int = (
        200  # Maximum total size for all files in a single upload request
    )
    UPLOAD_FOLDER: str = "uploads"  # Directory for persistent storage of uploaded files
    MAX_EXTRACTED_TEXT_LENGTH: int = (
        4000000  # Maximum characters for combined extracted text sent to LLM
    )

    LLM_MODEL_NAME: str = "gemini-2.5-pro"
    LLM_FALLBACK_MODEL_NAME: str = (
        "gemini-2.5-flash-lite"  # Fallback model when primary is overloaded
    )
    LLM_TEMPERATURE: float = 0.5
    LLM_MAX_TOKENS: int = 64000  # Max tokens for the LLM response

    # DOCX Generation Settings
    DOCX_FONT_NAME: str = "Times New Roman"
    DOCX_FONT_SIZE_NORMAL: int = 12
    DOCX_FONT_SIZE_HEADING: int = 12
    DOCX_LINE_SPACING: float = 1.5
    DOCX_SPACE_AFTER_PARAGRAPH: int = 0  # Punti di spazio dopo un paragrafo standard

    # Cache Settings
    REPORT_PROMPT_CACHE_NAME: Optional[str] = (
        None  # Set this in .env to reuse a specific cache
    )
    CACHE_TTL_DAYS: int = 2  # Time-to-live for the prompt cache in days
    CACHE_DISPLAY_NAME: str = "ReportGenerationPromptsV2"  # Display name for new caches
    CACHE_STATE_FILE: str = (
        "instance/cache_state.json"  # File to store dynamic cache state
    )

    LLM_API_RETRY_ATTEMPTS: int = 3  # Number of retry attempts for the LLM API call
    LLM_API_RETRY_WAIT_SECONDS: int = 2  # Time to wait between retry attempts
    LLM_API_TIMEOUT_SECONDS: int = 120  # Timeout for the entire generation call

    # Pricing Settings (Gemini 2.5 Pro)
    # Prices are per 1 million tokens
    PRICE_INPUT_TIER_1: float = 1.25  # <= 200k tokens
    PRICE_INPUT_TIER_2: float = 2.50  # > 200k tokens
    PRICE_OUTPUT_TIER_1: float = 10.00  # <= 200k tokens
    PRICE_OUTPUT_TIER_2: float = 15.00  # > 200k tokens
    PRICE_CACHE_TIER_1: float = 0.125  # <= 200k tokens
    PRICE_CACHE_TIER_2: float = 0.25  # > 200k tokens

    LOG_LEVEL: str = "INFO"

    @property
    def MAX_FILE_SIZE_BYTES(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def MAX_TOTAL_UPLOAD_SIZE_BYTES(self) -> int:
        return self.MAX_TOTAL_UPLOAD_SIZE_MB * 1024 * 1024


settings = Settings()
