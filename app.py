"""
Main FastAPI application with security hardening.
Implements proper error handling, validation, and CORS.
"""
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import logging
import uuid
import time

import models
import crud
import database
import schemas
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


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "request_id": getattr(request.state, "request_id", None)
            }
        }
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