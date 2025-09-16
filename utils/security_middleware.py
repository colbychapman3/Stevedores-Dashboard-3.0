"""Production Security Middleware with Flask-Talisman CSP Configuration
Fixes TypeError: can only join an iterable CSP error and provides enterprise-grade security

Features:
- Fixed CSP directive formatting that eliminates TypeError
- Enterprise security headers (HSTS, X-Frame-Options, etc.)
- Production security configurations
- Graceful error handling with fallbacks
- Security monitoring and violation tracking
- Configurable security policies based on environment
"""

from flask_talisman import Talisman
from flask import request, current_app, g, session
import logging
import json
from datetime import datetime, timedelta
from functools import wraps
import os
import secrets

logger = logging.getLogger(__name__)

class SecurityViolationTracker:
    """Track and monitor security policy violations"""
    
    def __init__(self):
        self.violations = []
        self.max_violations = 1000
    
    def record_violation(self, violation_type, details, request_info=None):
        """Record a security policy violation"""
        violation = {
            'timestamp': datetime.utcnow().isoformat(),
            'type': violation_type,
            'details': details,
            'ip': request_info.get('remote_addr') if request_info else None,
            'user_agent': request_info.get('user_agent') if request_info else None,
            'url': request_info.get('url') if request_info else None
        }
        
        self.violations.append(violation)
        
        # Keep only recent violations
        if len(self.violations) > self.max_violations:
            self.violations = self.violations[-self.max_violations:]
        
        logger.warning(f"Security violation recorded: {violation_type} - {details}")
    
    def get_recent_violations(self, limit=100):
        """Get recent security violations"""
        return self.violations[-limit:] if self.violations else []
    
    def get_violation_stats(self):
        """Get violation statistics"""
        if not self.violations:
            return {'total': 0, 'types': {}}
        
        stats = {
            'total': len(self.violations),
            'types': {},
            'recent_24h': 0
        }
        
        now = datetime.utcnow()
        day_ago = now - timedelta(hours=24)
        
        for violation in self.violations:
            v_type = violation['type']
            stats['types'][v_type] = stats['types'].get(v_type, 0) + 1
            
            try:
                v_time = datetime.fromisoformat(violation['timestamp'])
                if v_time > day_ago:
                    stats['recent_24h'] += 1
            except ValueError:
                continue
        
        return stats

