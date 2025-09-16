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
    
    def _cleanup_all_expired(self):
        """Clean up all expired keys in background thread."""
        with self._lock:
            now = datetime.now()
            expired_keys = []
            
            for key, expire_time in self.expires.items():
                if now > expire_time:
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._cleanup_expired(key)
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired keys from memory fallback")

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
        
        # Connection attempt throttling
        self.last_connection_attempt = 0
        self.connection_failure_count = 0
        self.max_retry_interval = 300  # 5 minutes max
        self.base_retry_interval = 60  # Start with 1 minute
        self.last_failure_type = None
        
        # Logging throttling
        self.last_log_time = 0
        self.log_interval = 300  # Log Redis issues max every 5 minutes
        self.failure_count_since_log = 0
        
        # Periodic recovery
        self.last_recovery_attempt = 0
        self.recovery_interval = 300  # Try recovery every 5 minutes
        
        self._initialize_redis()
        self._start_cleanup_thread()
    
    def _initialize_redis(self):
        """Initialize Redis connection with production settings and enhanced error handling."""
        if not self.redis_url:
            self._log_throttled("⚠️  No Redis URL configured, using fallback mode only", 'warning')
            self.fallback_mode = True
            return
        
        # Check if Redis URL looks valid
        if not self.redis_url.startswith(('redis://', 'rediss://')):
            self._log_throttled(f"❌ Invalid Redis URL format: {self.redis_url}", 'error')
            self.fallback_mode = True
            return
        
        # Implement connection attempt throttling
        current_time = time.time()
        
        # Check if we should throttle connection attempts
        if self.last_connection_attempt > 0:
            retry_interval = self._calculate_retry_interval()
            time_since_last_attempt = current_time - self.last_connection_attempt
            
            if time_since_last_attempt < retry_interval:
                # Skip connection attempt - too soon since last failure
                if not self.fallback_mode:
                    self._log_throttled(f"🔄 Redis connection throttled - waiting {retry_interval - time_since_last_attempt:.1f}s", 'debug')
                    self.fallback_mode = True
                return
        
        self.last_connection_attempt = current_time
        logger.info(f"🔗 Attempting Redis connection to: {self.redis_url.split('@')[-1] if '@' in self.redis_url else 'local'}")
        
        try:
            # Enhanced Redis configuration for production stability
            connection_params = {
                'socket_keepalive': True,
                'socket_keepalive_options': {},
                'health_check_interval': 30,
                'decode_responses': True,
                'socket_timeout': 5,  # 5 second socket timeout
                'socket_connect_timeout': 10,  # 10 second connection timeout
                'retry_on_timeout': True,
                'max_connections': 20
            }
            
            # Add SSL configuration for rediss:// URLs
            if self.redis_url.startswith('rediss://'):
                connection_params['ssl_cert_reqs'] = None
                connection_params['ssl_check_hostname'] = False
                logger.info("🔒 Using SSL/TLS Redis connection")
            
            self._redis_client = redis.from_url(self.redis_url, **connection_params)
            
            # Test connection with timeout
            self._redis_client.ping()
            self.connected = True
            self.connection_failure_count = 0  # Reset failure count on success
            logger.info("✅ Production Redis connection established successfully")
            
        except redis.ConnectionError as conn_error:
            self._handle_connection_failure('connection_error', str(conn_error))
            
        except redis.TimeoutError as timeout_error:
            self._handle_connection_failure('timeout_error', str(timeout_error))
            
        except Exception as e:
            # Categorize the error type for better handling
            error_msg = str(e).lower()
            if "name or service not known" in error_msg:
                self._handle_connection_failure('dns_error', str(e))
            elif "connection refused" in error_msg:
                self._handle_connection_failure('connection_refused', str(e))
            else:
                self._handle_connection_failure('unknown_error', str(e))
    
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
    
    def _calculate_retry_interval(self) -> float:
        """Calculate exponential backoff retry interval with jitter and special handling for persistent DNS failures."""
        if self.connection_failure_count == 0:
            return self.base_retry_interval
        
        # For persistent DNS failures (like invalid hostnames), use longer intervals
        if self.last_failure_type == 'dns_error' and self.connection_failure_count > 5:
            # Use extended intervals for DNS failures to reduce unnecessary attempts
            base_dns_interval = 600  # 10 minutes for persistent DNS issues
            interval = min(
                base_dns_interval * (2 ** min(self.connection_failure_count - 5, 3)),
                3600  # Cap at 1 hour for DNS failures
            )
        else:
            # Normal exponential backoff with jitter
            interval = min(
                self.base_retry_interval * (2 ** self.connection_failure_count),
                self.max_retry_interval
            )
        
        # Add jitter (±20% randomization)
        import random
        jitter = interval * 0.2 * (random.random() - 0.5)
        
        return max(self.base_retry_interval, interval + jitter)
    
    def _handle_connection_failure(self, failure_type: str, error_message: str):
        """Handle Redis connection failures with enhanced logging and tracking."""
        self.connected = False
        self.fallback_mode = True
        self.last_failure_type = failure_type
        self.connection_failure_count += 1
        self.failure_count_since_log += 1
        
        # Enhanced logging based on failure type
        if failure_type == 'dns_error':
            # For DNS errors, be more conservative with logging after persistent failures
            if self.connection_failure_count <= 3:
                self._log_throttled(
                    f"🌐 Redis DNS resolution failed (attempt {self.connection_failure_count}): {error_message}",
                    'warning'
                )
            elif self.connection_failure_count == 4:
                self._log_throttled(
                    f"🌐 Redis DNS persistent failure - switching to extended fallback mode",
                    'warning'
                )
                logger.info("🛡️ Application operating with in-memory fallback - this is normal for environments without Redis")
            else:
                # After 4 failures, only log every 10th attempt to reduce noise
                if self.connection_failure_count % 10 == 0:
                    self._log_throttled(
                        f"🌐 Redis DNS still failing after {self.connection_failure_count} attempts - continuing with fallback",
                        'debug'
                    )
            
            if self.failure_count_since_log == 1 and self.connection_failure_count <= 2:  # First couple failures get more detail
                logger.info("🌐 This may be due to network connectivity or DNS configuration issues")
                logger.info("🛡️ Application will continue with in-memory fallback until Redis is available")
                
        elif failure_type == 'connection_refused':
            self._log_throttled(
                f"🔌 Redis server connection refused (attempt {self.connection_failure_count}): {error_message}",
                'warning'
            )
            
        elif failure_type == 'timeout_error':
            self._log_throttled(
                f"⏱️  Redis connection timeout (attempt {self.connection_failure_count}): {error_message}",
                'warning'
            )
            
        else:
            self._log_throttled(
                f"⚠️  Redis connection failed with {failure_type} (attempt {self.connection_failure_count}): {error_message}",
                'warning'
            )
    
    def _log_throttled(self, message: str, level: str = 'info'):
        """Log messages with throttling to reduce spam."""
        current_time = time.time()
        
        # For the first failure, always log immediately
        if self.failure_count_since_log == 1 or current_time - self.last_log_time >= self.log_interval:
            
            if self.failure_count_since_log > 1:
                # Add summary of repeated failures
                summary_msg = f"{message} (Total failures since last log: {self.failure_count_since_log})"
            else:
                summary_msg = message
            
            # Log at appropriate level
            if level == 'error':
                logger.error(summary_msg)
            elif level == 'warning':
                logger.warning(summary_msg)
            elif level == 'info':
                logger.info(summary_msg)
            elif level == 'debug':
                logger.debug(summary_msg)
            
            self.last_log_time = current_time
            self.failure_count_since_log = 0  # Reset counter after logging
    
    def _should_attempt_recovery(self) -> bool:
        """Check if we should attempt Redis connection recovery."""
        if not self.fallback_mode:
            return False  # Not in fallback mode, no need for recovery
        
        current_time = time.time()
        return current_time - self.last_recovery_attempt >= self.recovery_interval
    
    def _attempt_recovery(self):
        """Attempt to recover Redis connection if in fallback mode."""
        if not self._should_attempt_recovery():
            return False
        
        self.last_recovery_attempt = time.time()
        logger.debug("🔄 Attempting Redis connection recovery...")
        
        # Temporarily reset failure count for recovery attempt
        old_failure_count = self.connection_failure_count
        self.connection_failure_count = 0
        
        self._initialize_redis()
        
        if self.connected and not self.fallback_mode:
            logger.info("✅ Redis connection recovered successfully!")
            return True
        else:
            # Restore failure count if recovery failed
            self.connection_failure_count = old_failure_count
            return False
    
    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set with fallback and recovery attempt."""
        # Attempt recovery if appropriate
        if self.fallback_mode:
            self._attempt_recovery()
        
        if self.fallback_mode:
            return self.fallback.set(key, value, ex)
        
        try:
            result = self.circuit_breaker.call(
                self._redis_client.set, key, value, ex=ex
            )
            return result
        except Exception as e:
            self._log_throttled(f"Redis SET operation failed, using fallback: {e}", 'debug')
            self._handle_connection_failure('operation_error', str(e))
            return self.fallback.set(key, value, ex)
    
    def get(self, key: str) -> Optional[str]:
        """Get with fallback and recovery attempt."""
        # Attempt recovery if appropriate
        if self.fallback_mode:
            self._attempt_recovery()
        
        if self.fallback_mode:
            return self.fallback.get(key)
        
        try:
            result = self.circuit_breaker.call(self._redis_client.get, key)
            return result
        except Exception as e:
            self._log_throttled(f"Redis GET operation failed, using fallback: {e}", 'debug')
            self._handle_connection_failure('operation_error', str(e))
            return self.fallback.get(key)
    
    def incr(self, key: str, amount: int = 1) -> int:
        """Increment with fallback and recovery attempt."""
        # Attempt recovery if appropriate
        if self.fallback_mode:
            self._attempt_recovery()
        
        if self.fallback_mode:
            return self.fallback.incr(key, amount)
        
        try:
            result = self.circuit_breaker.call(
                self._redis_client.incr, key, amount
            )
            return result
        except Exception as e:
            self._log_throttled(f"Redis INCR operation failed, using fallback: {e}", 'debug')
            self._handle_connection_failure('operation_error', str(e))
            return self.fallback.incr(key, amount)
    
    def ping(self) -> bool:
        """Health check ping with throttled recovery attempts."""
        # Attempt recovery only if it's time to try
        if self.fallback_mode:
            if self._should_attempt_recovery():
                return self._attempt_recovery()
            return False  # Don't attempt Redis ping if in fallback mode
        
        try:
            result = self.circuit_breaker.call(self._redis_client.ping)
            return result
        except Exception as e:
            self._log_throttled(f"Redis PING failed: {e}", 'debug')
            self._handle_connection_failure('ping_error', str(e))
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive Redis status information."""
        current_time = time.time()
        return {
            'redis_connected': self.connected and not self.fallback_mode,
            'fallback_mode': self.fallback_mode,
            'circuit_breaker_state': self.circuit_breaker.state,
            'connection_failure_count': self.connection_failure_count,
            'last_failure_type': self.last_failure_type,
            'time_since_last_attempt': current_time - self.last_connection_attempt if self.last_connection_attempt > 0 else 0,
            'next_retry_in': max(0, self._calculate_retry_interval() - (current_time - self.last_connection_attempt)) if self.last_connection_attempt > 0 else 0,
            'time_since_last_recovery': current_time - self.last_recovery_attempt if self.last_recovery_attempt > 0 else 0,
            'failures_since_log': self.failure_count_since_log,
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