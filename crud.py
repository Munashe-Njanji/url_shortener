"""
CRUD operations for URL shortener.
Uses secure slug generation and proper validation.
Includes Redis caching for performance.
"""
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional
from datetime import datetime, timedelta, timezone
import models
import hashing
from url_validator import validate_url, normalize_url, get_url_hash
from config import settings
from redis_client import cache_get, cache_set, cache_delete, link_cache_key
import logging

logger = logging.getLogger(__name__)


def create_short_url(
    db: Session,
    target_url: str,
    custom_slug: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    max_retries: int = 3
) -> models.URL:
    """
    Create a new short URL with security validation.
    
    Args:
        db: Database session
        target_url: The long URL to shorten
        custom_slug: Optional custom slug (must be unique)
        expires_at: Optional expiration date
        max_retries: Maximum retries for slug collision (default: 3)
        
    Returns:
        Created URL model instance
        
    Raises:
        ValueError: If URL validation fails or custom slug is taken
        
    Security:
        - Validates URL to prevent SSRF attacks
        - Uses cryptographically secure random slugs
        - Normalizes URLs for deduplication
    """
    # Validate URL for security (SSRF prevention)
    is_valid, error_msg = validate_url(target_url, check_dns=settings.ENABLE_DNS_CHECK)
    if not is_valid:
        raise ValueError(f"Invalid URL: {error_msg}")
    
    # Normalize URL for consistency
    normalized_url = normalize_url(
        target_url,
        remove_tracking=settings.REMOVE_TRACKING_PARAMS,
        remove_fragment=True
    )
    
    # Generate URL hash for deduplication
    url_hash = get_url_hash(normalized_url)
    
    # Check for existing URL with same hash (deduplication)
    existing = db.query(models.URL).filter(models.URL.url_hash == url_hash).first()
    if existing and existing.active:
        # Return existing link instead of creating duplicate
        return existing
    
    # Validate and set expiration date
    if expires_at:
        if expiration_date <= datetime.utcnow():
            raise ValueError("Expiration date must be in the future")
        
        max_expiration = datetime.utcnow() + timedelta(days=settings.MAX_EXPIRATION_DAYS)
        if expiration_date > max_expiration:
            raise ValueError(
                f"Expiration date cannot exceed {settings.MAX_EXPIRATION_DAYS} days"
            )
    else:
        # Default expiration: 1 year from now
        expiration_date = datetime.now(timezone.utc) + timedelta(
            days=settings.MAX_EXPIRATION_DAYS
        )
    
    # Generate or validate slug
    if custom_slug:
        # Validate custom slug format
        if not hashing.validate_custom_slug(custom_slug):
            raise ValueError("Invalid custom slug format")
        
        # Check if custom slug is available
        existing_slug = db.query(models.URL).filter(models.URL.slug == custom_slug).first()
        if existing_slug:
            raise ValueError(f"Custom slug '{custom_slug}' is already taken")
        
        slug = custom_slug
    else:
        # Generate secure random slug with collision handling
        slug = None
        for attempt in range(max_retries):
            candidate_slug = hashing.generate_secure_slug(
                length=settings.DEFAULT_SLUG_LENGTH + attempt
            )
            
            # Check if slug is available
            existing_slug = db.query(models.URL).filter(
                models.URL.slug == candidate_slug
            ).first()
            
            if not existing_slug:
                slug = candidate_slug
                break
        
        if not slug:
            raise ValueError(
                f"Failed to generate unique slug after {max_retries} attempts"
            )
    
    # Create URL record
    db_url = models.URL(
        target_url=normalized_url,
        slug=slug,
        url_hash=url_hash,
        expires_at=expiration_date,
        active=True,
        created_at=datetime.utcnow()
    )
    
    try:
        db.add(db_url)
        db.commit()
        db.refresh(db_url)
        return db_url
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Database error: {str(e)}")


