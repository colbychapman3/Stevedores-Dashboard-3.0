"""
Multi-Layer Cache Manager for Stevedores Dashboard 3.0
Implements Redis-backed caching with in-memory fallback and performance optimization
"""

import json
import hashlib
import time
import logging
from functools import wraps
from typing import Any, Dict, Optional, Union, Callable
from flask import request, current_app, g

logger = logging.getLogger(__name__)

class CacheManager:
    """Multi-layer caching system with Redis primary and in-memory fallback"""
    
    def __init__(self, redis_manager=None, default_timeout=300):
        self.redis_manager = redis_manager
        self.default_timeout = default_timeout
        self.fallback_cache = {}  # In-memory fallback cache
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'redis_hits': 0,
            'fallback_hits': 0,
            'errors': 0
        }
        
        # Cache size limits to prevent memory issues
        self.max_fallback_size = 1000
        self.fallback_cleanup_threshold = 0.8
    
    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a unique cache key from arguments"""
        # Create a deterministic string from all arguments
        key_parts = [str(prefix)]
        key_parts.extend([str(arg) for arg in args])
        
        # Add sorted kwargs
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            key_parts.extend([f"{k}:{v}" for k, v in sorted_kwargs])
        
        # Create hash to ensure key is within limits
        key_string = ":".join(key_parts)
        if len(key_string) > 200:  # Redis key limit precaution
            key_hash = hashlib.md5(key_string.encode()).hexdigest()
            return f"{prefix}:{key_hash}"
        
        return key_string.replace(' ', '_')  # Replace spaces for compatibility
    
    def _cleanup_fallback_cache(self):
        """Clean up fallback cache when it gets too large"""
        if len(self.fallback_cache) > self.max_fallback_size * self.fallback_cleanup_threshold:
            # Remove oldest 20% of entries (simple LRU-like behavior)
            items = list(self.fallback_cache.items())
            items_to_remove = items[:len(items) // 5]
            
            for key, _ in items_to_remove:
                del self.fallback_cache[key]
            
            logger.debug(f"Cleaned up fallback cache: removed {len(items_to_remove)} entries")
    
    def get(self, key: str, default=None) -> Any:
        """Get value from cache (Redis first, then fallback)"""
        try:
            # Try Redis first
            if self.redis_manager:
                redis_client = self.redis_manager.get_client()
                if redis_client:
                    value = redis_client.get(key)
                    if value is not None:
                        try:
                            result = json.loads(value)
                            self.cache_stats['hits'] += 1
                            self.cache_stats['redis_hits'] += 1
                            return result
                        except json.JSONDecodeError:
                            # Handle non-JSON values
                            self.cache_stats['hits'] += 1
                            self.cache_stats['redis_hits'] += 1
                            return value
            
            # Try fallback cache
            if key in self.fallback_cache:
                cached_item = self.fallback_cache[key]
                
                # Check if expired
                if cached_item['expires_at'] > time.time():
                    self.cache_stats['hits'] += 1
                    self.cache_stats['fallback_hits'] += 1
                    return cached_item['value']
                else:
                    # Remove expired item
                    del self.fallback_cache[key]
            
            # Cache miss
            self.cache_stats['misses'] += 1
            return default
            
        except Exception as e:
            logger.warning(f"Cache get error for key '{key}': {e}")
            self.cache_stats['errors'] += 1
            return default
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        """Set value in cache (Redis primary, fallback secondary)"""
        if timeout is None:
            timeout = self.default_timeout
        
        success = False
        
        try:
            # Set in Redis first
            if self.redis_manager:
                redis_client = self.redis_manager.get_client()
                if redis_client:
                    # Serialize value for Redis
                    if isinstance(value, (dict, list, tuple)):
                        serialized_value = json.dumps(value, default=str)
                    else:
                        serialized_value = json.dumps(value)
                    
                    redis_success = redis_client.setex(key, timeout, serialized_value)
                    if redis_success:
                        success = True
            
            # Always set in fallback cache as backup
            expires_at = time.time() + timeout
            self.fallback_cache[key] = {
                'value': value,
                'expires_at': expires_at,
                'created_at': time.time()
            }
            
            # Cleanup if needed
            self._cleanup_fallback_cache()
            
            return True  # Success if either Redis or fallback worked
            
        except Exception as e:
            logger.warning(f"Cache set error for key '{key}': {e}")
            self.cache_stats['errors'] += 1
            return False
    
    def delete(self, *keys: str) -> int:
        """Delete keys from cache"""
        deleted_count = 0
        
        try:
            # Delete from Redis
            if self.redis_manager and keys:
                redis_client = self.redis_manager.get_client()
                if redis_client:
                    redis_deleted = redis_client.delete(*keys)
                    deleted_count += redis_deleted
            
            # Delete from fallback cache
            for key in keys:
                if key in self.fallback_cache:
                    del self.fallback_cache[key]
                    deleted_count += 1
            
        except Exception as e:
            logger.warning(f"Cache delete error for keys {keys}: {e}")
            self.cache_stats['errors'] += 1
        
        return deleted_count
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            # Check Redis first
            if self.redis_manager:
                redis_client = self.redis_manager.get_client()
                if redis_client and redis_client.exists(key):
                    return True
            
            # Check fallback cache
            if key in self.fallback_cache:
                cached_item = self.fallback_cache[key]
                if cached_item['expires_at'] > time.time():
                    return True
                else:
                    # Remove expired item
                    del self.fallback_cache[key]
            
            return False
            
        except Exception as e:
            logger.warning(f"Cache exists check error for key '{key}': {e}")
            return False
    
    def clear(self, pattern: Optional[str] = None) -> int:
        """Clear cache entries, optionally by pattern"""
        cleared_count = 0
        
        try:
            # Clear Redis
            if self.redis_manager:
                redis_client = self.redis_manager.get_client()
                if redis_client:
                    if pattern:
                        # Delete keys matching pattern
                        keys = redis_client.keys(pattern)
                        if keys:
                            cleared_count += redis_client.delete(*keys)
                    else:
                        # Clear all keys (dangerous - use with caution)
                        redis_client.flushdb()
                        cleared_count += len(self.fallback_cache)
            
            # Clear fallback cache
            if pattern:
                import fnmatch
                keys_to_delete = [
                    key for key in self.fallback_cache.keys()
                    if fnmatch.fnmatch(key, pattern)
                ]
                for key in keys_to_delete:
                    del self.fallback_cache[key]
                    cleared_count += 1
            else:
                cleared_count += len(self.fallback_cache)
                self.fallback_cache.clear()
            
        except Exception as e:
            logger.warning(f"Cache clear error: {e}")
        
        return cleared_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'total_requests': total_requests,
            'hit_rate': round(hit_rate, 2),
            'hits': self.cache_stats['hits'],
            'misses': self.cache_stats['misses'],
            'redis_hits': self.cache_stats['redis_hits'],
            'fallback_hits': self.cache_stats['fallback_hits'],
            'errors': self.cache_stats['errors'],
            'fallback_cache_size': len(self.fallback_cache),
            'redis_available': self.redis_manager.is_healthy if self.redis_manager else False
        }

# Caching decorators
def cached_route(timeout: int = 300, key_prefix: str = 'route', 
                vary_on_user: bool = False, vary_on_args: bool = True):
    """Decorator for caching Flask route responses"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get cache manager from current app
            if not hasattr(current_app, 'cache_manager'):
                return f(*args, **kwargs)
            
            cache_manager = current_app.cache_manager
            
            # Generate cache key
            key_parts = [key_prefix, request.endpoint or f.__name__]
            
            if vary_on_user:
                from flask_login import current_user
                user_id = getattr(current_user, 'id', 'anonymous')
                key_parts.append(str(user_id))
            
            if vary_on_args and request.args:
                args_str = "&".join([f"{k}={v}" for k, v in sorted(request.args.items())])
                key_parts.append(hashlib.md5(args_str.encode()).hexdigest()[:8])
            
            cache_key = ":".join(key_parts)
            
            # Try to get cached result
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = f(*args, **kwargs)
            
            # Only cache successful responses
            if hasattr(result, 'status_code'):
                if result.status_code == 200:
                    cache_manager.set(cache_key, result, timeout)
            else:
                cache_manager.set(cache_key, result, timeout)
            
            return result
        return decorated_function
    return decorator

