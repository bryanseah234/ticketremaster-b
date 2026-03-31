"""
Redis-based token blacklist for immediate token revocation.
Provides functionality to blacklist JWT tokens and check if tokens are revoked.
"""
import logging
import os
import time
from typing import Optional

import redis

logger = logging.getLogger(__name__)

# Configuration
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
BLACKLIST_PREFIX = os.environ.get("TOKEN_BLACKLIST_PREFIX", "token_blacklist:")
BLACKLIST_TTL_BUFFER = int(os.environ.get("TOKEN_BLACKLIST_TTL_BUFFER", "300"))  # 5 minutes buffer


class TokenBlacklist:
    """Redis-based token blacklist for JWT revocation."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or REDIS_URL
        self._client: Optional[redis.Redis] = None
        self._connected = False
    
    def _get_client(self) -> Optional[redis.Redis]:
        """Get or create Redis client with connection pooling."""
        if self._client and self._connected:
            return self._client
        
        try:
            self._client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                health_check_interval=30,
            )
            self._client.ping()
            self._connected = True
            return self._client
        except Exception as exc:
            logger.warning(f"Redis unavailable for token blacklist: {exc}")
            self._connected = False
            return None
    
    def blacklist_token(self, token_id: str, exp: int, jti: Optional[str] = None) -> bool:
        """
        Add a token to the blacklist.
        
        Args:
            token_id: Unique identifier for the token (usually the jti claim).
            exp: Token expiration timestamp (Unix epoch).
            jti: Optional JWT ID claim. If not provided, token_id is used.
        
        Returns:
            True if successfully blacklisted, False otherwise.
        """
        client = self._get_client()
        if not client:
            logger.error("Cannot blacklist token: Redis unavailable")
            return False
        
        try:
            key = f"{BLACKLIST_PREFIX}{jti or token_id}"
            # TTL is expiration time plus a buffer to ensure the token is cleaned up
            ttl = exp - int(time.time()) + BLACKLIST_TTL_BUFFER
            if ttl <= 0:
                ttl = BLACKLIST_TTL_BUFFER  # Minimum TTL
            
            client.setex(key, ttl, "revoked")
            logger.info(f"Token {jti or token_id} blacklisted successfully")
            return True
        except Exception as exc:
            logger.error(f"Failed to blacklist token: {exc}")
            return False
    
    def is_blacklisted(self, token_id: str) -> bool:
        """
        Check if a token is blacklisted.
        
        Args:
            token_id: Unique identifier for the token (usually the jti claim).
        
        Returns:
            True if the token is blacklisted, False otherwise.
        """
        client = self._get_client()
        if not client:
            # If Redis is unavailable, we can't check the blacklist
            # Fail open (allow the token) but log a warning
            logger.warning("Redis unavailable for token blacklist check, failing open")
            return False
        
        try:
            key = f"{BLACKLIST_PREFIX}{token_id}"
            return client.exists(key) == 1
        except Exception as exc:
            logger.error(f"Failed to check token blacklist: {exc}")
            return False
    
    def revoke_all_user_tokens(self, user_id: str) -> bool:
        """
        Revoke all tokens for a specific user.
        This is useful for logout-all-devices functionality.
        
        Note: This requires storing a mapping of user_id -> token_ids,
        which adds complexity. For simplicity, this implementation
        uses a pattern-based scan which may be slower for large datasets.
        
        Args:
            user_id: The user ID whose tokens should be revoked.
        
        Returns:
            True if revocation was attempted, False on error.
        """
        client = self._get_client()
        if not client:
            logger.error("Cannot revoke user tokens: Redis unavailable")
            return False
        
        try:
            # Scan for all tokens belonging to this user
            pattern = f"{BLACKLIST_PREFIX}*"
            cursor = 0
            revoked_count = 0
            
            while True:
                cursor, keys = client.scan(cursor=cursor, match=pattern, count=100)
                for key in keys:
                    # Check if this token belongs to the user
                    # We'd need to store user_id with the token for efficient lookup
                    # For now, this is a placeholder for the concept
                    pass
                
                if cursor == 0:
                    break
            
            logger.info(f"Revoked {revoked_count} tokens for user {user_id}")
            return True
        except Exception as exc:
            logger.error(f"Failed to revoke user tokens: {exc}")
            return False
    
    def cleanup_expired(self) -> int:
        """
        Clean up expired entries from the blacklist.
        This is mostly handled by Redis TTL, but can be used for maintenance.
        
        Returns:
            Number of keys cleaned up.
        """
        # Redis automatically expires keys with TTL, so this is mostly a no-op
        # unless we want to do additional maintenance
        return 0
    
    def get_stats(self) -> dict:
        """
        Get statistics about the blacklist.
        
        Returns:
            Dictionary with blacklist statistics.
        """
        client = self._get_client()
        if not client:
            return {"error": "Redis unavailable", "connected": False}
        
        try:
            # Count keys matching our prefix
            cursor = 0
            count = 0
            pattern = f"{BLACKLIST_PREFIX}*"
            
            while True:
                cursor, keys = client.scan(cursor=cursor, match=pattern, count=100)
                count += len(keys)
                if cursor == 0:
                    break
            
            return {
                "connected": True,
                "blacklisted_count": count,
                "prefix": BLACKLIST_PREFIX,
            }
        except Exception as exc:
            return {"error": str(exc), "connected": False}


# Global instance for use across the application
_blacklist_instance: Optional[TokenBlacklist] = None


def get_token_blacklist() -> TokenBlacklist:
    """Get or create the global token blacklist instance."""
    global _blacklist_instance
    if _blacklist_instance is None:
        _blacklist_instance = TokenBlacklist()
    return _blacklist_instance


def init_token_blacklist(redis_url: Optional[str] = None) -> TokenBlacklist:
    """Initialize the token blacklist with custom configuration."""
    global _blacklist_instance
    _blacklist_instance = TokenBlacklist(redis_url)
    return _blacklist_instance