def get_url_by_short(db: Session, short_url: str, use_cache: bool = True) -> Optional[models.URL]:
    """
    Get URL by short slug with Redis caching.
    
    Args:
        db: Database session
        short_url: The short slug to look up
        use_cache: Whether to use Redis cache (default: True)
        
    Returns:
        URL model instance if found and valid, None otherwise
    """
    # Try cache first
    if use_cache:
        cache_key = link_cache_key(short_url)
        cached_data = cache_get(cache_key)
        
        if cached_data:
            logger.debug(f"Cache HIT for {short_url}")
            # Reconstruct URL object from cached data
            url = models.URL()
            for key, value in cached_data.items():
                if key == 'expiration_date' and value:
                    value = datetime.fromisoformat(value)
                elif key == 'created_at' and value:
                    value = datetime.fromisoformat(value)
                elif key == 'updated_at' and value:
                    value = datetime.fromisoformat(value)
                setattr(url, key, value)
            
            # Check if expired
            if url.expires_at and url.expires_at < datetime.utcnow():
                cache_delete(cache_key)
                return None
            
            return url
        
        logger.debug(f"Cache MISS for {short_url}")
    
    # Cache miss or cache disabled - query database
    url = db.query(models.URL).filter(
        models.URL.slug == short_url,
        models.URL.active == True
    ).first()
    
    if not url:
        return None
    
    # Check if expired
    if url.expires_at and url.expires_at < datetime.utcnow():
        return None
    
    # Cache the result
    if use_cache:
        cache_data = {
            'id': url.id,
            'target_url': url.target_url,
            'short_url': url.short_url,
            'url_hash': url.url_hash,
            'clicks': url.clicks,
            'active': url.active,
            'expiration_date': url.expires_at.isoformat() if url.expires_at else None,
            'created_at': url.created_at.isoformat() if url.created_at else None,
            'updated_at': url.updated_at.isoformat() if url.updated_at else None
        }
        cache_set(link_cache_key(short_url), cache_data)
    
    return url


def increment_clicks(db: Session, db_url: models.URL) -> models.URL:
    """
    Increment click count for a URL.
    
    Args:
        db: Database session
        db_url: URL model instance
        
    Returns:
        Updated URL model instance
    """
    db_url.clicks = db_url.clicks + 1
    db.commit()
    db.refresh(db_url)
    return db_url


def update_url(
    db: Session,
    url_id: int,
    target_url: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    active: Optional[bool] = None
) -> Optional[models.URL]:
    """
    Update an existing URL and invalidate cache.
    
    Args:
        db: Database session
        url_id: ID of the URL to update
        target_url: New target URL (optional)
        expires_at: New expiration date (optional)
        active: New active status (optional)
        
    Returns:
        Updated URL model instance if found, None otherwise
    """
    url = db.query(models.URL).filter(models.URL.id == url_id).first()
    if not url:
        return None
    
    if target_url is not None:
        # Validate new URL
        is_valid, error_msg = validate_url(target_url, check_dns=settings.ENABLE_DNS_CHECK)
        if not is_valid:
            raise ValueError(f"Invalid URL: {error_msg}")
        
        normalized_url = normalize_url(target_url)
        url.target_url = normalized_url
        url.url_hash = get_url_hash(normalized_url)
    
    if expires_at is not None:
        if expires_at <= datetime.utcnow():
            raise ValueError("Expiration date must be in the future")
        url.expires_at = expires_at
    
    if active is not None:
        url.active = active
    
    url.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(url)
    
    # Invalidate cache
    cache_delete(link_cache_key(url.short_url))
    logger.info(f"Cache invalidated for {url.short_url}")
    
    return url


def delete_url(db: Session, url_id: int) -> bool:
    """
    Soft delete a URL by marking it as inactive and invalidate cache.
    
    Args:
        db: Database session
        url_id: ID of the URL to delete
        
    Returns:
        True if deleted, False if not found
    """
    url = db.query(models.URL).filter(models.URL.id == url_id).first()
    if not url:
        return False
    
    url.active = False
    url.updated_at = datetime.utcnow()
    db.commit()
    
    # Invalidate cache
    cache_delete(link_cache_key(url.short_url))
    logger.info(f"Cache invalidated for deleted link {url.short_url}")
    
    return True
