"""
Secure slug generation module.
Uses cryptographically secure random generation instead of predictable MD5 hashing.
"""
import secrets
import string

# Alphanumeric characters for slug generation (62 characters: a-z, A-Z, 0-9)
SLUG_ALPHABET = string.ascii_letters + string.digits
DEFAULT_SLUG_LENGTH = 7  # 62^7 = 3.5 trillion combinations


def generate_secure_slug(length: int = DEFAULT_SLUG_LENGTH) -> str:
    """
    Generate a cryptographically secure random slug.
    
    Args:
        length: Length of the slug (default: 7 characters)
        
    Returns:
        A random alphanumeric string of specified length
        
    Security:
        Uses secrets module for cryptographic randomness to prevent
        enumeration attacks and ensure unpredictability.
    """
    return ''.join(secrets.choice(SLUG_ALPHABET) for _ in range(length))


def validate_custom_slug(slug: str) -> bool:
    """
    Validate a custom slug provided by the user.
    
    Args:
        slug: The custom slug to validate
        
    Returns:
        True if valid, False otherwise
        
    Rules:
        - 3-30 characters
        - Alphanumeric and hyphens only
        - Cannot start or end with hyphen
    """
    if not slug or len(slug) < 3 or len(slug) > 30:
        return False
    
    if slug.startswith('-') or slug.endswith('-'):
        return False
    
    # Check if all characters are alphanumeric or hyphen
    allowed_chars = set(SLUG_ALPHABET + '-')
    return all(c in allowed_chars for c in slug)
