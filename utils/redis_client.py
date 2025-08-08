"""
Production-Grade Redis Client with Circuit Breaker and Fallback Mechanisms

Features:
- Circuit Breaker Pattern with intelligent failure detection
- Connection Pooling with health monitoring
- Automatic Retry Logic with exponential backoff
- In-Memory Fallback for zero-downtime operations
- Rate Limiting Fallback when Redis is unavailable
- Comprehensive health monitoring and metrics
- Connection lifecycle management
- Memory-efficient fallback cache with TTL

Designed for Stevedores Dashboard 3.0 production environment
"""

import redis
import logging
import time
import threading
import random
import json
import hashlib
from typing import Optional, Any, Dict, List, Callable, Union
from functools import wraps
from datetime import datetime, timedelta
from collections import defaultdict, OrderedDict
from dataclasses import dataclass, asdict
from enum import Enum
import weakref

logger = logging.getLogger(__name__)

class CircuitBreakerState(Enum):
    """Circuit breaker states with enhanced tracking"""
    CLOSED = "closed"        # Normal operation - Redis working
    OPEN = "open"            # Failing - Redis unavailable, use fallback
    HALF_OPEN = "half_open"  # Testing - Limited Redis calls to test recovery
    FORCE_OPEN = "force_open" # Manually disabled - Admin override

@dataclass
class RedisMetrics:
    """Redis performance and health metrics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    circuit_breaker_trips: int = 0
    fallback_hits: int = 0
    avg_response_time_ms: float = 0.0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    connection_pool_size: int = 0
    active_connections: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100.0
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate percentage"""
        return 100.0 - self.success_rate

class AdvancedCircuitBreaker:
    """Enterprise-grade circuit breaker for Redis operations with intelligent failure detection"""
    
    def __init__(self, 
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60,
                 success_threshold: int = 3,
                 failure_rate_threshold: float = 50.0,  # 50% failure rate triggers open
                 min_requests: int = 10):  # Minimum requests before calculating failure rate
        
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.failure_rate_threshold = failure_rate_threshold
        self.min_requests = min_requests
        
        self.failure_count = 0
        self.success_count = 0
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.last_failure_time = None
        self.last_success_time = None
        self.state = CircuitBreakerState.CLOSED
        
        # Enhanced tracking
        self.request_history = []  # Recent requests for failure rate calculation
        self.history_window = 300  # 5 minutes
        self.trip_count = 0
        
        self._lock = threading.RLock()  # Reentrant lock for nested calls
        
        # State change callbacks
        self._state_change_callbacks: List[Callable[[CircuitBreakerState, CircuitBreakerState], None]] = []
        
        logger.info(f"Circuit breaker initialized: threshold={failure_threshold}, recovery={recovery_timeout}s")
    
    def call(self, func, *args, **kwargs):
        """Execute function with intelligent circuit breaker protection"""
        start_time = time.time()
        
        with self._lock:
            # Clean old request history
            self._clean_request_history()
            
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self._change_state(CircuitBreakerState.HALF_OPEN)
                    logger.info("Circuit breaker moving to HALF_OPEN - testing Redis recovery")
                else:
                    raise redis.ConnectionError(f"Circuit breaker OPEN - Redis unavailable (failed {self.failure_count} times)")
            
            elif self.state == CircuitBreakerState.FORCE_OPEN:
                raise redis.ConnectionError("Circuit breaker FORCE_OPEN - Redis manually disabled")
        
        try:
            result = func(*args, **kwargs)
            execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            self._on_success(execution_time)
            return result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self._on_failure(execution_time, e)
            raise e
    
    def add_state_change_callback(self, callback: Callable[[CircuitBreakerState, CircuitBreakerState], None]):
        """Add callback for state changes"""
        self._state_change_callbacks.append(callback)
    
    def _change_state(self, new_state: CircuitBreakerState):
        """Change circuit breaker state and notify callbacks"""
        old_state = self.state
        if old_state != new_state:
            self.state = new_state
            if new_state == CircuitBreakerState.OPEN:
                self.trip_count += 1
            
            # Notify callbacks
            for callback in self._state_change_callbacks:
                try:
                    callback(old_state, new_state)
                except Exception as e:
                    logger.error(f"Circuit breaker state change callback failed: {e}")
    
    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit breaker"""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def _clean_request_history(self):
        """Clean old requests from history"""
        cutoff_time = time.time() - self.history_window
        self.request_history = [req for req in self.request_history if req['timestamp'] > cutoff_time]
    
    def _calculate_failure_rate(self) -> float:
        """Calculate recent failure rate"""
        if len(self.request_history) < self.min_requests:
            return 0.0
        
        failures = sum(1 for req in self.request_history if not req['success'])
        return (failures / len(self.request_history)) * 100.0
    
    def _on_success(self, execution_time_ms: float):
        """Handle successful operation with detailed tracking"""
        with self._lock:
            self.success_count += 1
            self.consecutive_successes += 1
            self.consecutive_failures = 0
            self.last_success_time = time.time()
            
            # Add to request history
            self.request_history.append({
                'timestamp': time.time(),
                'success': True,
                'execution_time_ms': execution_time_ms
            })
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                if self.consecutive_successes >= self.success_threshold:
                    self._change_state(CircuitBreakerState.CLOSED)
                    self.failure_count = 0
                    self.success_count = 0
                    self.consecutive_failures = 0
                    self.consecutive_successes = 0
                    logger.info("✅ Circuit breaker CLOSED - Redis connection restored")
            
            elif self.state == CircuitBreakerState.CLOSED:
                # Reset failure count on success
                if self.consecutive_successes >= 3:
                    self.failure_count = max(0, self.failure_count - 1)
    
    def _on_failure(self, execution_time_ms: float, exception: Exception):
        """Handle failed operation with intelligent failure analysis"""
        with self._lock:
            self.failure_count += 1
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            self.last_failure_time = time.time()
            
            # Add to request history
            self.request_history.append({
                'timestamp': time.time(),
                'success': False,
                'execution_time_ms': execution_time_ms,
                'exception': str(exception)
            })
            
            # Determine if we should open the circuit
            should_open = False
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                # Any failure in half-open state triggers open
                should_open = True
                logger.warning(f"Circuit breaker OPEN - Redis still failing in half-open state: {exception}")
            
            elif self.state == CircuitBreakerState.CLOSED:
                # Check multiple conditions for opening
                failure_rate = self._calculate_failure_rate()
                
                if (self.consecutive_failures >= self.failure_threshold or
                    self.failure_count >= self.failure_threshold * 2 or
                    failure_rate >= self.failure_rate_threshold):
                    
                    should_open = True
                    logger.error(f"Circuit breaker OPEN - Redis failing (consecutive: {self.consecutive_failures}, "
                               f"total: {self.failure_count}, rate: {failure_rate:.1f}%, exception: {exception})")
            
            if should_open:
                self._change_state(CircuitBreakerState.OPEN)
    
    def force_open(self, reason: str = "Manual override"):
        """Manually open circuit breaker"""
        with self._lock:
            self._change_state(CircuitBreakerState.FORCE_OPEN)
            logger.warning(f"Circuit breaker FORCE_OPEN - {reason}")
    
    def force_close(self, reason: str = "Manual override"):
        """Manually close circuit breaker"""
        with self._lock:
            self._change_state(CircuitBreakerState.CLOSED)
            self.failure_count = 0
            self.consecutive_failures = 0
            logger.info(f"Circuit breaker FORCE_CLOSED - {reason}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detailed circuit breaker statistics"""
        with self._lock:
            failure_rate = self._calculate_failure_rate()
            
            return {
                'state': self.state.value,
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'consecutive_failures': self.consecutive_failures,
                'consecutive_successes': self.consecutive_successes,
                'trip_count': self.trip_count,
                'failure_rate_percent': round(failure_rate, 2),
                'last_failure_time': self.last_failure_time,
                'last_success_time': self.last_success_time,
                'request_history_size': len(self.request_history),
                'thresholds': {
                    'failure_threshold': self.failure_threshold,
                    'recovery_timeout': self.recovery_timeout,
                    'success_threshold': self.success_threshold,
                    'failure_rate_threshold': self.failure_rate_threshold
                }
            }

