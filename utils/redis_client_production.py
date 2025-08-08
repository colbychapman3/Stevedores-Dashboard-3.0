"""
Production-grade Redis client with circuit breaker pattern and fallback mechanisms.
Enterprise resilience for Stevedores Dashboard 3.0 production deployment.
"""

import redis
import logging
import time
import threading
from typing import Optional, Dict, Any, Union
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict
import os

logger = logging.getLogger(__name__)

class CircuitBreakerState:
    CLOSED = "closed"
    OPEN = "open" 
    HALF_OPEN = "half_open"

class RedisCircuitBreaker:
    """Circuit breaker pattern for Redis connections."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
        self._lock = threading.RLock()
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    logger.info("Redis circuit breaker transitioning to HALF_OPEN")
                else:
                    raise redis.ConnectionError("Redis circuit breaker is OPEN")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise e
    
    def _should_attempt_reset(self) -> bool:
        return (
            self.last_failure_time and 
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self):
        self.failure_count = 0
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.CLOSED
            logger.info("Redis circuit breaker reset to CLOSED")
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning(f"Redis circuit breaker OPENED after {self.failure_count} failures")

class InMemoryFallback:
    """In-memory fallback for Redis operations."""
    
    def __init__(self):
        self.data = {}
        self.expires = {}
        self._lock = threading.RLock()
    
    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        with self._lock:
            self.data[key] = value
            if ex:
                self.expires[key] = datetime.now() + timedelta(seconds=ex)
            return True
    
    def get(self, key: str) -> Optional[str]:
        with self._lock:
            if key in self.expires:
                if datetime.now() > self.expires[key]:
                    self._cleanup_expired(key)
                    return None
            return self.data.get(key)
    
    def incr(self, key: str, amount: int = 1) -> int:
        with self._lock:
            current = int(self.data.get(key, 0))
            new_value = current + amount
            self.data[key] = str(new_value)
            return new_value
    
    def delete(self, key: str) -> int:
        with self._lock:
            deleted = 0
            if key in self.data:
                del self.data[key]
                deleted += 1
            if key in self.expires:
                del self.expires[key]
            return deleted
    
    def _cleanup_expired(self, key: str):
        if key in self.data:
            del self.data[key]
        if key in self.expires:
            del self.expires[key]

class ProductionRedisClient:
    """Production-ready Redis client with circuit breaker and fallbacks."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv('REDIS_URL')
        self.circuit_breaker = RedisCircuitBreaker()
        self.fallback = InMemoryFallback()
        self._redis_client = None
        self.connected = False
        self.fallback_mode = False
        
        # Rate limiting counters
        self.rate_limit_counters = defaultdict(int)
        self.rate_limit_windows = defaultdict(float)
        
        self._initialize_redis()
        self._start_cleanup_thread()
    
    def _initialize_redis(self):
        """Initialize Redis connection with production settings."""
        if not self.redis_url:
            logger.warning("No Redis URL configured, using fallback mode only")
            self.fallback_mode = True
            return
        
        try:
            self._redis_client = redis.from_url(
                self.redis_url,
                max_connections=20,
                retry_on_timeout=True,
                socket_keepalive=True,
                health_check_interval=30,
                decode_responses=True
            )
            
            # Test connection
            self._redis_client.ping()
            self.connected = True
            logger.info("Production Redis connection established")
            
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self.connected = False
            self.fallback_mode = True
    
    def _start_cleanup_thread(self):
        """Start background cleanup thread."""
        def cleanup_worker():
            while True:
                try:
                    self.fallback._cleanup_all_expired()
                    time.sleep(60)
                except Exception as e:
                    logger.error(f"Cleanup thread error: {e}")
                    time.sleep(60)
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
    
    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set with fallback."""
        if self.fallback_mode:
            return self.fallback.set(key, value, ex)
        
        try:
            result = self.circuit_breaker.call(
                self._redis_client.set, key, value, ex=ex
            )
            return result
        except Exception as e:
            logger.warning(f"Redis SET failed, using fallback: {e}")
            return self.fallback.set(key, value, ex)
    
    def get(self, key: str) -> Optional[str]:
        """Get with fallback."""
        if self.fallback_mode:
            return self.fallback.get(key)
        
        try:
            result = self.circuit_breaker.call(self._redis_client.get, key)
            return result
        except Exception as e:
            logger.warning(f"Redis GET failed, using fallback: {e}")
            return self.fallback.get(key)
    
    def incr(self, key: str, amount: int = 1) -> int:
        """Increment with fallback."""
        if self.fallback_mode:
            return self.fallback.incr(key, amount)
        
        try:
            result = self.circuit_breaker.call(
                self._redis_client.incr, key, amount
            )
            return result
        except Exception as e:
            logger.warning(f"Redis INCR failed, using fallback: {e}")
            return self.fallback.incr(key, amount)
    
    def ping(self) -> bool:
        """Health check ping."""
        if self.fallback_mode:
            return False
        
        try:
            result = self.circuit_breaker.call(self._redis_client.ping)
            return result
        except Exception:
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get Redis status information."""
        return {
            'redis_connected': self.connected and not self.fallback_mode,
            'fallback_mode': self.fallback_mode,
            'circuit_breaker_state': self.circuit_breaker.state,
            'failure_count': self.circuit_breaker.failure_count,
            'status': 'healthy' if self.connected else 'degraded'
        }

# Global instance
production_redis_client = ProductionRedisClient()

# Rate limiting with Redis fallback
def rate_limit_check(key: str, limit: int, window: int) -> bool:
    """Production rate limiting with fallback."""
    try:
        now = time.time()
        window_key = f"rate_limit:{key}:{int(now // window)}"
        
        current = production_redis_client.incr(window_key)
        if current == 1:
            production_redis_client.set(f"{window_key}_exp", "1", ex=window)
        
        return current <= limit
    except Exception as e:
        logger.error(f"Rate limit check failed: {e}")
        return True  # Fail open for availability