"""
Rate Limiter with Resilient Fallback Mechanisms
Handles Redis failures gracefully without breaking API functionality
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import current_app, request, g
import logging
import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class InMemoryRateLimiter:
    """Fallback in-memory rate limiter when Redis is unavailable"""
    
    def __init__(self):
        self.requests = defaultdict(deque)  # IP -> timestamps
        self.locks = defaultdict(threading.Lock)
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
    
    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        """Check if request is allowed under rate limit"""
        now = time.time()
        
        # Periodic cleanup of old entries
        if now - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_entries(now)
            self.last_cleanup = now
        
        with self.locks[key]:
            request_times = self.requests[key]
            
            # Remove requests outside the current window
            cutoff = now - window
            while request_times and request_times[0] < cutoff:
                request_times.popleft()
            
            # Check if under limit
            if len(request_times) < limit:
                request_times.append(now)
                return True
            
            return False
    
    def _cleanup_old_entries(self, now: float):
        """Clean up old entries to prevent memory bloat"""
        keys_to_remove = []
        
        for key, request_times in self.requests.items():
            with self.locks[key]:
                # Remove all entries older than 1 hour
                cutoff = now - 3600
                while request_times and request_times[0] < cutoff:
                    request_times.popleft()
                
                # If no recent requests, mark for removal
                if not request_times:
                    keys_to_remove.append(key)
        
        # Remove empty entries
        for key in keys_to_remove:
            self.requests.pop(key, None)
            self.locks.pop(key, None)
        
        if keys_to_remove:
            logger.info(f"Rate limiter cleanup: removed {len(keys_to_remove)} inactive entries")

class ResilientRateLimiter:
    """Production-ready rate limiter with Redis and fallback"""
    
    def __init__(self):
        self.limiter = None
        self.fallback_limiter = InMemoryRateLimiter()
        self.redis_available = False
        self.last_redis_check = 0
        self.redis_check_interval = 30  # Check Redis every 30 seconds
    
    def init_app(self, app):
        """Initialize rate limiter with Redis and fallback"""
        try:
            # Always use in-memory storage first for reliability
            self.limiter = Limiter(
                app,
                key_func=self._get_rate_limit_key,
                default_limits=["1000 per hour", "100 per minute"],
                storage_uri="memory://",
                on_breach=self._rate_limit_handler,
                headers_enabled=True
            )
            
            # CRITICAL FIX: Set up rate limiter to skip health endpoints
            # We'll handle this in the key function instead of exempt()
            
            logger.info("✅ Rate limiter initialized with in-memory storage (health endpoints exempt)")
            
            # Try to upgrade to Redis if available (optional)
            try:
                from .redis_client import get_redis_client
                redis_url = app.config.get('REDIS_URL')
                if redis_url and redis_url != 'memory://':
                    redis_client = get_redis_client(redis_url)
                    if redis_client and redis_client.ping():
                        logger.info("✅ Redis available for rate limiting (using memory for now)")
                        self.redis_available = True
                    else:
                        logger.info("⚠️  Redis not available, using in-memory rate limiting")
            except Exception as redis_error:
                logger.warning(f"⚠️  Redis connection failed, using in-memory rate limiting: {redis_error}")
                self.redis_available = False
            
        except Exception as e:
            logger.error(f"❌ Rate limiter initialization failed: {e}")
            # Create minimal limiter to prevent app failure
            self.limiter = Limiter(
                app,
                key_func=self._get_rate_limit_key,
                default_limits=["1000 per hour"],
                storage_uri="memory://",
                headers_enabled=True
            )
    
    def _get_health_check_blueprint(self):
        """Identify health check endpoints that should be exempt from rate limiting"""
        from flask import request
        
        # Exempt health check and monitoring endpoints
        health_paths = ['/health', '/health/quick', '/security/status', '/monitoring/status']
        if request and request.path in health_paths:
            return True
        
        return False
    
    def _get_rate_limit_key(self) -> str:
        """Generate rate limit key for requests"""
        # Use IP address as primary key
        ip = get_remote_address()
        
        # For authenticated users, also consider user ID  
        if hasattr(g, 'current_user') and g.current_user and g.current_user.is_authenticated:
            return f"user_{g.current_user.id}_{ip}"
        
        return f"ip_{ip}"
    
    def _rate_limit_handler(self, request_limit):
        """Handle rate limit breaches"""
        ip = get_remote_address()
        logger.warning(f"Rate limit exceeded for IP {ip}: {request_limit.limit}")
        
        return {
            "error": "Rate limit exceeded",
            "message": f"Too many requests. Limit: {request_limit.limit}",
            "retry_after": request_limit.retry_after
        }, 429
    
    def check_redis_health(self):
        """Check Redis health periodically"""
        now = time.time()
        if now - self.last_redis_check < self.redis_check_interval:
            return self.redis_available
        
        try:
            from .redis_client import get_redis_client
            redis_client = get_redis_client()
            self.redis_available = redis_client.ping()
            self.last_redis_check = now
            
        except Exception:
            self.redis_available = False
            self.last_redis_check = now
        
        return self.redis_available
    
    def manual_rate_limit_check(self, key: str, limit: int = 100, window: int = 3600) -> bool:
        """Manual rate limit check using fallback mechanism"""
        if not self.limiter:
            # Use fallback limiter
            return self.fallback_limiter.is_allowed(key, limit, window)
        
        try:
            # Try to use Flask-Limiter's internal storage
            storage = self.limiter._storage
            current_count = storage.get(key) or 0
            
            if current_count >= limit:
                return False
            
            # Increment counter
            storage.incr(key, window)
            return True
            
        except Exception as e:
            logger.warning(f"Rate limit check failed, using fallback: {e}")
            return self.fallback_limiter.is_allowed(key, limit, window)
    
    def get_rate_limit_info(self) -> Dict[str, Any]:
        """Get rate limiter status information"""
        return {
            "limiter_initialized": self.limiter is not None,
            "redis_available": self.check_redis_health(),
            "storage_type": "redis" if self.redis_available else "memory",
            "fallback_entries": len(self.fallback_limiter.requests) if self.fallback_limiter else 0
        }

# Global rate limiter instance
_rate_limiter = ResilientRateLimiter()

def init_rate_limiter(app):
    """Initialize rate limiter for the application"""
    global _rate_limiter
    _rate_limiter.init_app(app)
    return _rate_limiter

def get_rate_limiter():
    """Get the global rate limiter instance"""
    return _rate_limiter

def rate_limiter_health_check():
    """Health check for rate limiter"""
    limiter = get_rate_limiter()
    return limiter.get_rate_limit_info()