class RetryStrategy:
    """Advanced retry strategy with exponential backoff and jitter"""
    
    def __init__(self, 
                 max_attempts: int = 3,
                 base_delay: float = 0.1,
                 max_delay: float = 2.0,
                 backoff_multiplier: float = 2.0,
                 jitter: bool = True):
        
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
    
    def execute(self, func, *args, **kwargs):
        """Execute function with retry logic"""
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt == self.max_attempts - 1:
                    # Last attempt, don't delay
                    break
                
                # Calculate delay with exponential backoff
                delay = min(self.base_delay * (self.backoff_multiplier ** attempt), self.max_delay)
                
                # Add jitter to prevent thundering herd
                if self.jitter:
                    delay *= (0.5 + random.random() * 0.5)
                
                logger.debug(f"Retry attempt {attempt + 1}/{self.max_attempts} after {delay:.3f}s delay: {e}")
                time.sleep(delay)
        
        raise last_exception

class InMemoryFallbackCache:
    """Memory-efficient LRU cache with TTL for Redis fallback"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        
        self._cache = OrderedDict()
        self._expiry = {}
        self._lock = threading.RLock()
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        
        logger.info(f"In-memory fallback cache initialized: max_size={max_size}, ttl={default_ttl}s")
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self._lock:
            self._cleanup_expired()
            
            if key in self._cache and key not in self._expiry:  # No TTL
                value = self._cache.pop(key)
                self._cache[key] = value  # Move to end (LRU)
                self.hits += 1
                return value
            
            elif key in self._cache and key in self._expiry:
                if time.time() <= self._expiry[key]:
                    value = self._cache.pop(key)
                    self._cache[key] = value  # Move to end (LRU)
                    self.hits += 1
                    return value
                else:
                    # Expired
                    del self._cache[key]
                    del self._expiry[key]
            
            self.misses += 1
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL"""
        with self._lock:
            # Remove if exists
            if key in self._cache:
                del self._cache[key]
                self._expiry.pop(key, None)
            
            # Evict oldest if at max size
            if len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._expiry.pop(oldest_key, None)
                self.evictions += 1
            
            # Add new entry
            self._cache[key] = value
            
            if ttl is not None:
                self._expiry[key] = time.time() + ttl
            elif self.default_ttl > 0:
                self._expiry[key] = time.time() + self.default_ttl
            
            return True
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._expiry.pop(key, None)
                return True
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired"""
        with self._lock:
            if key not in self._cache:
                return False
            
            if key in self._expiry and time.time() > self._expiry[key]:
                del self._cache[key]
                del self._expiry[key]
                return False
            
            return True
    
    def _cleanup_expired(self):
        """Clean up expired entries"""
        if not self._expiry:
            return
        
        now = time.time()
        expired_keys = [key for key, expiry in self._expiry.items() if now > expiry]
        
        for key in expired_keys:
            self._cache.pop(key, None)
            self._expiry.pop(key, None)
    
    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()
            self._expiry.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            self._cleanup_expired()
            
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate_percent': round(hit_rate, 2),
                'evictions': self.evictions,
                'entries_with_ttl': len(self._expiry)
            }

class EnterpriseRedisClient:
    """Enterprise-grade Redis client with comprehensive resilience patterns
    
    Features:
    - Advanced circuit breaker with failure rate analysis
    - Intelligent retry with exponential backoff and jitter
    - Connection pooling with health monitoring
    - Memory-efficient LRU fallback cache with TTL
    - Rate limiting support with fallback
    - Comprehensive metrics and monitoring
    - Zero-downtime operations during Redis outages
    - Connection lifecycle management
    - Thread-safe operations
    
    Designed for maritime operations requiring high availability
    """""
    
    def __init__(self, 
                 redis_url: Optional[str] = None,
                 max_connections: int = 20,
                 connection_timeout: int = 5,
                 socket_timeout: int = 5,
                 health_check_interval: int = 30,
                 fallback_cache_size: int = 1000,
                 fallback_ttl: int = 300,
                 retry_strategy: Optional[RetryStrategy] = None):
        
        # Configuration
        self.redis_url = redis_url
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.socket_timeout = socket_timeout
        self.health_check_interval = health_check_interval
        
        # Core components
        self._client: Optional[redis.Redis] = None
        self._circuit_breaker = AdvancedCircuitBreaker()
        self._connection_pool = None
        self._fallback_cache = InMemoryFallbackCache(fallback_cache_size, fallback_ttl)
        self._retry_strategy = retry_strategy or RetryStrategy()
        
        # Metrics and monitoring
        self._metrics = RedisMetrics()
        self._last_health_check = 0
        self._health_status = {'healthy': False, 'last_check': 0, 'error': None}
        
        # Thread safety
        self._initialization_lock = threading.Lock()
        self._metrics_lock = threading.Lock()
        
        # State tracking
        self._initialized = False
        self._initializing = False
        
        # Circuit breaker callbacks
        self._circuit_breaker.add_state_change_callback(self._on_circuit_breaker_state_change)
        
        logger.info(f"EnterpriseRedisClient initializing: url={'***' if redis_url else 'None'}, "
                   f"max_conn={max_connections}, timeout={connection_timeout}s")
        
        if redis_url:
            self._initialize_client()
        else:
            logger.warning("⚠️  No Redis URL provided - using in-memory fallback only")
    
    def _initialize_client(self):
        """Initialize Redis client with connection pool and health monitoring"""
        if self._initializing:
            return
            
        with self._initialization_lock:
            if self._initialized or self._initializing:
                return
            
            self._initializing = True
            
            try:
                logger.info("🔄 Initializing Redis connection pool...")
                
                # Parse Redis URL and configure connection pool
                pool_kwargs = {
                    'max_connections': self.max_connections,
                    'retry_on_timeout': True,
                    'socket_connect_timeout': self.connection_timeout,
                    'socket_timeout': self.socket_timeout,
                    'health_check_interval': self.health_check_interval,
                    'socket_keepalive': True,
                    'socket_keepalive_options': {},
                }
                
                # Handle SSL for secure Redis connections
                if self.redis_url and 'rediss://' in self.redis_url:
                    pool_kwargs['ssl_cert_reqs'] = None
                    pool_kwargs['ssl_check_hostname'] = False
                
                self._connection_pool = redis.ConnectionPool.from_url(
                    self.redis_url,
                    **pool_kwargs
                )
                
                self._client = redis.Redis(
                    connection_pool=self._connection_pool,
                    decode_responses=False,  # Keep binary for compatibility
                    retry_on_error=[redis.ConnectionError, redis.TimeoutError],
                    retry=redis.Retry(retries=2, supported_errors=[redis.ConnectionError])
                )
                
                # Test connection with timeout
                test_start = time.time()
                self._client.ping()
                connection_time = (time.time() - test_start) * 1000
                
                self._initialized = True
                self._update_health_status(True, None)
                
                with self._metrics_lock:
                    self._metrics.connection_pool_size = self.max_connections
                    self._metrics.last_success_time = time.time()
                
                logger.info(f"✅ Redis client initialized successfully "
                           f"(connection_time={connection_time:.1f}ms, pool_size={self.max_connections})")
                
            except redis.AuthenticationError as e:
                error_msg = f"Redis authentication failed: {e}"
                logger.error(f"❌ {error_msg}")
                self._update_health_status(False, error_msg)
                self._client = None
                
            except redis.ConnectionError as e:
                error_msg = f"Redis connection failed: {e}"
                logger.error(f"❌ {error_msg}")
                self._update_health_status(False, error_msg)
                self._client = None
                
            except Exception as e:
                error_msg = f"Redis initialization failed: {e}"
                logger.error(f"❌ {error_msg}")
                self._update_health_status(False, error_msg)
                self._client = None
                
            finally:
                self._initializing = False
    
    def _update_health_status(self, healthy: bool, error: Optional[str]):
        """Update Redis health status"""
        self._health_status = {
            'healthy': healthy,
            'last_check': time.time(),
            'error': error
        }
        
        with self._metrics_lock:
            if healthy:
                self._metrics.last_success_time = time.time()
            else:
                self._metrics.last_failure_time = time.time()
    
    def _on_circuit_breaker_state_change(self, old_state: CircuitBreakerState, new_state: CircuitBreakerState):
        """Handle circuit breaker state changes"""
        logger.info(f"🔄 Circuit breaker state changed: {old_state.value} -> {new_state.value}")
        
        with self._metrics_lock:
            if new_state == CircuitBreakerState.OPEN:
                self._metrics.circuit_breaker_trips += 1
    
    def _execute_with_fallback(self, operation_name: str, operation_func: Callable, *args, **kwargs) -> Any:
        """Execute Redis operation with comprehensive fallback and retry logic"""
        start_time = time.time()
        
        # Update metrics
        with self._metrics_lock:
            self._metrics.total_requests += 1
        
        # If no client, use fallback immediately
        if not self._client or not self._initialized:
            logger.debug(f"No Redis client available, using fallback for {operation_name}")
            with self._metrics_lock:
                self._metrics.fallback_hits += 1
            return self._fallback_operation(operation_name, *args, **kwargs)
        
        # Try Redis with circuit breaker and retry
        try:
            result = self._retry_strategy.execute(
                lambda: self._circuit_breaker.call(operation_func)
            )
            
            # Update success metrics
            execution_time = (time.time() - start_time) * 1000
            with self._metrics_lock:
                self._metrics.successful_requests += 1
                # Update rolling average response time
                if self._metrics.avg_response_time_ms == 0:
                    self._metrics.avg_response_time_ms = execution_time
                else:
                    self._metrics.avg_response_time_ms = (
                        self._metrics.avg_response_time_ms * 0.9 + execution_time * 0.1
                    )
            
            return result
            
        except (redis.ConnectionError, redis.TimeoutError, redis.AuthenticationError) as e:
            logger.warning(f"Redis {operation_name} failed: {e}, using fallback")
            
            with self._metrics_lock:
                self._metrics.failed_requests += 1
                self._metrics.fallback_hits += 1
            
            return self._fallback_operation(operation_name, *args, **kwargs)
            
        except Exception as e:
            logger.error(f"Unexpected error in Redis {operation_name}: {e}, using fallback")
            
            with self._metrics_lock:
                self._metrics.failed_requests += 1
                self._metrics.fallback_hits += 1
            
            return self._fallback_operation(operation_name, *args, **kwargs)
    
    def _fallback_operation(self, operation_name: str, *args, **kwargs) -> Any:
        """Handle operations using intelligent in-memory fallback"""
        try:
            if operation_name in ['set', 'setex']:
                if len(args) >= 2:
                    key, value = args[0], args[1]
                    ttl = kwargs.get('ex') or kwargs.get('ttl')
                    
                    # Handle setex format (key, ttl, value)
                    if operation_name == 'setex' and len(args) >= 3:
                        key, ttl, value = args[0], args[1], args[2]
                    
                    return self._fallback_cache.set(key, value, ttl)
                return False
                
            elif operation_name == 'get':
                if len(args) >= 1:
                    key = args[0]
                    return self._fallback_cache.get(key)
                return None
                
            elif operation_name in ['delete', 'del']:
                if len(args) >= 1:
                    key = args[0]
                    return 1 if self._fallback_cache.delete(key) else 0
                return 0
                
            elif operation_name == 'exists':
                if len(args) >= 1:
                    key = args[0]
                    return 1 if self._fallback_cache.exists(key) else 0
                return 0
                
            elif operation_name == 'ping':
                return False  # Indicate Redis is not available but fallback is working
                
            elif operation_name in ['incr', 'incrby']:
                if len(args) >= 1:
                    key = args[0]
                    increment = args[1] if len(args) > 1 else 1
                    
                    current_value = self._fallback_cache.get(key) or b'0'
                    if isinstance(current_value, bytes):
                        current_value = current_value.decode('utf-8')
                    
                    try:
                        new_value = int(current_value) + increment
                        self._fallback_cache.set(key, str(new_value).encode('utf-8'))
                        return new_value
                    except ValueError:
                        # Value is not an integer
                        return None
                return None
                
            elif operation_name == 'expire':
                if len(args) >= 2:
                    key, ttl = args[0], args[1]
                    if self._fallback_cache.exists(key):
                        value = self._fallback_cache.get(key)
                        return self._fallback_cache.set(key, value, ttl)
                return False
                
            elif operation_name in ['hget', 'hset', 'hdel', 'hexists']:
                # Simple hash operations using JSON encoding
                if operation_name == 'hset' and len(args) >= 3:
                    hash_key, field, value = args[0], args[1], args[2]
                    hash_data = self._fallback_cache.get(hash_key) or b'{}'
                    if isinstance(hash_data, bytes):
                        hash_data = hash_data.decode('utf-8')
                    
                    try:
                        hash_dict = json.loads(hash_data)
                        hash_dict[field] = value
                        self._fallback_cache.set(hash_key, json.dumps(hash_dict).encode('utf-8'))
                        return 1
                    except json.JSONDecodeError:
                        return 0
                        
                elif operation_name == 'hget' and len(args) >= 2:
                    hash_key, field = args[0], args[1]
                    hash_data = self._fallback_cache.get(hash_key)
                    if hash_data:
                        if isinstance(hash_data, bytes):
                            hash_data = hash_data.decode('utf-8')
                        try:
                            hash_dict = json.loads(hash_data)
                            return hash_dict.get(field)
                        except json.JSONDecodeError:
                            pass
                    return None
                    
            # Default: log unknown operation and return None
            logger.debug(f"Unsupported fallback operation: {operation_name}")
            return None
            
        except Exception as e:
            logger.error(f"Fallback operation {operation_name} failed: {e}")
            return None
    
    def set(self, key: str, value: Any, ex: Optional[int] = None, nx: bool = False, xx: bool = False) -> bool:
        """Set key-value with optional expiration and conditions"""
        def _set_operation():
            kwargs = {}
            if ex is not None:
                kwargs['ex'] = ex
            if nx:
                kwargs['nx'] = nx
            if xx:
                kwargs['xx'] = xx
            return self._client.set(key, value, **kwargs)
        
        result = self._execute_with_fallback('set', _set_operation, key, value, ex=ex, nx=nx, xx=xx)
        return bool(result)
    
    def get(self, key: str) -> Optional[Any]:
        """Get value by key"""
        def _get_operation():
            return self._client.get(key)
        
        return self._execute_with_fallback('get', _get_operation, key)
    
    def delete(self, *keys: str) -> int:
        """Delete one or more keys"""
        def _delete_operation():
            return self._client.delete(*keys)
        
        if len(keys) == 1:
            result = self._execute_with_fallback('delete', _delete_operation, keys[0])
        else:
            # For multiple keys, try each individually in fallback
            result = 0
            for key in keys:
                def _single_delete():
                    return self._client.delete(key)
                if self._execute_with_fallback('delete', _single_delete, key):
                    result += 1
        
        return result or 0
    
    def exists(self, *keys: str) -> int:
        """Check if one or more keys exist"""
        def _exists_operation():
            return self._client.exists(*keys)
        
        if len(keys) == 1:
            result = self._execute_with_fallback('exists', _exists_operation, keys[0])
            return int(bool(result))
        else:
            # For multiple keys, check each individually in fallback
            count = 0
            for key in keys:
                def _single_exists():
                    return self._client.exists(key)
                if self._execute_with_fallback('exists', _single_exists, key):
                    count += 1
            return count
    
    def incr(self, key: str, amount: int = 1) -> int:
        """Increment the value of key by amount"""
        def _incr_operation():
            if amount == 1:
                return self._client.incr(key)
            else:
                return self._client.incrby(key, amount)
        
        result = self._execute_with_fallback('incr', _incr_operation, key, amount)
        return result or 0
    
    def expire(self, key: str, time: int) -> bool:
        """Set TTL for key"""
        def _expire_operation():
            return self._client.expire(key, time)
        
        result = self._execute_with_fallback('expire', _expire_operation, key, time)
        return bool(result)
    
    def ttl(self, key: str) -> int:
        """Get TTL for key"""
        def _ttl_operation():
            return self._client.ttl(key)
        
        if not self._client or not self._initialized:
            # Fallback doesn't support TTL queries accurately
            return -1 if self._fallback_cache.exists(key) else -2
        
        try:
            return self._circuit_breaker.call(_ttl_operation)
        except:
            return -1 if self._fallback_cache.exists(key) else -2
    
    # Hash operations
    def hget(self, name: str, key: str) -> Optional[Any]:
        """Get field from hash"""
        def _hget_operation():
            return self._client.hget(name, key)
        
        return self._execute_with_fallback('hget', _hget_operation, name, key)
    
    def hset(self, name: str, key: str, value: Any) -> int:
        """Set field in hash"""
        def _hset_operation():
            return self._client.hset(name, key, value)
        
        result = self._execute_with_fallback('hset', _hset_operation, name, key, value)
        return result or 0
    
    def hdel(self, name: str, *keys: str) -> int:
        """Delete fields from hash"""
        def _hdel_operation():
            return self._client.hdel(name, *keys)
        
        result = self._execute_with_fallback('hdel', _hdel_operation, name, *keys)
        return result or 0
    
    def hexists(self, name: str, key: str) -> bool:
        """Check if field exists in hash"""
        def _hexists_operation():
            return self._client.hexists(name, key)
        
        result = self._execute_with_fallback('hexists', _hexists_operation, name, key)
        return bool(result)
    
    def ping(self) -> bool:
        """Health check ping with enhanced diagnostics"""
        if not self._client or not self._initialized:
            logger.debug("Ping failed: Redis client not initialized")
            return False
        
        try:
            start_time = time.time()
            result = self._circuit_breaker.call(self._client.ping)
            ping_time = (time.time() - start_time) * 1000
            
            self._update_health_status(True, None)
            logger.debug(f"Redis ping successful ({ping_time:.1f}ms)")
            return True
            
        except redis.ConnectionError as e:
            error_msg = f"Redis connection error during ping: {e}"
            logger.warning(error_msg)
            self._update_health_status(False, error_msg)
            return False
            
        except Exception as e:
            error_msg = f"Redis ping failed: {e}"
            logger.warning(error_msg)
            self._update_health_status(False, error_msg)
            return False
    
    def get_info(self, section: Optional[str] = None) -> Dict[str, Any]:
        """Get comprehensive Redis server and client information"""
        base_info = {
            "client_status": "unavailable" if not self._client else "available",
            "fallback_active": True,
            "circuit_breaker": self._circuit_breaker.get_stats(),
            "metrics": asdict(self._metrics),
            "fallback_cache": self._fallback_cache.get_stats(),
            "health": self._health_status.copy()
        }
        
        if not self._client or not self._initialized:
            base_info["status"] = "client_unavailable"
            return base_info
        
        try:
            # Get Redis server info
            redis_info = self._circuit_breaker.call(
                lambda: self._client.info(section) if section else self._client.info()
            )
            
            server_info = {
                "status": "connected",
                "redis_version": redis_info.get("redis_version", "unknown"),
                "redis_mode": redis_info.get("redis_mode", "unknown"),
                "used_memory_human": redis_info.get("used_memory_human", "unknown"),
                "used_memory_peak_human": redis_info.get("used_memory_peak_human", "unknown"),
                "connected_clients": redis_info.get("connected_clients", 0),
                "total_commands_processed": redis_info.get("total_commands_processed", 0),
                "keyspace_hits": redis_info.get("keyspace_hits", 0),
                "keyspace_misses": redis_info.get("keyspace_misses", 0),
                "uptime_in_seconds": redis_info.get("uptime_in_seconds", 0),
            }
            
            # Calculate hit rate
            hits = server_info["keyspace_hits"]
            misses = server_info["keyspace_misses"]
            if hits + misses > 0:
                server_info["hit_rate_percent"] = round((hits / (hits + misses)) * 100, 2)
            else:
                server_info["hit_rate_percent"] = 0.0
            
            base_info.update(server_info)
            
        except Exception as e:
            base_info.update({
                "status": "error",
                "last_error": str(e),
                "error_time": time.time()
            })
            logger.warning(f"Failed to get Redis info: {e}")
        
        return base_info
    
    def cleanup_fallback_cache(self) -> int:
        """Clean up expired entries in fallback cache"""
        initial_size = len(self._fallback_cache._cache)
        self._fallback_cache._cleanup_expired()
        final_size = len(self._fallback_cache._cache)
        
        cleaned_count = initial_size - final_size
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired fallback cache entries")
        
        return cleaned_count

    def reconnect(self, force: bool = False) -> bool:
        """Attempt to reconnect to Redis"""
        if not self.redis_url:
            logger.warning("Cannot reconnect: No Redis URL configured")
            return False
        
        if not force and self._initialized and self.ping():
            logger.info("Redis connection already healthy, skipping reconnect")
            return True
        
        logger.info("🔄 Attempting Redis reconnection...")
        
        # Close existing connection
        self.close()
        
        # Reset circuit breaker if forced
        if force:
            self._circuit_breaker.force_close("Manual reconnection")
        
        # Reinitialize
        self._initialized = False
        self._initialize_client()
        
        success = self._initialized and self.ping()
        if success:
            logger.info("✅ Redis reconnection successful")
        else:
            logger.error("❌ Redis reconnection failed")
        
        return success
    
    def close(self):
        """Close Redis connection and cleanup resources"""
        logger.info("🔄 Closing Redis connection...")
        
        if self._connection_pool:
            try:
                self._connection_pool.disconnect()
                logger.debug("Connection pool disconnected")
            except Exception as e:
                logger.warning(f"Error disconnecting connection pool: {e}")
        
        self._client = None
        self._connection_pool = None
        self._initialized = False
        
        logger.info("✅ Redis connection closed")
    
    def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check with diagnostics"""
        now = time.time()
        
        # Skip frequent health checks
        if now - self._last_health_check < 5:  # 5 seconds minimum interval
            return self._health_status.copy()
        
        self._last_health_check = now
        
        health_data = {
            'redis_available': False,
            'response_time_ms': None,
            'circuit_breaker_state': self._circuit_breaker.state.value,
            'connection_pool_available': self._connection_pool is not None,
            'fallback_active': True,
            'last_error': self._health_status.get('error'),
            'uptime_check': now
        }
        
        if self._client and self._initialized:
            try:
                start_time = time.time()
                ping_result = self._client.ping()
                response_time = (time.time() - start_time) * 1000
                
                health_data.update({
                    'redis_available': ping_result,
                    'response_time_ms': round(response_time, 2),
                    'last_error': None
                })
                
                self._update_health_status(True, None)
                
                # Check connection pool stats if available
                if self._connection_pool:
                    pool_stats = {
                        'max_connections': self._connection_pool.max_connections,
                        'created_connections': getattr(self._connection_pool, 'created_connections', 0),
                    }
                    health_data['connection_pool'] = pool_stats
                
            except Exception as e:
                error_msg = str(e)
                health_data['last_error'] = error_msg
                self._update_health_status(False, error_msg)
                logger.debug(f"Health check failed: {error_msg}")
        
        # Add fallback cache stats
        health_data['fallback_cache'] = self._fallback_cache.get_stats()
        
        return health_data
    
    def get_comprehensive_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics for monitoring and alerting"""
        with self._metrics_lock:
            metrics_data = asdict(self._metrics)
        
        # Add circuit breaker stats
        metrics_data['circuit_breaker'] = self._circuit_breaker.get_stats()
        
        # Add fallback cache stats
        metrics_data['fallback_cache'] = self._fallback_cache.get_stats()
        
        # Add health information
        metrics_data['health'] = self.health_check()
        
        # Connection pool information
        if self._connection_pool:
            metrics_data['connection_pool'] = {
                'max_connections': self._connection_pool.max_connections,
                'created_connections': getattr(self._connection_pool, 'created_connections', 0)
            }
        
        # Calculate derived metrics
        metrics_data['derived'] = {
            'availability_percent': 100.0 - metrics_data['failure_rate'],
            'fallback_dependency_percent': (
                (metrics_data['fallback_hits'] / max(metrics_data['total_requests'], 1)) * 100
            ),
            'avg_response_time_category': self._categorize_response_time(metrics_data['avg_response_time_ms'])
        }
        
        return metrics_data
    
    def _categorize_response_time(self, response_time_ms: float) -> str:
        """Categorize response time for monitoring"""
        if response_time_ms < 1:
            return 'excellent'
        elif response_time_ms < 5:
            return 'good'
        elif response_time_ms < 10:
            return 'acceptable'
        elif response_time_ms < 50:
            return 'slow'
        else:
            return 'critical'
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
    
    def __del__(self):
        """Destructor - cleanup resources"""
        try:
            self.close()
        except:
            pass


# Global Redis client instance with thread-safe initialization
_redis_client: Optional[EnterpriseRedisClient] = None
_client_lock = threading.Lock()

def get_redis_client(redis_url: Optional[str] = None, **kwargs) -> EnterpriseRedisClient:
    """Get global Redis client instance with thread-safe lazy initialization"""
    global _redis_client
    
    if _redis_client is None:
        with _client_lock:
            if _redis_client is None:  # Double-check pattern
                logger.info("Initializing global Redis client...")
                _redis_client = EnterpriseRedisClient(redis_url, **kwargs)
                logger.info("✅ Global Redis client initialized")
    
    return _redis_client

def reset_redis_client():
    """Reset global Redis client (for testing or reconfiguration)"""
    global _redis_client
    
    with _client_lock:
        if _redis_client:
            _redis_client.close()
        _redis_client = None
        logger.info("Global Redis client reset")

def redis_health_check(detailed: bool = False) -> Dict[str, Any]:
    """Perform comprehensive Redis health check for monitoring and alerting"""
    try:
        client = get_redis_client()
        
        # Basic health check
        health_data = client.health_check()
        
        if detailed:
            # Add comprehensive metrics for detailed monitoring
            health_data['comprehensive_metrics'] = client.get_comprehensive_metrics()
            
            # Add system-level information
            health_data['system'] = {
                'timestamp': time.time(),
                'client_type': 'EnterpriseRedisClient',
                'fallback_enabled': True,
                'circuit_breaker_enabled': True
            }
        
        return health_data
        
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            'redis_available': False,
            'error': str(e),
            'fallback_active': True,
            'timestamp': time.time()
        }

# Rate limiting support functions
def create_rate_limit_key(identifier: str, window: str = "hour") -> str:
    """Create a standardized rate limit key"""
    timestamp = int(time.time())
    
    if window == "minute":
        window_time = timestamp // 60
    elif window == "hour":
        window_time = timestamp // 3600
    elif window == "day":
        window_time = timestamp // 86400
    else:
        window_time = timestamp
    
    return f"rate_limit:{identifier}:{window}:{window_time}"

def check_rate_limit(client: EnterpriseRedisClient, 
                    identifier: str, 
                    limit: int, 
                    window: str = "hour") -> Dict[str, Any]:
    """Check and enforce rate limiting with fallback support"""
    key = create_rate_limit_key(identifier, window)
    
    try:
        current_count = client.get(key)
        if current_count is None:
            current_count = 0
        else:
            if isinstance(current_count, bytes):
                current_count = current_count.decode('utf-8')
            current_count = int(current_count)
        
        if current_count >= limit:
            return {
                'allowed': False,
                'current_count': current_count,
                'limit': limit,
                'reset_time': _get_window_reset_time(window)
            }
        
        # Increment counter
        new_count = client.incr(key)
        
        # Set expiry for the key if it's new
        if new_count == 1:
            client.expire(key, _get_window_seconds(window))
        
        return {
            'allowed': True,
            'current_count': new_count,
            'limit': limit,
            'remaining': max(0, limit - new_count)
        }
        
    except Exception as e:
        logger.error(f"Rate limiting check failed: {e}")
        # Fail open - allow request if rate limiting fails
        return {
            'allowed': True,
            'error': str(e),
            'fallback_mode': True
        }

def _get_window_seconds(window: str) -> int:
    """Get window duration in seconds"""
    windows = {
        'minute': 60,
        'hour': 3600,
        'day': 86400
    }
    return windows.get(window, 3600)

def _get_window_reset_time(window: str) -> int:
    """Get timestamp when the current window resets"""
    now = int(time.time())
    window_seconds = _get_window_seconds(window)
    
    if window == "minute":
        return (now // 60 + 1) * 60
    elif window == "hour":
        return (now // 3600 + 1) * 3600
    elif window == "day":
        return (now // 86400 + 1) * 86400
    else:
        return now + window_seconds

# Monitoring and alerting functions
def get_redis_alerts(client: Optional[EnterpriseRedisClient] = None) -> List[Dict[str, Any]]:
    """Generate alerts based on Redis health and metrics"""
    if client is None:
        client = get_redis_client()
    
    alerts = []
    metrics = client.get_comprehensive_metrics()
    
    # Circuit breaker alerts
    cb_state = metrics['circuit_breaker']['state']
    if cb_state == 'open':
        alerts.append({
            'severity': 'critical',
            'type': 'circuit_breaker_open',
            'message': 'Redis circuit breaker is OPEN - Redis is unavailable',
            'details': metrics['circuit_breaker']
        })
    elif cb_state == 'half_open':
        alerts.append({
            'severity': 'warning',
            'type': 'circuit_breaker_testing',
            'message': 'Redis circuit breaker is testing recovery (HALF_OPEN)',
            'details': metrics['circuit_breaker']
        })
    
    # Failure rate alerts
    failure_rate = metrics['failure_rate']
    if failure_rate > 50:
        alerts.append({
            'severity': 'critical',
            'type': 'high_failure_rate',
            'message': f'Redis failure rate is {failure_rate:.1f}% (>50%)',
            'details': {'failure_rate': failure_rate}
        })
    elif failure_rate > 20:
        alerts.append({
            'severity': 'warning',
            'type': 'elevated_failure_rate',
            'message': f'Redis failure rate is {failure_rate:.1f}% (>20%)',
            'details': {'failure_rate': failure_rate}
        })
    
    # Response time alerts
    response_time = metrics['avg_response_time_ms']
    if response_time > 100:
        alerts.append({
            'severity': 'warning',
            'type': 'slow_response_time',
            'message': f'Redis average response time is {response_time:.1f}ms (>100ms)',
            'details': {'response_time_ms': response_time}
        })
    
    # Fallback dependency alerts
    fallback_percent = metrics['derived']['fallback_dependency_percent']
    if fallback_percent > 80:
        alerts.append({
            'severity': 'warning',
            'type': 'high_fallback_dependency',
            'message': f'{fallback_percent:.1f}% of requests using fallback cache',
            'details': {'fallback_percent': fallback_percent}
        })
    
    return alerts

# Utility decorators
def redis_operation_timeout(timeout_seconds: int = 5):
    """Decorator to add timeout to Redis operations"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            def target():
                return func(*args, **kwargs)
            
            result = [None]
            exception = [None]
            
            def run_target():
                try:
                    result[0] = target()
                except Exception as e:
                    exception[0] = e
            
            thread = threading.Thread(target=run_target)
            thread.daemon = True
            thread.start()
            thread.join(timeout_seconds)
            
            if thread.is_alive():
                logger.warning(f"Redis operation {func.__name__} timed out after {timeout_seconds}s")
                raise redis.TimeoutError(f"Operation timed out after {timeout_seconds}s")
            
            if exception[0]:
                raise exception[0]
            
            return result[0]
        return wrapper
    return decorator

# Export main classes and functions
__all__ = [
    'EnterpriseRedisClient',
    'AdvancedCircuitBreaker', 
    'CircuitBreakerState',
    'RetryStrategy',
    'InMemoryFallbackCache',
    'RedisMetrics',
    'get_redis_client',
    'reset_redis_client',
    'redis_health_check',
    'check_rate_limit',
    'get_redis_alerts',
    'redis_operation_timeout'
]