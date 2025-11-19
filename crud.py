"""
CRUD operations for URL shortener.
Uses secure slug generation and proper validation.
"""
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional
from datetime import datetime, timedelta, timezone
import models
import hashing
from url_validator import validate_url, normalize_url, get_url_hash
from config import settings


def create_short_url(
    db: Session,
    target_url: str,
    custom_slug: Optional[str] = None,
    expiration_date: Optional[datetime] = None,
    max_retries: int = 3
) -> models.URL:
    """
    Create a new short URL with security validation.
    
    Args:
        db: Database session
        target_url: The long URL to shorten
        custom_slug: Optional custom slug (must be unique)
        expiration_date: Optional expiration date
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
    if expiration_date:
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
        existing_slug = db.query(models.URL).filter(models.URL.short_url == custom_slug).first()
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
                models.URL.short_url == candidate_slug
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
        short_url=slug,
        url_hash=url_hash,
        expiration_date=expiration_date,
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


def get_url_by_short(db: Session, short_url: str) -> Optional[models.URL]:
    """
    Get URL by short slug, checking expiration and active status.
    
    Args:
        db: Database session
        short_url: The short slug to look up
        
    Returns:
        URL model instance if found and valid, None otherwise
    """
    url = db.query(models.URL).filter(
        models.URL.short_url == short_url,
        models.URL.active == True
    ).first()
    
    if not url:
        return None
    
    # Check if expired
    if url.expiration_date and url.expiration_date < datetime.utcnow():
        return None
    
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
    expiration_date: Optional[datetime] = None,
    active: Optional[bool] = None
) -> Optional[models.URL]:
    """
    Update an existing URL.
    
    Args:
        db: Database session
        url_id: ID of the URL to update
        target_url: New target URL (optional)
        expiration_date: New expiration date (optional)
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
    
    if expiration_date is not None:
        if expiration_date <= datetime.utcnow():
            raise ValueError("Expiration date must be in the future")
        url.expiration_date = expiration_date
    
    if active is not None:
        url.active = active
    
    url.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(url)
    return url


def delete_url(db: Session, url_id: int) -> bool:
    """
    Soft delete a URL by marking it as inactive.
    
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
    return True
