"""
Redis client and helper functions for caching and rate limiting.
"""
import redis
import json
from typing import Optional, Any
from config import settings
import logging

logger = logging.getLogger(__name__)

# Redis connection pool
redis_pool = None
redis_client = None


def get_redis_client() -> redis.Redis:
    """
    Get Redis client with connection pooling.
    Creates connection pool on first call.
    """
    global redis_pool, redis_client
    
    if redis_client is None:
        try:
            redis_pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                max_connections=50
            )
            redis_client = redis.Redis(connection_pool=redis_pool)
            
            # Test connection
            redis_client.ping()
            logger.info(f"Redis connected: {settings.REDIS_URL}")
        
        except redis.ConnectionError as e:
            logger.warning(f"Redis connection failed: {e}. Caching disabled.")
            redis_client = None
    
    return redis_client


def cache_get(key: str) -> Optional[Any]:
    """
    Get value from Redis cache.
    
    Args:
        key: Cache key
        
    Returns:
        Cached value (deserialized from JSON) or None
    """
    client = get_redis_client()
    if not client:
        return None
    
    try:
        value = client.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception as e:
        logger.error(f"Redis GET error for key {key}: {e}")
        return None


def cache_set(key: str, value: Any, ttl: int = None) -> bool:
    """
    Set value in Redis cache.
    
    Args:
        key: Cache key
        value: Value to cache (will be JSON serialized)
        ttl: Time to live in seconds (default: from settings)
        
    Returns:
        True if successful, False otherwise
    """
    client = get_redis_client()
    if not client:
        return False
    
    try:
        ttl = ttl or settings.REDIS_CACHE_TTL
        serialized = json.dumps(value)
        client.setex(key, ttl, serialized)
        return True
    except Exception as e:
        logger.error(f"Redis SET error for key {key}: {e}")
        return False


def cache_delete(key: str) -> bool:
    """
    Delete key from Redis cache.
    
    Args:
        key: Cache key to delete
        
    Returns:
        True if successful, False otherwise
    """
    client = get_redis_client()
    if not client:
        return False
    
    try:
        client.delete(key)
        return True
    except Exception as e:
        logger.error(f"Redis DELETE error for key {key}: {e}")
        return False


def cache_invalidate_pattern(pattern: str) -> int:
    """
    Delete all keys matching a pattern.
    
    Args:
        pattern: Pattern to match (e.g., "link:*")
        
    Returns:
        Number of keys deleted
    """
    client = get_redis_client()
    if not client:
        return 0
    
    try:
        keys = client.keys(pattern)
        if keys:
            return client.delete(*keys)
        return 0
    except Exception as e:
        logger.error(f"Redis pattern delete error for {pattern}: {e}")
        return 0


# Key naming conventions
def link_cache_key(slug: str) -> str:
    """Generate cache key for a link."""
    return f"link:{slug}"


def user_cache_key(user_id: int) -> str:
    """Generate cache key for a user."""
    return f"user:{user_id}"


def rate_limit_key(identifier: str, endpoint: str = "api") -> str:
    """Generate rate limit key."""
    return f"ratelimit:{endpoint}:{identifier}"
