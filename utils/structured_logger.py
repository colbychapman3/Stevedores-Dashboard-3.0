"""
Structured JSON Logging Framework for Stevedores Dashboard 3.0
Production-ready logging with maritime operations focus and Render integration
"""

import os
import json
import logging
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from dataclasses import dataclass, asdict, field
from contextlib import contextmanager
from functools import wraps
import traceback
import uuid

# Maritime-specific imports
import psutil
from flask import g, request, has_request_context


class LogLevel(Enum):
    """Enhanced log levels for maritime operations"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    MARITIME_ALERT = "MARITIME_ALERT"  # Special level for maritime operations
    COMPLIANCE = "COMPLIANCE"  # Regulatory compliance events
    SECURITY = "SECURITY"  # Security-related events


class MaritimeOperationType(Enum):
    """Maritime operation types for structured logging"""
    VESSEL_ARRIVAL = "vessel_arrival"
    VESSEL_DEPARTURE = "vessel_departure"
    CARGO_LOADING = "cargo_loading"
    CARGO_UNLOADING = "cargo_unloading"
    CARGO_TALLY = "cargo_tally"
    DOCUMENT_PROCESSING = "document_processing"
    CUSTOMS_CLEARANCE = "customs_clearance"
    SECURITY_INSPECTION = "security_inspection"
    PORT_STATE_CONTROL = "port_state_control"
    ENVIRONMENTAL_MONITORING = "environmental_monitoring"
    CREW_CHANGE = "crew_change"
    FUEL_BUNKERING = "fuel_bunkering"
    MAINTENANCE_OPERATION = "maintenance_operation"
    EMERGENCY_RESPONSE = "emergency_response"


class ComponentType(Enum):
    """System component types for logging context"""
    WEB_SERVER = "web_server"
    DATABASE = "database"
    REDIS_CACHE = "redis_cache"
    MEMORY_MONITOR = "memory_monitor"
    CIRCUIT_BREAKER = "circuit_breaker"
    RATE_LIMITER = "rate_limiter"
    AUTH_SYSTEM = "auth_system"
    PWA_SYSTEM = "pwa_system"
    SYNC_ENGINE = "sync_engine"
    DOCUMENT_PROCESSOR = "document_processor"
    AUDIT_SYSTEM = "audit_system"
    HEALTH_MONITOR = "health_monitor"


@dataclass
class LogContext:
    """Structured log context for maritime operations"""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    level: str = "INFO"
    message: str = ""
    component: str = ""
    operation: Optional[str] = None
    maritime_operation: Optional[MaritimeOperationType] = None
    
    # Request context
    request_id: Optional[str] = None
    user_id: Optional[int] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    
    # Maritime context
    vessel_id: Optional[int] = None
    vessel_imo: Optional[str] = None
    voyage_id: Optional[str] = None
    port_code: Optional[str] = None
    berth_id: Optional[str] = None
    cargo_type: Optional[str] = None
    
    # Performance metrics
    duration_ms: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    response_size_bytes: Optional[int] = None
    
    # Error context
    error_type: Optional[str] = None
    error_code: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None
    
    # Business context
    business_impact: Optional[str] = None
    compliance_flags: List[str] = field(default_factory=list)
    security_classification: str = "internal"
    
    # Technical metadata
    deployment_version: Optional[str] = None
    environment: str = "production"
    service_name: str = "stevedores-dashboard"
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    
    # Custom fields
    extra_fields: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        
        # Convert enums to their values
        if self.maritime_operation:
            data['maritime_operation'] = self.maritime_operation.value
        
        # Remove None values to reduce log size
        return {k: v for k, v in data.items() if v is not None and v != [] and v != {}}


class StructuredLogger:
    """Production-ready structured logger for maritime operations"""
    
    def __init__(self, name: str = "stevedores", enable_render_streaming: bool = True):
        self.logger = logging.getLogger(name)
        self.enable_render_streaming = enable_render_streaming
        self.deployment_version = os.getenv('DEPLOYMENT_VERSION', '3.0.6')
        self.environment = os.getenv('FLASK_ENV', 'production')
        
        # Performance optimization
        self.log_buffer = []
        self.buffer_size = int(os.getenv('LOG_BUFFER_SIZE_KB', '256')) * 1024  # Convert KB to bytes
        self.flush_interval = int(os.getenv('LOG_FLUSH_INTERVAL_SECONDS', '10'))
        self.last_flush = time.time()
        self.buffer_lock = threading.Lock()
        
        # Cost optimization settings
        self.sampling_rate = float(os.getenv('LOG_SAMPLING_RATE', '1.0'))
        self.noise_reduction = os.getenv('LOG_NOISE_REDUCTION', 'true').lower() == 'true'
        self.deduplication = os.getenv('LOG_DEDUPLICATION', 'true').lower() == 'true'
        self.dedup_cache = {}  # Simple deduplication cache
        
        # Maritime-specific settings
        self.maritime_logging = os.getenv('LOG_MARITIME_OPERATIONS', 'true').lower() == 'true'
        self.performance_logging = os.getenv('LOG_PERFORMANCE_METRICS', 'true').lower() == 'true'
        self.security_logging = os.getenv('LOG_SECURITY_EVENTS', 'true').lower() == 'true'
        
        self._setup_logger()
        self._start_background_flush()
    
    def _setup_logger(self):
        """Set up the structured logger configuration"""
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Set log level
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.logger.setLevel(getattr(logging, log_level))
        
        # Create JSON formatter for structured logging
        formatter = JsonFormatter()
        
        # Console handler for Render log streaming
        if self.enable_render_streaming:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            console_handler.setLevel(logging.INFO)
            self.logger.addHandler(console_handler)
        
        # File handler for local development/backup
        if self.environment != 'production' or os.getenv('LOCAL_LOG_FILE_ENABLED', 'false').lower() == 'true':
            try:
                log_dir = '/tmp/logs'
                os.makedirs(log_dir, exist_ok=True)
                
                from logging.handlers import RotatingFileHandler
                file_handler = RotatingFileHandler(
                    f'{log_dir}/stevedores_structured.log',
                    maxBytes=50*1024*1024,  # 50MB
                    backupCount=5
                )
                file_handler.setFormatter(formatter)
                file_handler.setLevel(logging.INFO)
                self.logger.addHandler(file_handler)
            except Exception as e:
                print(f"Failed to set up file logging: {e}")
        
        self.logger.info("Structured logging initialized", extra={
            'component': ComponentType.WEB_SERVER.value,
            'deployment_version': self.deployment_version,
            'environment': self.environment
        })
    
    def _start_background_flush(self):
        """Start background thread for buffer flushing"""
        if not os.getenv('LOG_STREAMING_ENABLED', 'true').lower() == 'true':
            return
        
        def flush_worker():
            while True:
                time.sleep(self.flush_interval)
                self._flush_buffer()
        
        flush_thread = threading.Thread(target=flush_worker, daemon=True)
        flush_thread.start()
    
    def _flush_buffer(self):
        """Flush buffered logs"""
        with self.buffer_lock:
            if not self.log_buffer:
                return
            
            # Process buffered logs
            for log_entry in self.log_buffer:
                self.logger.handle(log_entry)
            
            self.log_buffer.clear()
            self.last_flush = time.time()
    
    def _should_sample_log(self) -> bool:
        """Determine if log should be sampled (for cost optimization)"""
        import random
        return random.random() <= self.sampling_rate
    
    def _deduplicate_log(self, log_context: LogContext) -> bool:
        """Check if log should be deduplicated"""
        if not self.deduplication:
            return False
        
        # Create deduplication key
        dedup_key = f"{log_context.component}:{log_context.level}:{log_context.message[:100]}"
        current_time = time.time()
        
        # Check if we've seen this log recently (within 60 seconds)
        if dedup_key in self.dedup_cache:
            last_seen = self.dedup_cache[dedup_key]
            if current_time - last_seen < 60:
                return True  # Skip this log
        
        self.dedup_cache[dedup_key] = current_time
        
        # Clean old entries (simple cleanup)
        if len(self.dedup_cache) > 1000:
            cutoff_time = current_time - 300  # 5 minutes
            self.dedup_cache = {k: v for k, v in self.dedup_cache.items() if v > cutoff_time}
        
        return False
    
    def _get_request_context(self) -> Dict[str, Any]:
        """Extract request context for logging"""
        context = {}
        
        try:
            if has_request_context():
                context.update({
                    'request_id': getattr(g, 'request_id', None) or str(uuid.uuid4())[:8],
                    'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr),
                    'user_agent': request.headers.get('User-Agent'),
                    'endpoint': request.endpoint,
                    'method': request.method,
                })
                
                # Get user context
                if hasattr(g, 'jwt_claims'):
                    context['user_id'] = g.jwt_claims.get('user_id')
                
                # Get session context
                try:
                    from flask import session
                    context['session_id'] = session.get('_id')
                except:
                    pass
        except:
            pass
        
        return context
    
    def _get_performance_context(self) -> Dict[str, Any]:
        """Get performance metrics for logging"""
        if not self.performance_logging:
            return {}
        
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                'memory_usage_mb': memory_info.rss / (1024 * 1024),
                'cpu_usage_percent': process.cpu_percent(),
            }
        except:
            return {}
    
    def log(self, level: LogLevel, message: str, **kwargs):
        """Main logging method with structured context"""
        # Sampling check for cost optimization
        if not self._should_sample_log():
            return
        
        # Create log context
        log_context = LogContext(
            level=level.value,
            message=message,
            deployment_version=self.deployment_version,
            environment=self.environment,
        )
        
        # Add request context
        request_context = self._get_request_context()
        for key, value in request_context.items():
            if hasattr(log_context, key):
                setattr(log_context, key, value)
        
        # Add performance context
        perf_context = self._get_performance_context()
        for key, value in perf_context.items():
            if hasattr(log_context, key):
                setattr(log_context, key, value)
        
        # Add custom fields
        for key, value in kwargs.items():
            if hasattr(log_context, key):
                setattr(log_context, key, value)
            else:
                log_context.extra_fields[key] = value
        
        # Deduplication check
        if self._deduplicate_log(log_context):
            return
        
        # Convert to dict for logging
        log_data = log_context.to_dict()
        
        # Create log record
        log_record = self.logger.makeRecord(
            name=self.logger.name,
            level=getattr(logging, level.value),
            fn='',
            lno=0,
            msg=message,
            args=(),
            exc_info=None,
            extra=log_data
        )
        
        # Buffer or immediate logging based on configuration
        if os.getenv('LOG_STREAMING_ENABLED', 'true').lower() == 'true':
            with self.buffer_lock:
                self.log_buffer.append(log_record)
                
                # Flush if buffer is full or time threshold reached
                buffer_size_bytes = sum(len(str(record.__dict__)) for record in self.log_buffer)
                if (buffer_size_bytes >= self.buffer_size or 
                    time.time() - self.last_flush >= self.flush_interval):
                    self._flush_buffer()
        else:
            self.logger.handle(log_record)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self.log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        if 'error_type' not in kwargs and 'exception' in kwargs:
            exception = kwargs.pop('exception')
            kwargs.update({
                'error_type': type(exception).__name__,
                'error_details': str(exception),
                'stack_trace': ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
            })
        
        self.log(LogLevel.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self.log(LogLevel.CRITICAL, message, **kwargs)
    
    def maritime_alert(self, message: str, maritime_operation: MaritimeOperationType, **kwargs):
        """Log maritime operation alert"""
        if not self.maritime_logging:
            return
        
        kwargs.update({
            'maritime_operation': maritime_operation,
            'business_impact': kwargs.get('business_impact', 'maritime_operations'),
            'compliance_flags': kwargs.get('compliance_flags', ['maritime_compliance'])
        })
        
        self.log(LogLevel.MARITIME_ALERT, message, **kwargs)
    
    def compliance_log(self, message: str, **kwargs):
        """Log compliance-related events"""
        kwargs.update({
            'compliance_flags': kwargs.get('compliance_flags', ['regulatory_compliance']),
            'security_classification': kwargs.get('security_classification', 'restricted')
        })
        
        self.log(LogLevel.COMPLIANCE, message, **kwargs)
    
    def security_log(self, message: str, **kwargs):
        """Log security-related events"""
        if not self.security_logging:
            return
        
        kwargs.update({
            'security_classification': 'restricted',
            'compliance_flags': kwargs.get('compliance_flags', ['security_audit'])
        })
        
        self.log(LogLevel.SECURITY, message, **kwargs)
    
    def performance_log(self, message: str, operation: str, duration_ms: float, **kwargs):
        """Log performance metrics"""
        if not self.performance_logging:
            return
        
        kwargs.update({
            'operation': operation,
            'duration_ms': duration_ms,
            'component': kwargs.get('component', ComponentType.WEB_SERVER.value)
        })
        
        # Determine log level based on performance thresholds
        level = LogLevel.INFO
        if duration_ms > 5000:  # 5 seconds
            level = LogLevel.CRITICAL
        elif duration_ms > 2000:  # 2 seconds
            level = LogLevel.ERROR
        elif duration_ms > 1000:  # 1 second
            level = LogLevel.WARNING
        
        self.log(level, message, **kwargs)


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        # Base log entry
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'logger': record.name,
        }
        
        # Add extra fields from the record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'stack_info', 'exc_info', 'exc_text']:
                log_entry[key] = value
        
        # Handle exceptions
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, default=str, ensure_ascii=False)


# Context managers and decorators
@contextmanager
def maritime_operation_context(operation: MaritimeOperationType, **context):
    """Context manager for maritime operations logging"""
    start_time = time.time()
    operation_id = str(uuid.uuid4())[:8]
    
    logger = get_structured_logger()
    
    # Log operation start
    logger.maritime_alert(
        f"Maritime operation started: {operation.value}",
        maritime_operation=operation,
        operation_id=operation_id,
        **context
    )
    
    try:
        yield operation_id
        
        # Log successful completion
        duration_ms = (time.time() - start_time) * 1000
        logger.maritime_alert(
            f"Maritime operation completed: {operation.value}",
            maritime_operation=operation,
            operation_id=operation_id,
            duration_ms=duration_ms,
            status="success",
            **context
        )
        
    except Exception as e:
        # Log operation failure
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Maritime operation failed: {operation.value}",
            maritime_operation=operation,
            operation_id=operation_id,
            duration_ms=duration_ms,
            status="error",
            exception=e,
            **context
        )
        raise


def log_performance(operation_name: str = None):
    """Decorator to log function performance"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            operation = operation_name or f"{func.__module__}.{func.__name__}"
            
            logger = get_structured_logger()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                logger.performance_log(
                    f"Function completed: {operation}",
                    operation=operation,
                    duration_ms=duration_ms,
                    function_name=func.__name__,
                    status="success"
                )
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                logger.performance_log(
                    f"Function failed: {operation}",
                    operation=operation,
                    duration_ms=duration_ms,
                    function_name=func.__name__,
                    status="error",
                    exception=e
                )
                
                raise
        
        return wrapper
    return decorator


