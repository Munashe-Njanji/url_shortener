"""
Main FastAPI application with security hardening.
Implements proper error handling, validation, and CORS.
"""
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import logging
import uuid
import time

import models
import crud
import auth_crud
import database
import schemas
from auth import create_access_token, create_refresh_token, verify_token, is_token_expired
from dependencies import get_current_user, get_current_verified_user, get_optional_user
from config import settings
from rate_limiter import check_rate_limit_ip
from redis_client import get_redis_client

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize database
database.init_db()

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-grade URL shortening service with security and analytics",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    max_age=3600
)

# Authentication routes are defined inline below


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Request ID middleware for tracing
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID for tracing."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Custom exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with user-friendly messages."""
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"] if loc != "body")
        message = error["msg"]
        error_type = error["type"]
        
        # Provide more user-friendly messages
        if "missing" in error_type:
            user_message = f"Required field '{field}' is missing"
        elif "type_error" in error_type:
            user_message = f"Invalid type for field '{field}': {message}"
        elif "value_error" in error_type:
            user_message = f"Invalid value for field '{field}': {message}"
        else:
            user_message = f"Validation error in field '{field}': {message}"
        
        errors.append({
            "field": field,
            "message": user_message,
            "type": error_type
        })
    
    logger.warning(f"Validation error: {errors}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request contains invalid data. Please check the errors below.",
                "errors": errors,
                "request_id": getattr(request.state, "request_id", None)
            }
        }
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError exceptions with proper error response."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": "INVALID_INPUT",
                "message": str(exc),
                "request_id": getattr(request.state, "request_id", None)
            }
        }
    )


@app.exception_handler(TypeError)
async def type_error_handler(request: Request, exc: TypeError):
    """Handle TypeError exceptions (often from validation issues)."""
    error_msg = str(exc)
    
    # Provide user-friendly messages for common type errors
    if "datetime" in error_msg.lower():
        user_message = "Invalid date format. Please provide a valid ISO 8601 datetime (e.g., 2024-12-31T23:59:59Z)"
    else:
        user_message = "Invalid data type provided. Please check your request format."
    
    logger.warning(f"Type error: {error_msg}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": "INVALID_DATA_TYPE",
                "message": user_message,
                "details": error_msg if settings.DEBUG else None,
                "request_id": getattr(request.state, "request_id", None)
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    
    # Provide more helpful error messages in development
    error_details = {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred. Please try again or contact support if the problem persists.",
            "request_id": getattr(request.state, "request_id", None)
        }
    }
    
    # Include exception details in debug mode
    if settings.DEBUG:
        error_details["error"]["debug_info"] = {
            "exception_type": type(exc).__name__,
            "exception_message": str(exc)
        }
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_details
    )


# Health check endpoint
@app.get("/health", response_model=schemas.HealthCheckResponse, tags=["System"])
async def health_check(db: Session = Depends(database.get_db)):
    """
    Health check endpoint for monitoring.
    Checks database, Redis connectivity and returns system status.
    """
    checks = {}
    
    # Check database
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        checks["database"] = False
    
    # Check Redis
    try:
        redis = get_redis_client()
        if redis:
            redis.ping()
            checks["redis"] = True
        else:
            checks["redis"] = False
    except Exception as e:
        logger.error(f"Redis health check failed: {str(e)}")
        checks["redis"] = False
    
    # Overall status
    all_healthy = all(checks.values())
    status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if all_healthy else "unhealthy",
            "checks": checks
        }
    )


# Authentication endpoints
@app.post(
    "/api/v1/auth/register",
    response_model=schemas.TokenResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
    summary="Register a new user"
)
async def register(
    user_data: schemas.UserCreate,
    db: Session = Depends(database.get_db)
):
    """Register a new user account."""
    try:
        user = auth_crud.create_user(db, user_data)
        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})
        
        logger.info(f"User registered: {user.email} (ID: {user.id})")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": user
        }
    except ValueError as e:
        logger.warning(f"Registration failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post(
    "/api/v1/auth/login",
    response_model=schemas.TokenResponse,
    tags=["Authentication"],
    summary="Login user"
)
async def login(
    user_data: schemas.UserLogin,
    db: Session = Depends(database.get_db)
):
    """Authenticate user and return JWT tokens."""
    user = auth_crud.authenticate_user(db, user_data.email, user_data.password)
    
    if not user:
        logger.warning(f"Failed login attempt for: {user_data.email}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    
    if auth_crud.is_user_account_locked(db, user.id):
        logger.warning(f"Login attempt on locked account: {user.email}")
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Account is locked")
    
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    logger.info(f"User logged in: {user.email} (ID: {user.id})")
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user
    }


@app.post(
    "/api/v1/auth/refresh",
    response_model=schemas.TokenResponse,
    tags=["Authentication"],
    summary="Refresh access token"
)
async def refresh_token(
    refresh_data: schemas.RefreshTokenRequest,
    db: Session = Depends(database.get_db)
):
    """
    Refresh access token using refresh token.
    
    Returns new access and refresh tokens.
    """
    try:
        # Verify refresh token
        payload = verify_token(refresh_data.refresh_token)
        
        # Check if it's a refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        # Get user
        user_id = int(payload.get("sub"))
        user = auth_crud.get_user_by_id(db, user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Check if account is locked
        if auth_crud.is_user_account_locked(db, user.id):
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account is locked"
            )
        
        # Create new tokens
        access_token = create_access_token(data={"sub": str(user.id)})
        new_refresh_token = create_refresh_token(data={"sub": str(user.id)})
        
        logger.info(f"Token refreshed for user: {user.email} (ID: {user.id})")
        
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": user
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate refresh token"
        )


