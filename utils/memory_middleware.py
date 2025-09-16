"""
Memory Leak Prevention Middleware for Stevedores Dashboard 3.0
Monitors and prevents memory leaks during request/response cycle
"""

import gc
import time
import logging
from functools import wraps
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from flask import request, g, current_app, jsonify
from werkzeug.exceptions import ServiceUnavailable

from utils.memory_monitor import get_memory_monitor, memory_limit

logger = logging.getLogger(__name__)

class MemoryMiddleware:
    """Memory leak prevention middleware for Flask applications"""
    
    def __init__(self, app=None):
        self.app = app
        self.request_memory_tracking = {}
        self.high_memory_requests = []
        self.gc_interval = 50  # Trigger GC every 50 requests
        self.request_count = 0
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize middleware with Flask app"""
        # Register request hooks
        app.before_request(self.before_request)
        app.after_request(self.after_request)
        app.teardown_appcontext(self.teardown_request)
        
        # Memory pressure protection
        app.before_request(self.check_memory_pressure)
        
        logger.info("Memory middleware initialized")
    
    def before_request(self):
        """Execute before each request"""
        try:
            # Track request start time
            g.request_start_time = time.time()
            
            # Get initial memory state
            monitor = get_memory_monitor()
            if monitor:
                initial_usage = monitor.get_memory_usage()
                g.initial_memory = initial_usage.get("process", {}).get("rss_mb", 0)
                g.initial_objects = initial_usage.get("gc", {}).get("objects", 0)
            else:
                g.initial_memory = 0
                g.initial_objects = 0
            
            # Track request details
            g.request_id = f"{int(time.time() * 1000)}_{id(request)}"
            
            # Log high-memory requests for debugging
            if hasattr(g, 'initial_memory') and g.initial_memory > 300:  # > 300MB
                logger.warning(f"Request starting with high memory: {g.initial_memory:.1f}MB "
                              f"[{request.method} {request.path}]")
            
        except Exception as e:
            logger.error(f"Memory middleware before_request error: {e}")
    
    def after_request(self, response):
        """Execute after each request"""
        try:
            # Calculate request duration
            if hasattr(g, 'request_start_time'):
                duration_ms = (time.time() - g.request_start_time) * 1000
                
                # Get final memory state
                monitor = get_memory_monitor()
                if monitor:
                    final_usage = monitor.get_memory_usage()
                    final_memory = final_usage.get("process", {}).get("rss_mb", 0)
                    final_objects = final_usage.get("gc", {}).get("objects", 0)
                    
                    # Calculate memory delta
                    initial_memory = getattr(g, 'initial_memory', 0)
                    initial_objects = getattr(g, 'initial_objects', 0)
                    
                    memory_delta = final_memory - initial_memory
                    objects_delta = final_objects - initial_objects
                    
                    # Log memory-intensive requests
                    if memory_delta > 10 or objects_delta > 1000 or duration_ms > 5000:
                        logger.info(f"Memory-intensive request: {request.method} {request.path} "
                                   f"({duration_ms:.0f}ms, +{memory_delta:.1f}MB, +{objects_delta} objects)")
                    
                    # Track high-memory requests
                    if memory_delta > 20:  # > 20MB increase
                        self.high_memory_requests.append({
                            'timestamp': datetime.now().isoformat(),
                            'path': request.path,
                            'method': request.method,
                            'memory_delta': memory_delta,
                            'objects_delta': objects_delta,
                            'duration_ms': duration_ms
                        })
                        
                        # Keep only recent high-memory requests
                        if len(self.high_memory_requests) > 20:
                            self.high_memory_requests = self.high_memory_requests[-20:]
            
            # Periodic garbage collection
            self.request_count += 1
            if self.request_count >= self.gc_interval:
                collected = gc.collect()
                if collected > 0:
                    logger.debug(f"Periodic GC after {self.request_count} requests: {collected} objects collected")
                self.request_count = 0
            
            return response
            
        except Exception as e:
            logger.error(f"Memory middleware after_request error: {e}")
            return response
    
    def teardown_request(self, exception=None):
        """Clean up after request (always executed)"""
        try:
            # Clean up request-specific memory tracking
            if hasattr(g, 'request_id'):
                self.request_memory_tracking.pop(g.request_id, None)
            
            # Force cleanup on exceptions that might leave hanging references
            if exception:
                logger.warning(f"Request exception cleanup: {exception}")
                gc.collect()
                
        except Exception as e:
            logger.error(f"Memory middleware teardown error: {e}")
    
    def check_memory_pressure(self):
        """Check memory pressure before processing request"""
        try:
            monitor = get_memory_monitor()
            if not monitor:
                return
            
            usage = monitor.get_memory_usage()
            memory_percent = usage.get("container", {}).get("percent", 0)
            
            # Reject new requests if memory is critically high
            if memory_percent >= 92:  # 92% threshold for request rejection
                logger.warning(f"Rejecting request due to critical memory: {memory_percent:.1f}% "
                              f"[{request.method} {request.path}]")
                
                # Return 503 Service Unavailable
                raise ServiceUnavailable(
                    description="Service temporarily unavailable due to high memory usage",
                    response=jsonify({
                        "error": "Service temporarily unavailable",
                        "reason": "high_memory_usage",
                        "memory_percent": round(memory_percent, 1),
                        "retry_after": 30,
                        "timestamp": datetime.now().isoformat()
                    })
                )
            
            # Log warnings for high memory requests
            elif memory_percent >= 85:
                logger.warning(f"Processing request with high memory: {memory_percent:.1f}% "
                              f"[{request.method} {request.path}]")
                
        except ServiceUnavailable:
            # Re-raise service unavailable
            raise
        except Exception as e:
            logger.error(f"Memory pressure check error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get middleware statistics"""
        try:
            return {
                "request_count": self.request_count,
                "gc_interval": self.gc_interval,
                "high_memory_requests": len(self.high_memory_requests),
                "recent_high_memory": self.high_memory_requests[-5:] if self.high_memory_requests else [],
                "active_tracking": len(self.request_memory_tracking),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting middleware stats: {e}")
            return {"error": str(e)}

# Singleton instance
_memory_middleware: Optional[MemoryMiddleware] = None

def init_memory_middleware(app) -> MemoryMiddleware:
    """Initialize memory middleware singleton"""
    global _memory_middleware
    
    if _memory_middleware is None:
        _memory_middleware = MemoryMiddleware(app)
        logger.info("Memory middleware singleton initialized")
    
    return _memory_middleware

def get_memory_middleware() -> Optional[MemoryMiddleware]:
    """Get memory middleware singleton"""
    return _memory_middleware

# Decorators for memory-aware route handling

def memory_intensive(threshold_mb: float = 50):
    """Decorator to mark routes as memory-intensive and add extra monitoring"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Pre-check memory availability
            monitor = get_memory_monitor()
            if monitor:
                usage = monitor.get_memory_usage()
                available_mb = usage.get("container", {}).get("free_mb", 0)
                
                if available_mb < threshold_mb:
                    logger.warning(f"Insufficient memory for intensive operation: "
                                  f"{available_mb:.1f}MB available < {threshold_mb}MB required")
                    
                    return jsonify({
                        "error": "Insufficient memory for this operation",
                        "required_mb": threshold_mb,
                        "available_mb": round(available_mb, 1),
                        "retry_after": 60
                    }), 503
            
            # Mark as memory intensive in context
            g.memory_intensive = True
            g.memory_threshold = threshold_mb
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

def auto_cleanup(trigger_percent: float = 80):
    """Decorator to automatically trigger cleanup after route execution"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Check if cleanup is needed
            monitor = get_memory_monitor()
            if monitor:
                usage = monitor.get_memory_usage()
                memory_percent = usage.get("container", {}).get("percent", 0)
                
                if memory_percent >= trigger_percent:
                    logger.info(f"Auto-cleanup triggered after {func.__name__}: {memory_percent:.1f}%")
                    collected = gc.collect()
                    if collected > 0:
                        logger.info(f"Auto-cleanup collected {collected} objects")
            
            return result
        
        return wrapper
    return decorator

def memory_track(track_objects: bool = False):
    """Decorator to track memory usage of specific routes"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get initial state
            monitor = get_memory_monitor()
            start_time = time.time()
            
            if monitor:
                initial = monitor.get_memory_usage()
                initial_memory = initial.get("process", {}).get("rss_mb", 0)
                initial_objects = initial.get("gc", {}).get("objects", 0) if track_objects else 0
            else:
                initial_memory = initial_objects = 0
            
            # Execute function
            try:
                result = func(*args, **kwargs)
                
                # Get final state
                if monitor:
                    final = monitor.get_memory_usage()
                    final_memory = final.get("process", {}).get("rss_mb", 0)
                    final_objects = final.get("gc", {}).get("objects", 0) if track_objects else 0
                    
                    # Calculate deltas
                    memory_delta = final_memory - initial_memory
                    objects_delta = final_objects - initial_objects
                    duration = (time.time() - start_time) * 1000
                    
                    # Log tracking info
                    log_msg = f"TRACK {func.__name__}: {duration:.0f}ms, {memory_delta:+.1f}MB"
                    if track_objects:
                        log_msg += f", {objects_delta:+d} objects"
                    
                    if memory_delta > 5 or duration > 1000:  # Log significant changes
                        logger.info(log_msg)
                    else:
                        logger.debug(log_msg)
                
                return result
                
            except Exception as e:
                # Log error with memory state
                if monitor:
                    error_usage = monitor.get_memory_usage()
                    error_memory = error_usage.get("process", {}).get("rss_mb", 0)
                    logger.error(f"ERROR in {func.__name__}: {e} (Memory: {error_memory:.1f}MB)")
                raise
        
        return wrapper
    return decorator