# Global logger instance
_structured_logger: Optional[StructuredLogger] = None


def init_structured_logger(name: str = "stevedores") -> StructuredLogger:
    """Initialize the global structured logger"""
    global _structured_logger
    
    if _structured_logger is None:
        _structured_logger = StructuredLogger(name)
    
    return _structured_logger


def get_structured_logger() -> StructuredLogger:
    """Get the global structured logger instance"""
    global _structured_logger
    
    if _structured_logger is None:
        _structured_logger = init_structured_logger()
    
    return _structured_logger


def configure_flask_logging(app):
    """Configure Flask app with structured logging"""
    # Initialize structured logger
    structured_logger = init_structured_logger()
    
    # Middleware for request logging
    @app.before_request
    def before_request_logging():
        g.request_start_time = time.time()
        g.request_id = str(uuid.uuid4())[:8]
        
        structured_logger.debug(
            "Request started",
            component=ComponentType.WEB_SERVER.value,
            endpoint=request.endpoint,
            method=request.method,
            path=request.path
        )
    
    @app.after_request
    def after_request_logging(response):
        if hasattr(g, 'request_start_time'):
            duration_ms = (time.time() - g.request_start_time) * 1000
            
            # Determine log level based on status code and duration
            if response.status_code >= 500:
                level = LogLevel.ERROR
            elif response.status_code >= 400:
                level = LogLevel.WARNING
            elif duration_ms > 2000:
                level = LogLevel.WARNING
            else:
                level = LogLevel.INFO
            
            structured_logger.log(
                level,
                f"Request completed: {request.method} {request.path}",
                component=ComponentType.WEB_SERVER.value,
                endpoint=request.endpoint,
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                response_size_bytes=response.content_length
            )
        
        return response
    
    return app


# Export all public interfaces
__all__ = [
    'LogLevel', 'MaritimeOperationType', 'ComponentType', 'LogContext',
    'StructuredLogger', 'JsonFormatter', 'maritime_operation_context',
    'log_performance', 'init_structured_logger', 'get_structured_logger',
    'configure_flask_logging'
]