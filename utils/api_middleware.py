"""
API Security Middleware for Stevedores Dashboard 3.0
Request/response processing, validation, and security enforcement
"""

import os
import time
import json
import logging
from typing import Dict, Any, Optional, List, Callable
from functools import wraps
from datetime import datetime, timezone
from flask import request, jsonify, g, current_app
from werkzeug.exceptions import RequestEntityTooLarge

from .jwt_auth import get_jwt_manager, extract_jwt_token
from .audit_logger import get_audit_logger, AuditEventType, AuditSeverity
from .security_config import SecurityConfig, get_security_context

logger = logging.getLogger(__name__)

class APISecurityMiddleware:
    """Comprehensive API security middleware for maritime operations"""
    
    def __init__(self, app=None):
        self.app = app
        self.config = SecurityConfig()
        self.jwt_manager = None
        self.audit_logger = None
        self.request_size_limit = 100 * 1024 * 1024  # 100MB
        self.request_timeout = 60  # seconds
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize API middleware with Flask app"""
        self.app = app
        self.jwt_manager = get_jwt_manager()
        self.audit_logger = get_audit_logger()
        
        # Configure middleware settings
        self.request_size_limit = app.config.get(
            'MAX_CONTENT_LENGTH', 
            self.config.API_SECURITY['max_request_size']
        )
        self.request_timeout = app.config.get(
            'API_REQUEST_TIMEOUT',
            self.config.API_SECURITY['request_timeout']
        )
        
        # Set up middleware hooks
        self._setup_request_processing(app)
        self._setup_response_processing(app)
        self._setup_error_handling(app)
        
        logger.info("API security middleware initialized for maritime operations")
    
    def _setup_request_processing(self, app):
        """Set up request processing middleware"""
        
        @app.before_request
        def process_api_request():
            """Process and validate API requests"""
            
            # Skip non-API routes
            if not request.path.startswith('/api/'):
                return
            
            # Record request start time
            g.request_start_time = time.time()
            g.api_request = True
            
            # Validate request size
            if request.content_length and request.content_length > self.request_size_limit:
                self.audit_logger.log_security_event(
                    AuditEventType.SECURITY_VIOLATION,
                    f"Request too large: {request.content_length} bytes",
                    details={'max_allowed': self.request_size_limit}
                )
                return jsonify({
                    'success': False,
                    'error': 'Request entity too large',
                    'max_size': self.request_size_limit
                }), 413
            
            # Validate Content-Type for POST/PUT requests
            if request.method in ['POST', 'PUT', 'PATCH']:
                if not self._validate_content_type():
                    return jsonify({
                        'success': False,
                        'error': 'Invalid Content-Type',
                        'expected': 'application/json or multipart/form-data'
                    }), 400
            
            # Check for suspicious patterns
            if self._detect_malicious_request():
                self.audit_logger.log_security_event(
                    AuditEventType.SUSPICIOUS_ACTIVITY,
                    "Malicious request pattern detected",
                    details={
                        'user_agent': request.headers.get('User-Agent'),
                        'endpoint': request.endpoint,
                        'method': request.method
                    }
                )
                return jsonify({
                    'success': False,
                    'error': 'Request blocked by security policy'
                }), 403
            
            # Add security headers to request context
            self._add_security_context()
            
            # Log API request start
            if self.config.API_SECURITY['enable_audit_logging']:
                self._log_api_request_start()
    
    def _setup_response_processing(self, app):
        """Set up response processing middleware"""
        
        @app.after_request
        def process_api_response(response):
            """Process and secure API responses"""
            
            # Skip non-API routes
            if not hasattr(g, 'api_request'):
                return response
            
            # Add security headers
            self._add_security_headers(response)
            
            # Add API metadata
            self._add_api_metadata(response)
            
            # Log API request completion
            if self.config.API_SECURITY['enable_audit_logging']:
                self._log_api_request_completion(response)
            
            # Sanitize response data
            if response.content_type == 'application/json':
                self._sanitize_response_data(response)
            
            return response
    
    def _setup_error_handling(self, app):
        """Set up API error handling"""
        
        @app.errorhandler(400)
        def handle_bad_request(error):
            if request.path.startswith('/api/'):
                return self._create_error_response(
                    'Bad Request',
                    'The request could not be understood by the server',
                    400
                )
            return error
        
        @app.errorhandler(401)
        def handle_unauthorized(error):
            if request.path.startswith('/api/'):
                return self._create_error_response(
                    'Unauthorized',
                    'Authentication required',
                    401
                )
            return error
        
        @app.errorhandler(403)
        def handle_forbidden(error):
            if request.path.startswith('/api/'):
                return self._create_error_response(
                    'Forbidden',
                    'Insufficient permissions',
                    403
                )
            return error
        
        @app.errorhandler(404)
        def handle_not_found(error):
            if request.path.startswith('/api/'):
                return self._create_error_response(
                    'Not Found',
                    'The requested resource was not found',
                    404
                )
            return error
        
        @app.errorhandler(429)
        def handle_rate_limit(error):
            if request.path.startswith('/api/'):
                return self._create_error_response(
                    'Rate Limit Exceeded',
                    'Too many requests. Please try again later.',
                    429
                )
            return error
        
        @app.errorhandler(500)
        def handle_internal_error(error):
            if request.path.startswith('/api/'):
                # Log internal errors for debugging
                logger.error(f"Internal API error: {error}")
                return self._create_error_response(
                    'Internal Server Error',
                    'An unexpected error occurred',
                    500
                )
            return error
    
    def _validate_content_type(self) -> bool:
        """Validate request Content-Type"""
        content_type = request.content_type or ''
        
        allowed_types = [
            'application/json',
            'multipart/form-data',
            'application/x-www-form-urlencoded'
        ]
        
        return any(content_type.startswith(allowed) for allowed in allowed_types)
    
    def _detect_malicious_request(self) -> bool:
        """Detect potentially malicious requests"""
        try:
            # Check User-Agent for suspicious patterns
            user_agent = request.headers.get('User-Agent', '').lower()
            suspicious_agents = [
                'sqlmap', 'nikto', 'nmap', 'masscan', 'zap',
                'burp', 'w3af', 'dirbuster', 'gobuster'
            ]
            
            if any(agent in user_agent for agent in suspicious_agents):
                return True
            
            # Check for common attack patterns in URL
            suspicious_patterns = [
                '../', '..\\', '<script', 'javascript:', 'union select',
                'drop table', 'insert into', 'delete from'
            ]
            
            url_path = request.path.lower()
            query_string = request.query_string.decode('utf-8', errors='ignore').lower()
            
            for pattern in suspicious_patterns:
                if pattern in url_path or pattern in query_string:
                    return True
            
            # Check for excessive parameter count
            if len(request.args) > 50:
                return True
            
            # Check for suspicious headers
            suspicious_headers = request.headers.get('X-Forwarded-For', '')
            if 'script' in suspicious_headers.lower():
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in malicious request detection: {e}")
            return False
    
    def _add_security_context(self):
        """Add security context to request"""
        g.security_context = get_security_context()
        g.request_validated = True
        
        # Check for JWT token
        token = extract_jwt_token()
        if token:
            claims = self.jwt_manager.verify_token(token) if self.jwt_manager else None
            if claims:
                g.jwt_claims = claims
                g.jwt_user_id = claims.get('user_id')
    
    def _add_security_headers(self, response):
        """Add security headers to API response"""
        security_headers = self.config.API_SECURITY['response_headers']
        
        for header, value in security_headers.items():
            response.headers[header] = value
        
        # Add maritime-specific headers
        response.headers['X-Maritime-API'] = 'Stevedores-Dashboard-3.0'
        response.headers['X-API-Version'] = '1.0'
        
        # Add CORS headers if configured
        cors_origins = self.config.API_SECURITY.get('allow_cors_origins', [])
        if cors_origins:
            origin = request.headers.get('Origin')
            if origin in cors_origins:
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Credentials'] = 'true'
                response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    
    def _add_api_metadata(self, response):
        """Add API metadata to response"""
        if hasattr(g, 'request_start_time'):
            response.headers['X-Response-Time'] = f"{(time.time() - g.request_start_time) * 1000:.2f}ms"
        
        response.headers['X-Request-ID'] = getattr(g, 'request_id', 'unknown')
        response.headers['X-Timestamp'] = datetime.now(timezone.utc).isoformat()
    
    def _sanitize_response_data(self, response):
        """Sanitize sensitive data in API responses"""
        try:
            # This is a placeholder for response data sanitization
            # In production, you would implement actual sanitization logic
            pass
        except Exception as e:
            logger.error(f"Error sanitizing response data: {e}")
    
    def _log_api_request_start(self):
        """Log API request start"""
        self.audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_STARTUP,  # Using as generic API event
            message=f"API request started: {request.method} {request.endpoint}",
            details={
                'endpoint': request.endpoint,
                'method': request.method,
                'content_length': request.content_length,
                'user_agent': request.headers.get('User-Agent'),
            },
            severity=AuditSeverity.LOW,
            compliance_flags=['api_access']
        )
    
    def _log_api_request_completion(self, response):
        """Log API request completion"""
        duration = time.time() - getattr(g, 'request_start_time', time.time())
        
        severity = AuditSeverity.LOW
        if response.status_code >= 500:
            severity = AuditSeverity.HIGH
        elif response.status_code >= 400:
            severity = AuditSeverity.MEDIUM
        
        self.audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_STARTUP,  # Using as generic API event
            message=f"API request completed: {request.method} {request.endpoint}",
            details={
                'endpoint': request.endpoint,
                'method': request.method,
                'status_code': response.status_code,
                'duration_seconds': duration,
                'response_size': len(response.data) if response.data else 0,
            },
            severity=severity,
            maritime_context={
                'api_performance': {
                    'duration': duration,
                    'status': response.status_code
                }
            },
            compliance_flags=['api_access', 'performance_monitoring']
        )
    
    def _create_error_response(self, error_type: str, message: str, status_code: int):
        """Create standardized error response"""
        return jsonify({
            'success': False,
            'error': error_type,
            'message': message,
            'status_code': status_code,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'request_id': getattr(g, 'request_id', 'unknown'),
            'maritime_context': True
        }), status_code

def require_api_auth(f):
    """
    Decorator to require API authentication
    
    Usage:
        @app.route('/api/secure')
        @require_api_auth
        def secure_endpoint():
            return jsonify({'data': 'secure'})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'jwt_claims'):
            return jsonify({
                'success': False,
                'error': 'Authentication required',
                'message': 'Valid JWT token required for this endpoint'
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated_function

def require_maritime_context(f):
    """
    Decorator to require maritime operational context
    
    Usage:
        @app.route('/api/maritime/vessels')
        @require_maritime_context
        def maritime_endpoint():
            return jsonify({'vessels': []})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if hasattr(g, 'jwt_claims'):
            if not g.jwt_claims.get('maritime_context'):
                return jsonify({
                    'success': False,
                    'error': 'Maritime context required',
                    'message': 'This endpoint requires maritime operational context'
                }), 403
        
        return f(*args, **kwargs)
    
    return decorated_function

def log_api_access(operation: str = None):
    """
    Decorator to log API access for audit trail
    
    Usage:
        @app.route('/api/vessels')
        @log_api_access("vessel_list_access")
        def list_vessels():
            return jsonify({'vessels': []})
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Log access attempt
            audit_logger = get_audit_logger()
            audit_logger.log_event(
                event_type=AuditEventType.SYSTEM_STARTUP,  # Generic API access
                message=f"API access: {operation or f.__name__}",
                details={
                    'function': f.__name__,
                    'operation': operation,
                    'endpoint': request.endpoint,
                },
                severity=AuditSeverity.LOW,
                compliance_flags=['api_access', 'audit_trail']
            )
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def validate_request_size(max_size: int = None):
    """
    Decorator to validate request size
    
    Args:
        max_size: Maximum request size in bytes
    
    Usage:
        @app.route('/api/upload', methods=['POST'])
        @validate_request_size(10*1024*1024)  # 10MB
        def upload_file():
            return jsonify({'success': True})
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            size_limit = max_size or SecurityConfig.API_SECURITY['max_request_size']
            
            if request.content_length and request.content_length > size_limit:
                return jsonify({
                    'success': False,
                    'error': 'Request too large',
                    'max_size': size_limit,
                    'provided_size': request.content_length
                }), 413
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

# Global middleware instance
api_middleware = APISecurityMiddleware()

def init_api_middleware(app) -> APISecurityMiddleware:
    """Initialize API middleware with Flask app"""
    api_middleware.init_app(app)
    return api_middleware

def get_api_middleware() -> APISecurityMiddleware:
    """Get the global API middleware instance"""
    return api_middleware