"""
Configuration management using environment variables.
All secrets and configuration should be loaded from environment, not hardcoded.
"""
import os
from typing import Optional
from pydantic import BaseSettings, validator


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    
    # Application
    APP_NAME: str = "URL Shortener"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development, staging, production
    
    # Database
    DATABASE_URL: str = "sqlite:///./url_shortener.db"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 3600
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600  # 1 hour
    
    # Security
    SECRET_KEY: str = "change-this-to-a-secure-random-key-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Password hashing
    BCRYPT_ROUNDS: int = 12
    
    # Rate Limiting
    RATE_LIMIT_REDIRECT_PER_MINUTE: int = 100
    RATE_LIMIT_API_FREE_PER_HOUR: int = 100
    RATE_LIMIT_API_PRO_PER_HOUR: int = 1000
    RATE_LIMIT_API_ENTERPRISE_PER_HOUR: int = 10000
    
    # Link settings
    DEFAULT_SLUG_LENGTH: int = 7
    MAX_SLUG_LENGTH: int = 30
    MIN_SLUG_LENGTH: int = 3
    MAX_EXPIRATION_DAYS: int = 365
    
    # URL validation
    MAX_URL_LENGTH: int = 2048
    ENABLE_DNS_CHECK: bool = True
    REMOVE_TRACKING_PARAMS: bool = False
    
    # CORS
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000"]
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    
    # Object Storage (S3)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: Optional[str] = None
    
    # Analytics
    CLICKHOUSE_HOST: Optional[str] = None
    CLICKHOUSE_PORT: int = 9000
    CLICKHOUSE_DATABASE: str = "url_shortener"
    
    # Monitoring
    SENTRY_DSN: Optional[str] = None
    ENABLE_METRICS: bool = True
    
    # Stripe
    STRIPE_API_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    
    @validator("SECRET_KEY")
    def validate_secret_key(cls, v, values):
        """Warn if using default secret key in production."""
        if values.get("ENVIRONMENT") == "production" and v == "change-this-to-a-secure-random-key-in-production":
            raise ValueError("SECRET_KEY must be changed in production environment")
        return v
    
    @validator("DATABASE_URL")
    def validate_database_url(cls, v, values):
        """Warn if using SQLite in production."""
        if values.get("ENVIRONMENT") == "production" and v.startswith("sqlite"):
            raise ValueError("SQLite should not be used in production. Use PostgreSQL instead.")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get the global settings instance.
    Useful for dependency injection in FastAPI.
    """
    return settings
