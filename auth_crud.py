"""CRUD operations for authentication and user management."""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional
from datetime import datetime, timedelta
import models
from auth import hash_password, verify_password, validate_password_strength
from schemas import UserCreate


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    """
    Get user by email address.
    
    Args:
        db: Database session
        email: User email address
        
    Returns:
        User model instance if found, None otherwise
    """
    return db.query(models.User).filter(models.User.email == email.lower()).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    """
    Get user by ID.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        User model instance if found, None otherwise
    """
    return db.query(models.User).filter(models.User.id == user_id).first()


def create_user(db: Session, user: UserCreate) -> models.User:
    """
    Create a new user.
    
    Args:
        db: Database session
        user: User creation data
        
    Returns:
        Created user model instance
        
    Raises:
        ValueError: If email already exists or password is weak
    """
    # Check if user already exists
    existing_user = get_user_by_email(db, user.email)
    if existing_user:
        raise ValueError("Email already registered")
    
    # Validate password strength
    is_valid, error_msg = validate_password_strength(user.password)
    if not is_valid:
        raise ValueError(error_msg)
    
    # Hash password
    hashed_password = hash_password(user.password)
    
    # Create user
    db_user = models.User(
        email=user.email.lower(),
        password_hash=hashed_password,
        email_verified=False,
        tier='free',
        created_at=datetime.utcnow()
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, email: str, password: str) -> Optional[models.User]:
    """
    Authenticate a user with email and password.
    
    Args:
        db: Database session
        email: User email
        password: Plain text password
        
    Returns:
        User model instance if authentication successful, None otherwise
    """
    user = get_user_by_email(db, email)
    if not user:
        return None
    
    # Check if account is locked
    if user.account_locked_until and user.account_locked_until > datetime.utcnow():
        return None
    
    # Verify password
    if not verify_password(password, user.password_hash):
        # Increment failed login attempts
        user.failed_login_attempts += 1
        
        # Lock account after 5 failed attempts
        if user.failed_login_attempts >= 5:
            user.account_locked_until = datetime.utcnow() + timedelta(minutes=30)
        
        db.commit()
        return None
    
    # Reset failed login attempts on successful login
    user.failed_login_attempts = 0
    user.account_locked_until = None
    user.last_login_at = datetime.utcnow()
    db.commit()
    
    return user


def update_user_password(db: Session, user_id: int, current_password: str, new_password: str) -> bool:
    """
    Update user password.
    
    Args:
        db: Database session
        user_id: User ID
        current_password: Current password for verification
        new_password: New password
        
    Returns:
        True if password updated successfully, False otherwise
        
    Raises:
        ValueError: If current password is wrong or new password is weak
    """
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    
    # Verify current password
    if not verify_password(current_password, user.password_hash):
        raise ValueError("Current password is incorrect")
    
    # Validate new password strength
    is_valid, error_msg = validate_password_strength(new_password)
    if not is_valid:
        raise ValueError(error_msg)
    
    # Update password
    user.password_hash = hash_password(new_password)
    user.updated_at = datetime.utcnow()
    db.commit()
    
    return True


def verify_user_email(db: Session, user_id: int) -> bool:
    """
    Mark user email as verified.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        True if email verified successfully, False if user not found
    """
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    
    user.email_verified = True
    user.updated_at = datetime.utcnow()
    db.commit()
    
    return True


def is_user_account_locked(db: Session, user_id: int) -> bool:
    """
    Check if user account is locked.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        True if account is locked, False otherwise
    """
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    
    if user.account_locked_until and user.account_locked_until > datetime.utcnow():
        return True
    
    return False


def unlock_user_account(db: Session, user_id: int) -> bool:
    """
    Unlock user account (admin function).
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        True if account unlocked successfully, False if user not found
    """
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    
    user.failed_login_attempts = 0
    user.account_locked_until = None
    user.updated_at = datetime.utcnow()
    db.commit()
    
    return True


def update_user_tier(db: Session, user_id: int, tier: str) -> bool:
    """
    Update user tier (admin function).
    
    Args:
        db: Database session
        user_id: User ID
        tier: New tier (free, pro, teams, enterprise)
        
    Returns:
        True if tier updated successfully, False if user not found
    """
    valid_tiers = ['free', 'pro', 'teams', 'enterprise']
    if tier not in valid_tiers:
        raise ValueError(f"Invalid tier. Must be one of: {', '.join(valid_tiers)}")
    
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    
    user.tier = tier
    user.updated_at = datetime.utcnow()
    db.commit()
    
    return True