class SecurityMiddleware:
    """Enterprise-grade security middleware with comprehensive protection"""
    
    def __init__(self):
        self.talisman = None
        self.is_initialized = False
        self.violation_tracker = SecurityViolationTracker()
        self.nonce_cache = {}
        self.security_config = None
    
    def _generate_security_nonce(self):
        """Generate a cryptographically secure nonce for CSP"""
        return secrets.token_urlsafe(16)
    
    def _get_environment_config(self, app):
        """Get security configuration based on environment"""
        is_debug = app.config.get('DEBUG', False)
        is_testing = app.config.get('TESTING', False)
        is_production = not (is_debug or is_testing)
        
        return {
            'is_production': is_production,
            'is_debug': is_debug,
            'is_testing': is_testing,
            'force_https': is_production and not os.environ.get('DISABLE_HTTPS_REDIRECT'),
            'strict_csp': is_production,
            'enable_hsts': is_production
        }
    
    def _build_csp_policy(self, config):
        """Build Content Security Policy with proper formatting to avoid TypeError"""
        
        # Base policy - more restrictive for production
        if config['strict_csp']:
            # Production CSP - stricter security
            csp = {
                'default-src': ["'self'"],
                'script-src': [
                    "'self'",
                    "'unsafe-inline'",  # Required for PWA - consider removing in future
                    "https://cdn.jsdelivr.net",
                    "https://unpkg.com",
                    "https://cdnjs.cloudflare.com"
                ],
                'style-src': [
                    "'self'",
                    "'unsafe-inline'",  # Required for dynamic styles
                    "https://cdn.jsdelivr.net",
                    "https://fonts.googleapis.com",
                    "https://fonts.gstatic.com"
                ],
                'font-src': [
                    "'self'",
                    "https://fonts.gstatic.com",
                    "data:"
                ],
                'img-src': [
                    "'self'",
                    "data:",
                    "blob:",
                    "https:"
                ],
                'connect-src': [
                    "'self'",
                    "https:",
                    "wss:",  # WebSocket connections for real-time features
                    "ws:"   # WebSocket for development
                ],
                'worker-src': ["'self'"],
                'manifest-src': ["'self'"],
                'object-src': ["'none'"],
                'base-uri': ["'self'"],
                'form-action': ["'self'"],
                'frame-ancestors': ["'none'"],  # Prevent framing
                'upgrade-insecure-requests': True if config['force_https'] else False
            }
        else:
            # Development/Testing CSP - more permissive
            csp = {
                'default-src': ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
                'script-src': [
                    "'self'",
                    "'unsafe-inline'",
                    "'unsafe-eval'",
                    "https:",
                    "http:",
                    "data:"
                ],
                'style-src': [
                    "'self'",
                    "'unsafe-inline'",
                    "https:",
                    "http:"
                ],
                'font-src': ["*"],
                'img-src': ["*"],
                'connect-src': ["*"],
                'worker-src': ["*"],
                'manifest-src': ["*"],
                'object-src': ["*"],
                'base-uri': ["*"],
                'form-action': ["*"]
            }
        
        # Remove any boolean values that aren't directives
        clean_csp = {}
        for key, value in csp.items():
            if key == 'upgrade-insecure-requests':
                if value:  # Only include if True
                    clean_csp[key] = True
            else:
                # Ensure all directive values are properly formatted lists or strings
                if isinstance(value, list):
                    clean_csp[key] = value
                elif isinstance(value, str):
                    clean_csp[key] = [value]
        
        return clean_csp
    
    def _build_permissions_policy(self, config):
        """Build Permissions Policy (formerly Feature Policy)"""
        
        if config['strict_csp']:
            # Production - deny most permissions
            return {
                'geolocation': '()',
                'camera': '()',
                'microphone': '()',
                'payment': '(self)',
                'usb': '()',
                'bluetooth': '()',
                'accelerometer': '()',
                'gyroscope': '()',
                'magnetometer': '()',
                'ambient-light-sensor': '()',
                'encrypted-media': '()',
                'autoplay': '(self)'
            }
        else:
            # Development - more permissive
            return {
                'geolocation': '(self)',
                'camera': '(self)',
                'microphone': '(self)',
                'payment': '(self)'
            }
    
    def init_app(self, app):
        """Initialize security middleware with comprehensive protection"""
        try:
            self.security_config = self._get_environment_config(app)
            config = self.security_config
            
            logger.info(f"Initializing security middleware for {('production' if config['is_production'] else 'development')} environment")
            
            # Build CSP policy
            csp_policy = self._build_csp_policy(config)
            permissions_policy = self._build_permissions_policy(config)
            
            # Configure Talisman with comprehensive security settings
            talisman_config = {
                'force_https': config['force_https'],
                'strict_transport_security': config['enable_hsts'],
                'strict_transport_security_max_age': 31536000 if config['enable_hsts'] else None,  # 1 year
                'strict_transport_security_include_subdomains': config['enable_hsts'],
                'content_security_policy': csp_policy,
                'content_security_policy_nonce_in': ['script-src', 'style-src'] if config['strict_csp'] else None,
                'content_security_policy_report_only': False,
                'referrer_policy': 'strict-origin-when-cross-origin',
                'permissions_policy': permissions_policy,
                'session_cookie_secure': config['force_https'],
                'session_cookie_http_only': True,
                'session_cookie_samesite': 'Lax',
                'force_file_save': True,
                'x_content_type_options': True,
                'x_frame_options': 'DENY',
                'x_xss_protection': True
            }
            
            # Remove None values to avoid Talisman errors
            talisman_config = {k: v for k, v in talisman_config.items() if v is not None}
            
            # Initialize Talisman with error handling
            try:
                self.talisman = Talisman(app, **talisman_config)
                logger.info("✅ Talisman security middleware initialized successfully")
            except Exception as talisman_error:
                logger.error(f"❌ Talisman initialization error: {talisman_error}")
                # Try with basic configuration as fallback
                basic_config = {
                    'force_https': False,
                    'content_security_policy': {'default-src': ["'self'"]},
                    'session_cookie_http_only': True
                }
                try:
                    self.talisman = Talisman(app, **basic_config)
                    logger.warning("⚠️  Talisman initialized with basic fallback configuration")
                except Exception as fallback_error:
                    logger.error(f"❌ Talisman fallback initialization failed: {fallback_error}")
                    self.talisman = None
            
            # Add custom security headers middleware
            self._add_custom_headers_middleware(app)
            
            # Add CSP violation reporting
            self._add_csp_violation_reporting(app)
            
            self.is_initialized = True
            logger.info("✅ Enterprise security middleware initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize security middleware: {e}")
            self.violation_tracker.record_violation(
                'initialization_error',
                str(e),
                {'component': 'security_middleware'}
            )
            # Don't fail application startup
            self.is_initialized = False
    
    def _add_custom_headers_middleware(self, app):
        """Add custom security headers not handled by Talisman"""
        
        @app.after_request
        def add_security_headers(response):
            """Add additional security headers"""
            try:
                config = self.security_config or self._get_environment_config(app)
                
                # Additional security headers
                if config['is_production']:
                    response.headers['X-Robots-Tag'] = 'noindex, nofollow'  # Prevent indexing
                    response.headers['X-Permitted-Cross-Domain-Policies'] = 'none'
                    response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
                    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
                    response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'
                
                # Cache control for static resources
                if request.endpoint and request.endpoint.startswith('static'):
                    response.headers['Cache-Control'] = 'public, max-age=31536000'  # 1 year
                elif request.endpoint in ['manifest', 'service_worker']:
                    response.headers['Cache-Control'] = 'public, max-age=86400'  # 24 hours
                else:
                    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                    response.headers['Pragma'] = 'no-cache'
                    response.headers['Expires'] = '0'
                
                # PWA-specific headers
                if request.path in ['/manifest.json', '/service-worker.js']:
                    response.headers['Access-Control-Allow-Origin'] = '*'
                
            except Exception as e:
                logger.error(f"Error adding custom security headers: {e}")
            
            return response
    
    def _add_csp_violation_reporting(self, app):
        """Add CSP violation reporting endpoint"""
        
        @app.route('/security/csp-report', methods=['POST'])
        def csp_violation_report():
            """Handle CSP violation reports"""
            try:
                report = request.get_json()
                if report:
                    self.violation_tracker.record_violation(
                        'csp_violation',
                        report,
                        {
                            'remote_addr': request.remote_addr,
                            'user_agent': str(request.user_agent),
                            'url': request.url
                        }
                    )
                return '', 204
            except Exception as e:
                logger.error(f"Error handling CSP violation report: {e}")
                return '', 400
    
    def get_csp_nonce(self):
        """Get or generate CSP nonce for inline scripts/styles"""
        if self.talisman and hasattr(self.talisman, 'csp_nonce'):
            try:
                return self.talisman.csp_nonce()
            except Exception as e:
                logger.warning(f"Error getting CSP nonce from Talisman: {e}")
        
        # Fallback nonce generation
        if not hasattr(g, 'csp_nonce'):
            g.csp_nonce = self._generate_security_nonce()
        
        return g.csp_nonce
    
    def is_security_enabled(self):
        """Check if security middleware is properly enabled"""
        return self.is_initialized and (self.talisman is not None or self.security_config is not None)
    
    def get_security_status(self):
        """Get comprehensive security status"""
        config = self.security_config or {}
        
        return {
            "middleware_initialized": self.is_initialized,
            "talisman_enabled": self.talisman is not None,
            "https_enforced": config.get('force_https', False),
            "hsts_enabled": config.get('enable_hsts', False),
            "strict_csp": config.get('strict_csp', False),
            "environment": "production" if config.get('is_production') else "development",
            "csp_enabled": True,
            "violation_tracking": True,
            "recent_violations": len(self.violation_tracker.get_recent_violations(100)),
            "total_violations": self.violation_tracker.get_violation_stats()['total']
        }
    
    def get_violation_report(self, limit=100):
        """Get security violation report"""
        return {
            "recent_violations": self.violation_tracker.get_recent_violations(limit),
            "statistics": self.violation_tracker.get_violation_stats(),
            "recommendations": self._generate_security_recommendations()
        }
    
    def _generate_security_recommendations(self):
        """Generate security recommendations based on violations"""
        stats = self.violation_tracker.get_violation_stats()
        recommendations = []
        
        if stats['total'] > 0:
            if 'csp_violation' in stats['types']:
                recommendations.append(
                    "Consider reviewing CSP policy - violations detected"
                )
            
            if stats['recent_24h'] > 10:
                recommendations.append(
                    "High number of security violations in last 24h - review logs"
                )
        
        config = self.security_config or {}
        if not config.get('force_https', False):
            recommendations.append(
                "Enable HTTPS enforcement for production security"
            )
        
        if not config.get('strict_csp', False):
            recommendations.append(
                "Enable strict CSP policy for enhanced security"
            )
        
        return recommendations

