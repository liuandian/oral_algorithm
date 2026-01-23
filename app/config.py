"""
System Configuration Management
Based on environment variables
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """System Configuration"""

    # ========================================
    # Application Basic Configuration
    # ========================================
    APP_NAME: str = "Oral Health Monitoring System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # ========================================
    # Database Configuration (PostgreSQL)
    # ========================================
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgre"
    DB_PASSWORD: str = "postgre"
    DB_NAME: str = "oral_health_db"

    @property
    def DATABASE_URL(self) -> str:
        """Generate database connection URL"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def DATABASE_URL_ASYNC(self) -> str:
        """Generate async database connection URL"""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # ========================================
    # File Storage Configuration
    # ========================================
    # Project root directory
    BASE_DIR: Path = Path(__file__).parent.parent

    # Data storage root directory
    DATA_ROOT: Optional[str] = None

    @property
    def DATA_ROOT_PATH(self) -> Path:
        """Data storage root path"""
        if self.DATA_ROOT:
            return Path(self.DATA_ROOT)
        return self.BASE_DIR / "data"

    @property
    def B_STREAM_PATH(self) -> Path:
        """B stream (raw videos) storage path"""
        return self.DATA_ROOT_PATH / "b_stream"

    @property
    def A_STREAM_PATH(self) -> Path:
        """A stream (keyframes) storage path"""
        return self.DATA_ROOT_PATH / "a_stream"

    @property
    def C_STREAM_PATH(self) -> Path:
        """C stream (training data) storage path"""
        return self.DATA_ROOT_PATH / "c_stream"

    # ========================================
    # Video Processing Configuration
    # ========================================
    MAX_VIDEO_SIZE_MB: int = 100  # Max video size (MB)
    MAX_VIDEO_DURATION_SEC: int = 30  # Max video duration (seconds)
    MAX_KEYFRAMES: int = 25  # Max keyframe count
    MIN_KEYFRAMES: int = 5  # Min keyframe count

    # Keyframe extraction strategy configuration
    UNIFORM_SAMPLE_COUNT: int = 20  # Uniform sampling candidate count
    PRIORITY_FRAME_THRESHOLD: float = 0.5  # Priority frame anomaly threshold (0-1)

    # Image quality configuration
    KEYFRAME_QUALITY: int = 85  # JPEG quality (0-100)
    THUMBNAIL_SIZE: tuple = (320, 240)  # Thumbnail size

    # ========================================
    # Qianwen API Configuration
    # ========================================
    QIANWEN_API_KEY: str = ""
    QIANWEN_VISION_MODEL: str = "qwen-vl-max"  # Vision model
    QIANWEN_TEXT_MODEL: str = "qwen-max"  # Text model
    QIANWEN_API_BASE: str = "https://dashscope.aliyuncs.com/api/v1"

    # API timeout configuration
    QIANWEN_TIMEOUT: int = 30  # Request timeout (seconds)
    QIANWEN_MAX_RETRIES: int = 3  # Max retry count

    # ========================================
    # Security Configuration
    # ========================================
    # JWT configuration (simplified version for basic auth)
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # CORS configuration
    CORS_ORIGINS: list = ["*"]  # Should limit to specific domains in production

    # ========================================
    # Logging Configuration
    # ========================================
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_FILE: Optional[str] = None  # Log file path (None = console only)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# ========================================
# Global Configuration Instance
# ========================================
settings = Settings()


# ========================================
# Initialization Functions
# ========================================
def ensure_directories():
    """Ensure all necessary directories exist"""
    directories = [
        settings.B_STREAM_PATH,
        settings.A_STREAM_PATH,
        settings.C_STREAM_PATH,
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"[Config] Directory ready: {directory}")


def validate_config():
    """Validate critical configuration items"""
    errors = []

    # Check database configuration
    if not settings.DB_NAME:
        errors.append("Database name not configured (DB_NAME)")

    # Check Qianwen API configuration
    if not settings.QIANWEN_API_KEY:
        errors.append("Qianwen API Key not configured (QIANWEN_API_KEY)")
    elif settings.QIANWEN_API_KEY == "your-api-key-here":
        errors.append("Please change Qianwen API Key (do not use default value)")

    # Check JWT secret key
    if settings.JWT_SECRET_KEY == "your-secret-key-change-in-production":
        print("[Warning] JWT secret key using default value, MUST change in production!")

    if errors:
        print("\n[Config Error] The following configuration items need correction:")
        for error in errors:
            print(f"  - {error}")
        raise ValueError("Configuration validation failed")

    print("[Config] Validation passed")


# ========================================
# Auto-execute on startup
# ========================================
if __name__ == "__main__":
    print("=" * 60)
    print(f"{settings.APP_NAME} v{settings.APP_VERSION}")
    print("=" * 60)
    print(f"Database: {settings.DATABASE_URL}")
    print(f"Data root directory: {settings.DATA_ROOT_PATH}")
    print(f"B stream path: {settings.B_STREAM_PATH}")
    print(f"A stream path: {settings.A_STREAM_PATH}")
    print(f"C stream path: {settings.C_STREAM_PATH}")
    print("=" * 60)

    ensure_directories()
    validate_config()
