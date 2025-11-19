"""
Token bucket rate limiter using Redis.
"""
import time
from typing import Tuple
from redis_client import get_redis_client, rate_limit_key
import logging

logger = logging.getLogger(__name__)

# Lua script for atomic token bucket operation
TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or max_tokens
local last_refill = tonumber(bucket[2]) or now

local elapsed = now - last_refill
tokens = math.min(max_tokens, tokens + elapsed * refill_rate)

if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 3600)
    return {1, math.floor(tokens)}
else
    return {0, math.floor(tokens)}
end
"""


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self):
        self.redis = get_redis_client()
        self.script = None
        if self.redis:
            try:
                self.script = self.redis.register_script(TOKEN_BUCKET_SCRIPT)
            except Exception as e:
                logger.error(f"Failed to register rate limit script: {e}")
    
    def check_rate_limit(
        self,
        identifier: str,
        max_tokens: int,
        refill_rate: float,
        endpoint: str = "api",
        requested: int = 1
    ) -> Tuple[bool, int, int]:
        """
        Check if request is allowed under rate limit.
        
        Args:
            identifier: Unique identifier (IP, user ID, etc.)
            max_tokens: Maximum tokens in bucket
            refill_rate: Tokens added per second
            endpoint: Endpoint name for key namespacing
            requested: Number of tokens requested (default: 1)
            
        Returns:
            Tuple of (allowed, remaining_tokens, reset_time)
        """
        if not self.redis or not self.script:
            # If Redis is not available, allow the request
            logger.warning("Rate limiting disabled (Redis unavailable)")
            return True, max_tokens, 0
        
        try:
            key = rate_limit_key(identifier, endpoint)
            now = time.time()
            
            # Execute Lua script
            result = self.script(
                keys=[key],
                args=[max_tokens, refill_rate, now, requested]
            )
            
            allowed = bool(result[0])
            remaining = int(result[1])
            
            # Calculate reset time (when bucket will be full)
            if remaining < max_tokens:
                tokens_needed = max_tokens - remaining
                reset_time = int(now + (tokens_needed / refill_rate))
            else:
                reset_time = int(now)
            
            return allowed, remaining, reset_time
        
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # On error, allow the request
            return True, max_tokens, 0


# Global rate limiter instance
rate_limiter = RateLimiter()


def check_rate_limit_ip(ip: str, max_per_minute: int = 100) -> Tuple[bool, int, int]:
    """
    Check rate limit for an IP address.
    
    Args:
        ip: IP address
        max_per_minute: Maximum requests per minute
        
    Returns:
        Tuple of (allowed, remaining, reset_time)
    """
    refill_rate = max_per_minute / 60.0  # tokens per second
    return rate_limiter.check_rate_limit(
        identifier=ip,
        max_tokens=max_per_minute,
        refill_rate=refill_rate,
        endpoint="redirect"
    )


def check_rate_limit_user(user_id: int, tier: str = "free") -> Tuple[bool, int, int]:
    """
    Check rate limit for a user based on their tier.
    
    Args:
        user_id: User ID
        tier: User tier (free, pro, enterprise)
        
    Returns:
        Tuple of (allowed, remaining, reset_time)
    """
    from config import settings
    
    # Get limits based on tier
    limits = {
        "free": settings.RATE_LIMIT_API_FREE_PER_HOUR,
        "pro": settings.RATE_LIMIT_API_PRO_PER_HOUR,
        "enterprise": settings.RATE_LIMIT_API_ENTERPRISE_PER_HOUR
    }
    
    max_per_hour = limits.get(tier, limits["free"])
    refill_rate = max_per_hour / 3600.0  # tokens per second
    
    return rate_limiter.check_rate_limit(
        identifier=str(user_id),
        max_tokens=max_per_hour,
        refill_rate=refill_rate,
        endpoint="api"
    )