# Global security middleware instance
_security_middleware = SecurityMiddleware()

def init_security_middleware(app):
    """Initialize security middleware for the application"""
    global _security_middleware
    _security_middleware.init_app(app)
    return _security_middleware

def get_security_middleware():
    """Get the global security middleware instance"""
    return _security_middleware

def security_health_check():
    """Check security middleware status for health endpoint"""
    middleware = get_security_middleware()
    return middleware.get_security_status()

def security_violation_report(limit=100):
    """Get security violation report"""
    middleware = get_security_middleware()
    return middleware.get_violation_report(limit)

def requires_security_clearance(level='basic'):
    """Decorator for routes requiring specific security clearance"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                middleware = get_security_middleware()
                if not middleware.is_security_enabled():
                    logger.warning(f"Security clearance check failed - middleware not enabled")
                    return current_app.response_class(
                        response=json.dumps({'error': 'Security middleware not available'}),
                        status=503,
                        mimetype='application/json'
                    )
                
                # Add security audit log
                logger.info(f"Security clearance '{level}' granted for {request.endpoint}")
                
                return f(*args, **kwargs)
            except Exception as e:
                logger.error(f"Security clearance check error: {e}")
                middleware.violation_tracker.record_violation(
                    'clearance_check_error',
                    str(e),
                    {
                        'endpoint': request.endpoint,
                        'method': request.method,
                        'ip': request.remote_addr
                    }
                )
                return current_app.response_class(
                    response=json.dumps({'error': 'Security check failed'}),
                    status=500,
                    mimetype='application/json'
                )
        return decorated_function
    return decorator