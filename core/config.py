from typing import Optional, Set

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    GEMINI_API_KEY: Optional[str] = None
    FLASK_SECRET_KEY: str

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
    MAX_FILE_SIZE_MB: int = 25  # Maximum size for a single uploaded file in MB
    MAX_TOTAL_UPLOAD_SIZE_MB: int = (
        100  # Maximum total size for all files in a single upload request
    )
    UPLOAD_FOLDER: str = "uploads"  # Directory for persistent storage of uploaded files
    MAX_EXTRACTED_TEXT_LENGTH: int = (
        1000000  # Maximum characters for combined extracted text sent to LLM
    )

    LLM_MODEL_NAME: str = "gemini-2.5-flash-preview-05-20"
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

    LLM_API_RETRY_ATTEMPTS: int = 3  # Number of retry attempts for the LLM API call
    LLM_API_RETRY_WAIT_SECONDS: int = 2  # Time to wait between retry attempts
    LLM_API_TIMEOUT_SECONDS: int = 120  # Timeout for the entire generation call

    LOG_LEVEL: str = "INFO"

    @property
    def MAX_FILE_SIZE_BYTES(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def MAX_TOTAL_UPLOAD_SIZE_BYTES(self) -> int:
        return self.MAX_TOTAL_UPLOAD_SIZE_MB * 1024 * 1024


settings = Settings()
