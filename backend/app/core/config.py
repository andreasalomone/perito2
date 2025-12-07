from typing import Optional
from pydantic_settings import BaseSettings
import os

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
    # Service Account Email for Cloud Tasks (to verify OIDC token)
    CLOUD_TASKS_SA_EMAIL: Optional[str] = None
    
    # AI
    GEMINI_API_KEY: str
    
    # Local or Not
    ENVIRONMENT: str = "production" # "local", "production", "staging"
    RUN_LOCALLY: bool = False  # Default to False (Production)
    
    # CORS Settings
    # List of allowed origins for CORS
    BACKEND_CORS_ORIGINS: list[str] = [
        "https://perito.my", 
        "https://www.perito.my", 
        "https://api.perito.my",
        "https://perito-479708.firebaseapp.com",
        "http://localhost:3000",
        "https://perito.my/",
        "https://perito-479708.firebaseapp.com/",
        "https://api.perito.my/"
        
    ]
    # The URL of this backend service (for Cloud Tasks to target)
    BACKEND_URL: str = "https://api.perito.my"

    # Security
    # In production (Cloud Run), Firebase credentials are auto-detected via IAM.
    # For local dev, you might set GOOGLE_APPLICATION_CREDENTIALS env var.
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # --- Application Settings (Legacy Support) ---
    # File Processing
    MAX_FILE_SIZE_MB: int = 50
    MAX_TOTAL_UPLOAD_SIZE_MB: int = 200
    MAX_EXTRACTED_TEXT_LENGTH: int = 4000000

    
    # Map extensions to MIME types (Source of Truth for Uploads)
    ALLOWED_MIME_TYPES: dict = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".txt": "text/plain",
        ".eml": "message/rfc822",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    
    UPLOAD_FOLDER: str = "/tmp"

    # LLM Configuration
    LLM_MODEL_NAME: str = "gemini-2.5-pro" 
    LLM_FALLBACK_MODEL_NAME: str = "gemini-2.5-flash-lite"
    LLM_TEMPERATURE: float = 0.5
    LLM_MAX_TOKENS: int = 64000
    LLM_API_RETRY_ATTEMPTS: int = 2
    LLM_API_RETRY_WAIT_SECONDS: int = 2
    LLM_API_TIMEOUT_SECONDS: int = 600


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
    
    # Superadmin Access
    SUPERADMIN_EMAILS: str = ""  # Comma-separated list
    
    @property
    def SUPERADMIN_EMAIL_LIST(self) -> list[str]:
        """Parse superadmin emails into a list"""
        if not self.SUPERADMIN_EMAILS:
            return []
        return [email.strip() for email in self.SUPERADMIN_EMAILS.split(",")]
    
    @property
    def RESOLVED_BACKEND_URL(self) -> str:
        """
        Returns the backend URL, constructing it dynamically if needed.
        
        This prevents the "Ouroboros" bug where Cloud Tasks receive localhost URLs
        in production, causing 100% task failure.
        """
        # If explicitly set, use it. 
        # We prioritize this over K_SERVICE to avoid "Ouroboros" (self-discovery) issues
        # where Cloud Tasks cannot reach the internal K_SERVICE URL.
        if self.BACKEND_URL:
            return self.BACKEND_URL.rstrip("/")
        
        # For Cloud Run: construct URL from K_SERVICE environment variable
        # K_SERVICE is automatically set by Cloud Run to the service name
        if not self.RUN_LOCALLY and os.getenv("K_SERVICE"):
            service_name = os.getenv("K_SERVICE")
            # Cloud Run URL format: https://{service}-{project}.{region}.run.app
            return f"https://{service_name}-{self.GOOGLE_CLOUD_PROJECT}.{self.GOOGLE_CLOUD_REGION}.run.app"
        
        # Local development fallback
        return "http://localhost:8000"
    
    @property
    def CLOUD_RUN_AUDIENCE_URL(self) -> str:
        """
        Returns the Cloud Run-generated URL for OIDC token audience verification.
        
        IMPORTANT: When using custom domains with Cloud Tasks OIDC tokens, the audience
        MUST be the Cloud Run-generated URL (*.run.app), NOT the custom domain.
        Google Cloud Tasks sets the token audience to this URL, and verification must match.
        
        Reference: https://cloud.google.com/tasks/docs/creating-http-target-tasks#oidc_token
        """
        # Always use Cloud Run URL for audience, never the custom domain
        project_number = os.getenv("K_PROJECT_NUMBER", "738291935960")  # Fallback to known value
        service_name = os.getenv("K_SERVICE", "robotperizia-backend")
        
        # In development, allow local testing
        if self.RUN_LOCALLY:
            return "http://localhost:8000"
        
        # Cloud Run URL format: https://{service}-{project_number}.{region}.run.app
        return f"https://{service_name}-{project_number}.{self.GOOGLE_CLOUD_REGION}.run.app"

    @property
    def MAX_FILE_SIZE_BYTES(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def MAX_TOTAL_UPLOAD_SIZE_BYTES(self) -> int:
        return self.MAX_TOTAL_UPLOAD_SIZE_MB * 1024 * 1024
    
    @property
    def ASSETS_DIR(self) -> str:
        """
        Returns the absolute path to the assets directory.
        Prioritizes:
        1. /app/assets (Production/Container)
        2. {project_root}/assets (Local Development)
        """
        # 1. Container / Production Path
        container_assets = "/app/assets"
        if os.path.exists(container_assets):
            return container_assets
            
        # 2. Local Development Path
        # config.py is in backend/app/core/ -> .../backend/app/core/
        # We need to go up to 'perito' root.
        # current: backend/app/core
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # backend/app
        backend_app = os.path.dirname(current_dir)
        # backend
        backend_root = os.path.dirname(backend_app)
        # perito (project root)
        project_root = os.path.dirname(backend_root)
        
        local_assets = os.path.join(project_root, "assets")
        return local_assets
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
