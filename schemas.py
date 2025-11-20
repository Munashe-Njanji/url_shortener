"""
Pydantic schemas for request/response validation.
Provides comprehensive input validation and sanitization.
"""
from pydantic import BaseModel, validator, Field
from typing import Optional
from datetime import datetime
import re


class URLCreate(BaseModel):
    """Schema for creating a new short link."""
    
    target_url: str = Field(
        ...,
        description="The long URL to shorten",
        min_length=1,
        max_length=2048,
        example="https://example.com/very/long/url"
    )
    custom_slug: Optional[str] = Field(
        None,
        description="Custom slug (3-30 chars, alphanumeric and hyphens)",
        min_length=3,
        max_length=30,
        example="my-custom-link"
    )
    expiration_date: Optional[datetime] = Field(
        None,
        description="Optional expiration date for the link",
        example="2024-12-31T23:59:59Z"
    )
    
    @validator('target_url')
    def validate_target_url(cls, v):
        """Validate that target URL is not empty and properly formatted."""
        if not v or not v.strip():
            raise ValueError('Target URL cannot be empty')
        
        # Basic URL format check
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        
        return v.strip()
    
    @validator('custom_slug')
    def validate_custom_slug(cls, v):
        """Validate custom slug format."""
        if v is None:
            return v
        
        v = v.strip()
        
        # Check length
        if len(v) < 3 or len(v) > 30:
            raise ValueError('Custom slug must be between 3 and 30 characters')
        
        # Check format: alphanumeric and hyphens only
        if not re.match(r'^[a-zA-Z0-9-]+$', v):
            raise ValueError('Custom slug can only contain letters, numbers, and hyphens')
        
        # Cannot start or end with hyphen
        if v.startswith('-') or v.endswith('-'):
            raise ValueError('Custom slug cannot start or end with a hyphen')
        
        # Reserved slugs
        reserved = {'api', 'admin', 'docs', 'redoc', 'health', 'metrics', 'static'}
        if v.lower() in reserved:
            raise ValueError(f'Slug "{v}" is reserved and cannot be used')
        
        return v
    
    @validator('expiration_date')
    def validate_expiration_date(cls, v):
        """Validate that expiration date is in the future."""
        if v is None:
            return v
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
            if v <= datetime.now(timezone.utc):
                raise ValueError('Expiration date must be in the future')
        return v


class URLResponse(BaseModel):
    """Schema for short link response."""
    
    id: int
    target_url: str
    short_url: str
    slug: Optional[str] = None
    clicks: int
    expiration_date: Optional[datetime]
    created_at: datetime
    active: bool
    
    @validator('slug', always=True)
    def set_slug(cls, v, values):
        """Set slug to match short_url for backward compatibility."""
        return v or values.get('short_url')
    
    class Config:
        from_attributes = True


class URLUpdate(BaseModel):
    """Schema for updating an existing short link."""
    
    target_url: Optional[str] = Field(
        None,
        description="New target URL",
        min_length=1,
        max_length=2048
    )
    expiration_date: Optional[datetime] = Field(
        None,
        description="New expiration date"
    )
    active: Optional[bool] = Field(
        None,
        description="Whether the link is active"
    )
    
    @validator('target_url')
    def validate_target_url(cls, v):
        """Validate target URL if provided."""
        if v is None:
            return v
        # Make timezone-aware if naive (assume UTC)
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            v = v.replace(tzinfo=timezone.utc)
            if not v.strip():
                raise ValueError('Target URL cannot be empty')
            if not v.startswith(('http://', 'https://')):
                raise ValueError('URL must start with http:// or https://')
        return v


class ErrorResponse(BaseModel):
    """Schema for error responses."""
    
    error: dict = Field(
        ...,
        description="Error details",
        example={
            "code": "INVALID_URL",
            "message": "The provided URL is invalid",
            "details": {"reason": "URL resolves to private IP"}
        }
    )


class HealthCheckResponse(BaseModel):
    """Schema for health check response."""
    
    status: str = Field(..., description="Overall health status", example="healthy")
    checks: dict = Field(
        ...,
        description="Individual component health checks",
        example={
            "database": True,
            "redis": True,
            "celery": True
        }
    )


# Authentication Schemas

class UserCreate(BaseModel):
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    email_verified: bool
    tier: str
    created_at: datetime
    last_login_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
