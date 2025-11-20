"""FastAPI dependencies for authentication and authorization."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
import models
import auth_crud
from auth import extract_user_id_from_token
from database import get_db

# Security scheme for Bearer token
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> models.User:
    """
    Get current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer credentials
        db: Database session
        
    Returns:
        Current user model instance
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    try:
        user_id = extract_user_id_from_token(credentials.credentials)
        user = auth_crud.get_user_by_id(db, user_id)
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if account is locked
        if auth_crud.is_user_account_locked(db, user.id):
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account is locked due to too many failed login attempts",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_verified_user(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """
    Get current authenticated user with verified email.
    
    Args:
        current_user: Current user from get_current_user
        
    Returns:
        Current user model instance
        
    Raises:
        HTTPException: If user email is not verified
    """
    if not current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email address."
        )
    
    return current_user


def get_current_active_user(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """
    Get current active user (not locked).
    
    Args:
        current_user: Current user from get_current_user
        
    Returns:
        Current user model instance
        
    Note:
        Account locking is already checked in get_current_user,
        so this is just an alias for consistency.
    """
    return current_user


def require_tier(required_tier: str):
    """
    Create a dependency that requires a specific user tier.
    
    Args:
        required_tier: Required tier (free, pro, teams, enterprise)
        
    Returns:
        Dependency function
    """
    tier_hierarchy = {
        'free': 0,
        'pro': 1,
        'teams': 2,
        'enterprise': 3
    }
    
    def check_tier(current_user: models.User = Depends(get_current_user)) -> models.User:
        user_tier_level = tier_hierarchy.get(current_user.tier, 0)
        required_tier_level = tier_hierarchy.get(required_tier, 0)
        
        if user_tier_level < required_tier_level:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"This feature requires {required_tier} tier or higher. Current tier: {current_user.tier}"
            )
        
        return current_user
    
    return check_tier


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[models.User]:
    """
    Get current user if authenticated, None otherwise.
    Useful for endpoints that work for both authenticated and anonymous users.
    
    Args:
        credentials: Optional HTTP Bearer credentials
        db: Database session
        
    Returns:
        Current user model instance if authenticated, None otherwise
    """
    if not credentials:
        return None
    
    try:
        user_id = extract_user_id_from_token(credentials.credentials)
        user = auth_crud.get_user_by_id(db, user_id)
        
        # Check if account is locked
        if user and auth_crud.is_user_account_locked(db, user.id):
            return None
        
        return user
    
    except Exception:
        return None


# Tier-specific dependencies
require_pro = require_tier('pro')
require_teams = require_tier('teams')
require_enterprise = require_tier('enterprise')