@app.get(
    "/api/v1/auth/me",
    response_model=schemas.UserResponse,
    tags=["Authentication"],
    summary="Get current user info"
)
async def get_current_user_info(
    current_user: models.User = Depends(get_current_user)
):
    """Get current authenticated user information."""
    return current_user


# API endpoints
@app.post(
    "/shorten/",
    response_model=schemas.URLResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Links"],
    summary="Create a short link",
    responses={
        201: {"description": "Link created successfully"},
        400: {"description": "Invalid URL or parameters"},
        409: {"description": "Custom slug already taken"}
    }
)
async def shorten_url(
    url_data: schemas.URLCreate,
    db: Session = Depends(database.get_db)
):
    """
    Create a new short link.
    
    - **target_url**: The long URL to shorten (required)
    - **custom_slug**: Custom slug (3-30 chars, optional)
    - **expiration_date**: Expiration date (optional)
    
    Security features:
    - URL validation to prevent SSRF attacks
    - Cryptographically secure slug generation
    - URL normalization for deduplication
    """
    try:
        db_url = crud.create_short_url(
            db,
            target_url=url_data.target_url,
            custom_slug=url_data.custom_slug,
            expires_at=url_data.expiration_date
        )
        
        logger.info(f"Created short link: {db_url.short_url} -> {db_url.target_url}")
        
        return db_url
    
    except ValueError as e:
        logger.warning(f"Failed to create link: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@app.get(
    "/{short_url}",
    tags=["Redirect"],
    summary="Redirect to target URL",
    responses={
        302: {"description": "Redirect to target URL"},
        404: {"description": "Link not found"},
        410: {"description": "Link expired or deleted"},
        429: {"description": "Rate limit exceeded"}
    }
)
async def redirect_to_target(
    short_url: str,
    request: Request,
    db: Session = Depends(database.get_db)
):
    """
    Redirect to the target URL for a given short link.
    
    This endpoint is optimized for performance:
    - Redis caching for fast lookups
    - Rate limiting per IP
    - Minimal processing on redirect path
    - Click tracking happens asynchronously (future enhancement)
    """
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    
    # Check rate limit
    allowed, remaining, reset_time = check_rate_limit_ip(client_ip)
    if not allowed:
        logger.warning(f"Rate limit exceeded for IP {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
            headers={
                "X-RateLimit-Limit": str(settings.RATE_LIMIT_REDIRECT_PER_MINUTE),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_time),
                "Retry-After": str(max(0, reset_time - int(time.time())))
            }
        )
    
    # Validate slug format to prevent injection
    if not short_url or len(short_url) > 30:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid short URL format"
        )
    
    # Get URL from cache/database
    db_url = crud.get_url_by_short(db, short_url, use_cache=True)
    
    if db_url is None:
        logger.info(f"Short URL not found or expired: {short_url}")
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="URL not found or has expired"
        )
    
    # Increment click count (synchronous for now, will be async in future)
    try:
        crud.increment_clicks(db, db_url)
    except Exception as e:
        # Don't fail redirect if click tracking fails
        logger.error(f"Failed to increment clicks: {str(e)}")
    
    logger.info(f"Redirecting {short_url} -> {db_url.target_url}")
    
    # Return redirect response with rate limit headers
    response = RedirectResponse(
        url=str(db_url.target_url),
        status_code=status.HTTP_302_FOUND
    )
    response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_REDIRECT_PER_MINUTE)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset_time)
    
    return response


@app.get(
    "/api/v1/links/{short_url}",
    response_model=schemas.URLResponse,
    tags=["Links"],
    summary="Get link details"
)
async def get_link_details(
    short_url: str,
    db: Session = Depends(database.get_db)
):
    """
    Get details about a short link without redirecting.
    """
    db_url = crud.get_url_by_short(db, short_url)
    
    if db_url is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found"
        )
    
    return db_url


@app.put(
    "/api/v1/links/{short_url}",
    response_model=schemas.URLResponse,
    tags=["Links"],
    summary="Update link"
)
async def update_link(
    short_url: str,
    update_data: schemas.URLUpdate,
    db: Session = Depends(database.get_db)
):
    """
    Update an existing short link.
    """
    # Get existing link
    db_url = crud.get_url_by_short(db, short_url)
    if db_url is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found"
        )
    
    # Update link
    try:
        updated_url = crud.update_url(
            db,
            url_id=db_url.id,
            target_url=update_data.target_url,
            expires_at=update_data.expiration_date,
            active=update_data.active
        )
        
        logger.info(f"Updated link: {short_url}")
        return updated_url
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@app.delete(
    "/api/v1/links/{short_url}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Links"],
    summary="Delete link"
)
async def delete_link(
    short_url: str,
    db: Session = Depends(database.get_db)
):
    """
    Delete (deactivate) a short link.
    """
    # Get existing link
    db_url = crud.get_url_by_short(db, short_url)
    if db_url is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link not found"
        )
    
    # Delete link (soft delete)
    success = crud.delete_url(db, db_url.id)
    
    if success:
        logger.info(f"Deleted link: {short_url}")
        return None
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete link"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )