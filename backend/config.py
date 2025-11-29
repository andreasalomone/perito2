from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Google Cloud Project Info
    GOOGLE_CLOUD_PROJECT: str
    GOOGLE_CLOUD_REGION: str = "europe-west1"
    
    # Cloud SQL (Database)
    # Format: "project-id:region:instance-name" (Get this from GCP Console > SQL > Overview)
    CLOUD_SQL_CONNECTION_NAME: str 
    DB_USER: str = "report_user"
    DB_PASS: str
    DB_NAME: str = "perizia_db"
    
    # Storage & Queue
    STORAGE_BUCKET_NAME: str
    # Format: "projects/{project}/locations/{location}/queues/{queue_name}"
    CLOUD_TASKS_QUEUE_PATH: str 
    
    # AI
    GEMINI_API_KEY: str
    
    # Local or Not
    RUN_LOCALLY: bool = False  # Default to False (Production)

    # Security
    # In production (Cloud Run), Firebase credentials are auto-detected via IAM.
    # For local dev, you might set GOOGLE_APPLICATION_CREDENTIALS env var.
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # --- Application Settings (Legacy Support) ---
    # File Processing
    MAX_FILE_SIZE_MB: int = 50
    MAX_TOTAL_UPLOAD_SIZE_MB: int = 200
    MAX_EXTRACTED_TEXT_LENGTH: int = 4000000
    ALLOWED_EXTENSIONS: set = {"png", "jpg", "jpeg", "xlsx", "pdf", "docx", "txt", "eml"}
    UPLOAD_FOLDER: str = "/tmp"

    # LLM Configuration
    LLM_MODEL_NAME: str = "gemini-2.5-pro" 
    LLM_FALLBACK_MODEL_NAME: str = "gemini-2.5-flash-lite"
    LLM_TEMPERATURE: float = 0.5
    LLM_MAX_TOKENS: int = 64000
    LLM_API_RETRY_ATTEMPTS: int = 3
    LLM_API_RETRY_WAIT_SECONDS: int = 2
    LLM_API_TIMEOUT_SECONDS: int = 600

# Pricing (Gemini 2.5 Pro)
    PRICE_INPUT_TIER_1: float = 1.25
    PRICE_INPUT_TIER_2: float = 2.50
    PRICE_OUTPUT_TIER_1: float = 10.00
    PRICE_OUTPUT_TIER_2: float = 15.00
    PRICE_CACHE_TIER_1: float = 0.125
    PRICE_CACHE_TIER_2: float = 0.25

    # Cache Settings
    REPORT_PROMPT_CACHE_NAME: Optional[str] = None
    CACHE_TTL_DAYS: int = 2
    CACHE_DISPLAY_NAME: str = "ReportGenerationPromptsV2"
    # Use /tmp for Cloud Run compatibility
    CACHE_STATE_FILE: str = "/tmp/cache_state.json" 

    # DOCX Generation Settings
    DOCX_FONT_NAME: str = "Times New Roman"
    DOCX_FONT_SIZE_NORMAL: int = 12
    DOCX_FONT_SIZE_HEADING: int = 12
    DOCX_LINE_SPACING: float = 1.5
    DOCX_SPACE_AFTER_PARAGRAPH: int = 0

    # Logging
    LOG_LEVEL: str = "INFO"

    @property
    def MAX_FILE_SIZE_BYTES(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def MAX_TOTAL_UPLOAD_SIZE_BYTES(self) -> int:
        return self.MAX_TOTAL_UPLOAD_SIZE_MB * 1024 * 1024
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