def cached_function(timeout: int = 300, key_prefix: str = 'func'):
    """Decorator for caching function results"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get cache manager from current app context
            if not hasattr(current_app, 'cache_manager'):
                return f(*args, **kwargs)
            
            cache_manager = current_app.cache_manager
            
            # Generate cache key from function name and arguments
            cache_key = cache_manager._generate_cache_key(
                f"{key_prefix}:{f.__name__}", *args, **kwargs
            )
            
            # Try to get cached result
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = f(*args, **kwargs)
            cache_manager.set(cache_key, result, timeout)
            
            return result
        return decorated_function
    return decorator

def cache_vessel_data(timeout: int = 600):  # 10 minutes for vessel data
    """Specialized caching for vessel-related data"""
    return cached_function(timeout=timeout, key_prefix='vessel')

def cache_tally_data(timeout: int = 300):  # 5 minutes for tally data
    """Specialized caching for cargo tally data"""
    return cached_function(timeout=timeout, key_prefix='tally')

# Global cache manager instance
cache_manager = None

def get_cache_manager() -> Optional[CacheManager]:
    """Get global cache manager instance"""
    return cache_manager

def init_cache_manager(app, redis_manager) -> CacheManager:
    """Initialize global cache manager"""
    global cache_manager
    cache_manager = CacheManager(redis_manager)
    app.cache_manager = cache_manager
    
    # Add cache stats route for monitoring
    @app.route('/api/cache-stats')
    def cache_stats():
        from flask import jsonify
        if hasattr(current_app, 'cache_manager'):
            return jsonify(current_app.cache_manager.get_stats())
        return jsonify({'error': 'Cache manager not available'}), 503
    
    return cache_manager