"""
Redis Connection Manager with Performance Optimization
Handles Redis connection pooling, timeouts, and fallback for Stevedores Dashboard 3.0
"""

import redis
from redis.connection import ConnectionPool
from redis.exceptions import ConnectionError, TimeoutError, RedisError
import logging
import time
import json
from functools import wraps
from typing import Optional, Any, Dict

logger = logging.getLogger(__name__)

class RedisManager:
    """Optimized Redis connection manager with fallback capabilities"""
    
    def __init__(self, app=None):
        self.redis_client = None
        self.connection_pool = None
        self.is_healthy = False
        self.last_health_check = 0
        self.health_check_interval = 30  # seconds
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize Redis manager with Flask app"""
        redis_url = app.config.get('REDIS_URL')
        
        if redis_url:
            try:
                # Create optimized connection pool
                self.connection_pool = ConnectionPool.from_url(
                    redis_url,
                    max_connections=15,          # Reduced from default 50
                    retry_on_timeout=True,
                    retry_on_error=[ConnectionError, TimeoutError],
                    socket_timeout=3.0,          # 3 second socket timeout
                    socket_connect_timeout=3.0,   # 3 second connection timeout
                    health_check_interval=30,    # Health check every 30s
                    socket_keepalive=True,
                    socket_keepalive_options={},
                )
                
                # Create Redis client with optimized settings
                self.redis_client = redis.Redis(
                    connection_pool=self.connection_pool,
                    decode_responses=True,       # Automatically decode responses
                    retry_on_error=[ConnectionError],
                    socket_keepalive=True,
                    socket_keepalive_options={}
                )
                
                # Initial health check
                self.health_check()
                
                app.logger.info(f"✅ Redis manager initialized - Health: {self.is_healthy}")
                
            except Exception as e:
                app.logger.error(f"❌ Redis initialization failed: {e}")
                self.redis_client = None
                self.is_healthy = False
        else:
            app.logger.warning("⚠️ No REDIS_URL provided - Redis features disabled")
    
    def health_check(self) -> bool:
        """Check Redis connection health with caching"""
        current_time = time.time()
        
        # Use cached result if recent
        if current_time - self.last_health_check < self.health_check_interval:
            return self.is_healthy
        
        try:
            if self.redis_client:
                # Quick ping with timeout
                result = self.redis_client.ping()
                self.is_healthy = result is True
                
                if self.is_healthy:
                    # Additional connection pool health check
                    info = self.redis_client.info('clients')
                    connected_clients = info.get('connected_clients', 0)
                    
                    # Log if connection count is high
                    if connected_clients > 10:
                        logger.warning(f"High Redis connection count: {connected_clients}")
                
            else:
                self.is_healthy = False
                
        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.warning(f"Redis health check failed: {e}")
            self.is_healthy = False
        except Exception as e:
            logger.error(f"Unexpected Redis health check error: {e}")
            self.is_healthy = False
        
        self.last_health_check = current_time
        return self.is_healthy
    
    def get_client(self) -> Optional[redis.Redis]:
        """Get Redis client if available and healthy"""
        if self.health_check():
            return self.redis_client
        return None
    
    def safe_get(self, key: str, default=None) -> Any:
        """Safely get value from Redis with error handling"""
        try:
            client = self.get_client()
            if client:
                result = client.get(key)
                if result:
                    # Try to parse JSON, fallback to raw string
                    try:
                        return json.loads(result)
                    except (json.JSONDecodeError, TypeError):
                        return result
        except Exception as e:
            logger.debug(f"Redis get failed for key '{key}': {e}")
        
        return default
    
    def safe_set(self, key: str, value: Any, timeout: int = 300) -> bool:
        """Safely set value in Redis with error handling"""
        try:
            client = self.get_client()
            if client:
                # Serialize complex objects as JSON
                if isinstance(value, (dict, list, tuple)):
                    value = json.dumps(value, default=str)
                
                result = client.setex(key, timeout, value)
                return result is True
        except Exception as e:
            logger.debug(f"Redis set failed for key '{key}': {e}")
        
        return False
    
    def safe_delete(self, *keys: str) -> int:
        """Safely delete keys from Redis"""
        try:
            client = self.get_client()
            if client and keys:
                return client.delete(*keys)
        except Exception as e:
            logger.debug(f"Redis delete failed for keys {keys}: {e}")
        
        return 0
    
    def safe_exists(self, key: str) -> bool:
        """Check if key exists in Redis"""
        try:
            client = self.get_client()
            if client:
                return client.exists(key) > 0
        except Exception as e:
            logger.debug(f"Redis exists check failed for key '{key}': {e}")
        
        return False
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get Redis connection statistics"""
        stats = {
            'healthy': self.is_healthy,
            'last_check': self.last_health_check,
            'client_available': self.redis_client is not None
        }
        
        try:
            client = self.get_client()
            if client:
                info = client.info('clients')
                stats.update({
                    'connected_clients': info.get('connected_clients', 0),
                    'client_longest_output_list': info.get('client_longest_output_list', 0),
                    'client_biggest_input_buf': info.get('client_biggest_input_buf', 0)
                })
                
                # Memory info
                memory_info = client.info('memory')
                stats['used_memory_mb'] = round(memory_info.get('used_memory', 0) / 1024 / 1024, 2)
        except Exception as e:
            logger.debug(f"Failed to get Redis stats: {e}")
            stats['error'] = str(e)
        
        return stats

# Decorator for Redis operations with fallback
def redis_fallback(fallback_value=None, log_errors=True):
    """Decorator for Redis operations with automatic fallback"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (ConnectionError, TimeoutError, RedisError) as e:
                if log_errors:
                    logger.warning(f"Redis operation failed in {func.__name__}: {e}")
                return fallback_value
            except Exception as e:
                if log_errors:
                    logger.error(f"Unexpected error in {func.__name__}: {e}")
                return fallback_value
        return wrapper
    return decorator

# Global Redis manager instance (initialized by app factory)
redis_manager = None

def get_redis_manager() -> Optional[RedisManager]:
    """Get global Redis manager instance"""
    return redis_manager

def init_redis_manager(app) -> RedisManager:
    """Initialize global Redis manager"""
    global redis_manager
    redis_manager = RedisManager(app)
    return redis_manager