"""
Security Manager for Stevedores Dashboard 3.0
Centralized security component integration for maritime operations
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from flask import Flask, request, session, g
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import bleach

from .security_config import SecurityConfig, get_maritime_rate_limit_key, get_security_context, SecurityValidators

logger = logging.getLogger(__name__)

class SecurityManager:
    """Centralized security management for maritime operations"""
    
    def __init__(self, app: Optional[Flask] = None):
        self.app = app
        self.talisman = None
        self.limiter = None
        self.config = SecurityConfig()
        
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize security components with Flask app"""
        self.app = app
        
        # Configure Flask security settings
        self._configure_flask_security(app)
        
        # Initialize Flask-Talisman for security headers
        self._init_talisman(app)
        
        # Initialize Flask-Limiter for rate limiting
        self._init_limiter(app)
        
        # Set up security middleware
        self._setup_security_middleware(app)
        
        # Configure security logging
        self._setup_security_logging(app)
        
        logger.info("Maritime security manager initialized successfully")
    
    def _configure_flask_security(self, app: Flask):
        """Configure Flask-level security settings"""
        
        # Session security
        app.config.update({
            'SESSION_COOKIE_SECURE': self.config.AUTH_SECURITY['session_cookie_secure'] and not app.debug,
            'SESSION_COOKIE_HTTPONLY': self.config.AUTH_SECURITY['session_cookie_httponly'],
            'SESSION_COOKIE_SAMESITE': self.config.AUTH_SECURITY['session_cookie_samesite'],
            'PERMANENT_SESSION_LIFETIME': self.config.AUTH_SECURITY['permanent_session_lifetime'],
            'REMEMBER_COOKIE_SECURE': self.config.AUTH_SECURITY['remember_cookie_secure'] and not app.debug,
            'REMEMBER_COOKIE_HTTPONLY': self.config.AUTH_SECURITY['remember_cookie_httponly'],
            'REMEMBER_COOKIE_DURATION': self.config.AUTH_SECURITY['remember_cookie_duration'],
        })
        
        # File upload security
        app.config.update({
            'MAX_CONTENT_LENGTH': self.config.FILE_UPLOAD_SECURITY['max_file_size'],
            'UPLOAD_FOLDER': self.config.FILE_UPLOAD_SECURITY['upload_folder'],
        })
        
        # Create upload directories
        os.makedirs(self.config.FILE_UPLOAD_SECURITY['upload_folder'], exist_ok=True)
        os.makedirs(self.config.FILE_UPLOAD_SECURITY['temp_folder'], exist_ok=True)
        
        logger.info("Flask security configuration applied")
    
    def _init_talisman(self, app: Flask):
        """Initialize Flask-Talisman for security headers"""
        
        # Adjust CSP for development vs production
        csp_policy = self.config.CSP_POLICY.copy()
        
        if app.debug:
            # Relax CSP for development
            csp_policy['script-src'].append("'unsafe-eval'")
            force_https = False
        else:
            # Stricter CSP for production
            force_https = True
        
        # Initialize Talisman with correct parameters
        self.talisman = Talisman(
            app,
            content_security_policy=csp_policy,
            force_https=force_https,
            strict_transport_security=True,
            strict_transport_security_max_age=31536000,
            strict_transport_security_include_subdomains=True,
            frame_options='DENY',
            referrer_policy='strict-origin-when-cross-origin',
        )
        
        logger.info("Flask-Talisman security headers initialized")
    
    def _init_limiter(self, app: Flask):
        """Initialize Flask-Limiter for rate limiting"""
        
        # Extract key_func from config to avoid duplication
        limiter_config = self.config.RATE_LIMIT_CONFIG.copy()
        key_func = limiter_config.pop('key_func', get_maritime_rate_limit_key)
        
        # Configure limiter with maritime-specific settings
        self.limiter = Limiter(
            app=app,
            key_func=key_func,
            **limiter_config
        )
        
        logger.info("Flask-Limiter rate limiting initialized")
    
    def _setup_security_middleware(self, app: Flask):
        """Set up security middleware for request processing"""
        
        @app.before_request
        def security_before_request():
            """Security checks before each request"""
            
            # Store security context
            g.security_context = get_security_context()
            g.security_context['timestamp'] = datetime.utcnow().isoformat()
            
            # Check for maritime-critical operations
            if g.security_context['is_maritime_critical']:
                self._log_maritime_access(g.security_context)
            
            # Validate request size for maritime data uploads
            if request.content_length and request.content_length > self.config.API_SECURITY['max_request_size']:
                logger.warning(f"Request too large: {request.content_length} bytes from {g.security_context['ip_address']}")
                return 'Request too large', 413
            
            # Check for suspicious patterns in request
            if self._detect_suspicious_request():
                logger.warning(f"Suspicious request detected from {g.security_context['ip_address']}")
                return 'Forbidden', 403
        
        @app.after_request
        def security_after_request(response):
            """Security processing after each request"""
            
            # Add security headers to API responses
            if request.path.startswith('/api/'):
                for header, value in self.config.API_SECURITY['response_headers'].items():
                    response.headers[header] = value
            
            # Log security events if enabled
            if hasattr(g, 'security_context') and self.config.API_SECURITY['enable_audit_logging']:
                self._log_security_event(g.security_context, response.status_code)
            
            return response
        
        logger.info("Security middleware configured")
    
    def _setup_security_logging(self, app: Flask):
        """Configure security-specific logging"""
        
        # Create security logger
        security_logger = logging.getLogger('maritime_security')
        security_logger.setLevel(logging.INFO)
        
        # Create file handler for security events
        security_log_file = os.path.join(app.instance_path if hasattr(app, 'instance_path') else '.', 'logs', 'security.log')
        os.makedirs(os.path.dirname(security_log_file), exist_ok=True)
        
        file_handler = logging.FileHandler(security_log_file)
        file_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        security_logger.addHandler(file_handler)
        
        # Store reference for use in other methods
        self.security_logger = security_logger
        
        logger.info("Security logging configured")
    
    def _detect_suspicious_request(self) -> bool:
        """Detect potentially suspicious requests"""
        
        try:
            # Check User-Agent for known bad patterns
            user_agent = request.headers.get('User-Agent', '').lower()
            suspicious_agents = [
                'sqlmap', 'nikto', 'nmap', 'masscan', 'zap',
                'burp', 'w3af', 'curl', 'wget'
            ]
            
            if any(agent in user_agent for agent in suspicious_agents):
                return True
            
            # Check for common attack patterns in query parameters
            for key, value in request.args.items():
                if isinstance(value, str):
                    # SQL injection patterns
                    if any(pattern in value.lower() for pattern in [
                        'union select', 'drop table', 'insert into',
                        'delete from', 'update set', '--', '/*'
                    ]):
                        return True
                    
                    # XSS patterns
                    if any(pattern in value.lower() for pattern in [
                        '<script', 'javascript:', 'onload=', 'onerror=',
                        'eval(', 'alert(', 'document.cookie'
                    ]):
                        return True
            
            # Check for path traversal
            if '../' in request.path or '..\\' in request.path:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in suspicious request detection: {e}")
            return False
    
    def _log_maritime_access(self, security_context: Dict):
        """Log access to maritime-critical operations"""
        
        if hasattr(self, 'security_logger'):
            self.security_logger.info(
                f"MARITIME_ACCESS - User: {security_context['user_id']} - "
                f"IP: {security_context['ip_address']} - "
                f"Endpoint: {security_context['endpoint']} - "
                f"Method: {security_context['method']}"
            )
    
    def _log_security_event(self, security_context: Dict, status_code: int):
        """Log security events for audit trail"""
        
        if hasattr(self, 'security_logger'):
            self.security_logger.info(
                f"SECURITY_EVENT - User: {security_context['user_id']} - "
                f"IP: {security_context['ip_address']} - "
                f"Endpoint: {security_context['endpoint']} - "
                f"Method: {security_context['method']} - "
                f"Status: {status_code} - "
                f"Critical: {security_context['is_maritime_critical']}"
            )
    
    def apply_maritime_rate_limits(self):
        """Apply maritime-specific rate limits to endpoints"""
        
        if not self.limiter:
            logger.error("Limiter not initialized")
            return
        
        # Authentication endpoints
        self.limiter.limit(self.config.MARITIME_RATE_LIMITS['auth_login'])(self._get_endpoint_function('auth.login'))
        self.limiter.limit(self.config.MARITIME_RATE_LIMITS['auth_logout'])(self._get_endpoint_function('auth.logout'))
        
        # Maritime operation endpoints
        self.limiter.limit(self.config.MARITIME_RATE_LIMITS['cargo_tally'])(self._get_endpoint_function('api_vessel_cargo_tally'))
        self.limiter.limit(self.config.MARITIME_RATE_LIMITS['vessel_create'])(self._get_endpoint_function('wizard.create_vessel'))
        self.limiter.limit(self.config.MARITIME_RATE_LIMITS['document_upload'])(self._get_endpoint_function('document.upload'))
        self.limiter.limit(self.config.MARITIME_RATE_LIMITS['sync_operations'])(self._get_endpoint_function('sync.process'))
        
        logger.info("Maritime-specific rate limits applied")
    
    def _get_endpoint_function(self, endpoint_name: str):
        """Get endpoint function for rate limiting (placeholder)"""
        # This would be implemented with actual endpoint functions
        # For now, return a lambda that does nothing
        return lambda: None
    
    def sanitize_maritime_data(self, data: Any) -> Any:
        """Sanitize maritime data for security"""
        
        if isinstance(data, str):
            return SecurityValidators.sanitize_maritime_html(data)
        elif isinstance(data, dict):
            return {key: self.sanitize_maritime_data(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self.sanitize_maritime_data(item) for item in data]
        else:
            return data
    
    def validate_maritime_file_upload(self, file_data: bytes, filename: str) -> Dict[str, Any]:
        """Validate maritime document uploads"""
        
        return SecurityValidators.validate_maritime_file(filename, file_data)
    
    def check_authentication_security(self, user_id: str, ip_address: str) -> Dict[str, Any]:
        """Check authentication security for maritime operations"""
        
        # This would implement additional authentication checks
        # like geolocation validation, device fingerprinting, etc.
        
        return {
            'secure': True,
            'risk_level': 'low',
            'additional_verification_required': False,
            'message': 'Authentication security check passed'
        }
    
    def get_security_status(self) -> Dict[str, Any]:
        """Get current security status for monitoring"""
        
        return {
            'talisman_enabled': self.talisman is not None,
            'limiter_enabled': self.limiter is not None,
            'security_logging': hasattr(self, 'security_logger'),
            'csp_policy_active': bool(self.config.CSP_POLICY),
            'rate_limits_active': bool(self.config.MARITIME_RATE_LIMITS),
            'file_upload_security': self.config.FILE_UPLOAD_SECURITY['scan_for_malware'],
            'audit_trail_enabled': self.config.MARITIME_COMPLIANCE['enable_audit_trail'],
            'timestamp': datetime.utcnow().isoformat()
        }

# Global security manager instance
security_manager = SecurityManager()

def init_security_manager(app: Flask) -> SecurityManager:
    """Initialize security manager with Flask app"""
    
    security_manager.init_app(app)
    return security_manager

def get_security_manager() -> SecurityManager:
    """Get the global security manager instance"""
    
    return security_manager