"""
Security Configuration for Stevedores Dashboard 3.0
Centralized security settings for maritime-critical operations
"""

import os
from datetime import timedelta
from flask import request
from typing import Dict, List, Optional, Union

class SecurityConfig:
    """Centralized security configuration for maritime operations"""
    
    # Flask-Talisman CSP Configuration for Maritime Operations
    CSP_POLICY = {
        'default-src': "'self'",
        'script-src': [
            "'self'",
            "'unsafe-inline'",  # Required for service worker and offline functionality
            "'unsafe-eval'",   # Required for maritime data processing
            'https://cdn.jsdelivr.net',  # CDN for fallback libraries
        ],
        'style-src': [
            "'self'",
            "'unsafe-inline'",  # Required for dynamic maritime UI components
            'https://fonts.googleapis.com',
            'https://cdn.jsdelivr.net',
        ],
        'font-src': [
            "'self'",
            'https://fonts.gstatic.com',
            'data:',  # For embedded maritime icons
        ],
        'img-src': [
            "'self'",
            'data:',  # For cargo and vessel icons
            'blob:',  # For offline cached images
            'https:',  # Allow secure external maritime resources
        ],
        'connect-src': [
            "'self'",
            'https:',  # Allow secure connections to maritime APIs
            'wss:',   # WebSocket for real-time ship data
        ],
        'worker-src': [
            "'self'",  # Service worker for offline functionality
        ],
        'manifest-src': [
            "'self'",  # PWA manifest
        ],
        'media-src': [
            "'self'",
            'blob:',  # For offline media content
        ],
        'object-src': "'none'",
        'base-uri': "'self'",
        'form-action': "'self'",
        'frame-ancestors': "'none'",
        'upgrade-insecure-requests': True,
    }
    
    # Flask-Talisman Security Headers
    SECURITY_HEADERS = {
        'force_https': False,  # Set to True in production with HTTPS
        'force_https_permanent': False,
        'force_file_save': False,
        'frame_options': 'DENY',
        'frame_options_allow_from': None,
        'strict_transport_security': True,
        'strict_transport_security_preload': True,
        'strict_transport_security_max_age': 31536000,  # 1 year
        'strict_transport_security_include_subdomains': True,
        'content_type_nosniff': True,
        'referrer_policy': 'strict-origin-when-cross-origin',
        'feature_policy': {
            'geolocation': "'self'",  # GPS for vessel location
            'camera': "'self'",      # Document scanning
            'microphone': "'none'",
            'payment': "'none'",
            'usb': "'none'",
        },
        'permissions_policy': {
            'geolocation': ['self'],
            'camera': ['self'],
            'microphone': [],
            'payment': [],
            'usb': [],
        },
    }
    
    # Flask-Limiter Rate Limiting Configuration
    RATE_LIMIT_CONFIG = {
        'default_limits': ['1000 per hour', '100 per minute'],
        'headers_enabled': True,
        'swallow_errors': False,
        'storage_uri': os.environ.get('REDIS_URL', 'memory://'),
        'strategy': 'fixed-window',
    }
    
    # Maritime-specific Rate Limits
    MARITIME_RATE_LIMITS = {
        'auth_login': '5 per minute',          # Prevent brute force
        'auth_logout': '10 per minute',        # Allow quick logouts
        'vessel_create': '10 per hour',        # Limit vessel creation
        'cargo_tally': '100 per minute',       # High-frequency maritime operations
        'document_upload': '20 per minute',    # Document processing
        'sync_operations': '50 per minute',    # Offline sync
        'api_vessel_data': '200 per minute',   # Real-time vessel data
        'wizard_operations': '30 per hour',    # Vessel setup wizard
        'reports_generate': '10 per minute',   # Report generation
        'health_check': '60 per minute',       # System monitoring
    }
    
    # HTML Sanitization Settings (bleach)
    BLEACH_CONFIG = {
        'allowed_tags': [
            'p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'blockquote', 'code', 'pre',
            'span', 'div',  # For maritime data formatting
            'table', 'thead', 'tbody', 'tr', 'th', 'td',  # For cargo manifests
        ],
        'allowed_attributes': {
            '*': ['class', 'id'],
            'span': ['data-*'],  # For maritime data attributes
            'div': ['data-*'],
            'table': ['data-*'],
            'tr': ['data-*'],
            'td': ['data-*'],
            'th': ['data-*'],
        },
        'allowed_protocols': ['http', 'https', 'mailto'],
        'strip_comments': True,
        'strip': True,
    }
    
    # Authentication Security Settings
    AUTH_SECURITY = {
        'session_timeout': timedelta(hours=8),     # Maritime shift length
        'permanent_session_lifetime': timedelta(hours=24),
        'session_cookie_secure': True,             # HTTPS only in production
        'session_cookie_httponly': True,
        'session_cookie_samesite': 'Lax',
        'remember_cookie_duration': timedelta(days=30),
        'remember_cookie_secure': True,
        'remember_cookie_httponly': True,
        'max_login_attempts': 5,
        'lockout_duration': timedelta(minutes=15),
        'password_min_length': 8,
        'password_require_special': True,
        'password_require_numbers': True,
        'password_require_mixed_case': True,
    }
    
    # File Upload Security (for maritime documents)
    FILE_UPLOAD_SECURITY = {
        'max_file_size': 50 * 1024 * 1024,  # 50MB for maritime documents
        'allowed_extensions': {
            'pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv',
            'txt', 'png', 'jpg', 'jpeg', 'gif',
            'json', 'xml'  # Maritime data formats
        },
        'allowed_mime_types': {
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'text/csv',
            'text/plain',
            'image/png',
            'image/jpeg',
            'image/gif',
            'application/json',
            'application/xml',
            'text/xml',
        },
        'scan_for_malware': True,
        'quarantine_suspicious': True,
        'upload_folder': 'uploads/maritime_documents',
        'temp_folder': 'temp/upload_processing',
    }
    
    # API Security Settings
    API_SECURITY = {
        'require_authentication': True,
        'require_csrf_token': True,
        'allow_cors_origins': [],  # Specify allowed origins in production
        'max_request_size': 100 * 1024 * 1024,  # 100MB for maritime data
        'request_timeout': 60,  # seconds
        'enable_audit_logging': True,
        'audit_sensitive_fields': [
            'password', 'token', 'secret', 'key',
            'ssn', 'credit_card', 'passport'
        ],
        'response_headers': {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
        },
    }
    
    # Maritime Compliance Settings
    MARITIME_COMPLIANCE = {
        'enable_audit_trail': True,
        'audit_retention_days': 2555,  # 7 years for maritime compliance
        'data_classification_levels': [
            'public', 'internal', 'confidential', 'restricted'
        ],
        'encryption_at_rest': True,
        'encryption_in_transit': True,
        'gdpr_compliance': True,
        'right_to_deletion': True,
        'data_portability': True,
    }

def get_maritime_rate_limit_key() -> str:
    """
    Generate rate limit key based on user and operation context
    
    Returns:
        str: Rate limit key for current request
    """
    try:
        from flask_login import current_user
        
        # Base key on IP address
        key = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        
        # Add user context if authenticated
        if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            key = f"user:{current_user.id}:{key}"
        else:
            key = f"anon:{key}"
            
        # Add endpoint context for maritime operations
        if request.endpoint:
            key = f"{key}:{request.endpoint}"
            
        return key
        
    except Exception:
        # Fallback to IP-based limiting
        return request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)

def is_maritime_critical_endpoint(endpoint: str) -> bool:
    """
    Check if endpoint handles maritime-critical operations
    
    Args:
        endpoint: Flask endpoint name
        
    Returns:
        bool: True if endpoint is maritime-critical
    """
    critical_patterns = [
        'cargo_tally', 'vessel_', 'sync_', 'wizard_',
        'auth.login', 'document_', 'offline_'
    ]
    
    return any(pattern in endpoint for pattern in critical_patterns)

def get_security_context() -> Dict[str, Union[str, bool, int]]:
    """
    Get current security context for logging and monitoring
    
    Returns:
        dict: Security context information
    """
    try:
        from flask_login import current_user
        
        context = {
            'user_id': getattr(current_user, 'id', None) if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated else None,
            'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr),
            'user_agent': request.headers.get('User-Agent', ''),
            'endpoint': request.endpoint,
            'method': request.method,
            'is_maritime_critical': is_maritime_critical_endpoint(request.endpoint or ''),
            'timestamp': None,  # Will be set by caller
        }
        
        return context
        
    except Exception:
        return {
            'user_id': None,
            'ip_address': 'unknown',
            'user_agent': 'unknown',
            'endpoint': 'unknown',
            'method': 'unknown',
            'is_maritime_critical': False,
            'timestamp': None,
        }

class SecurityValidators:
    """Security validation utilities for maritime operations"""
    
    @staticmethod
    def validate_maritime_file(filename: str, content: bytes) -> Dict[str, Union[bool, str]]:
        """
        Validate uploaded maritime document
        
        Args:
            filename: Original filename
            content: File content bytes
            
        Returns:
            dict: Validation result with status and details
        """
        import magic
        
        result = {
            'valid': False,
            'reason': '',
            'mime_type': '',
            'file_size': len(content),
            'safe_filename': '',
        }
        
        try:
            # Check file size
            if len(content) > SecurityConfig.FILE_UPLOAD_SECURITY['max_file_size']:
                result['reason'] = 'File too large'
                return result
            
            # Check file extension
            ext = filename.lower().split('.')[-1] if '.' in filename else ''
            if ext not in SecurityConfig.FILE_UPLOAD_SECURITY['allowed_extensions']:
                result['reason'] = f'File extension .{ext} not allowed'
                return result
            
            # Check MIME type using python-magic
            try:
                mime_type = magic.from_buffer(content, mime=True)
                result['mime_type'] = mime_type
                
                if mime_type not in SecurityConfig.FILE_UPLOAD_SECURITY['allowed_mime_types']:
                    result['reason'] = f'MIME type {mime_type} not allowed'
                    return result
            except Exception:
                result['reason'] = 'Could not determine file type'
                return result
            
            # Generate safe filename
            import re
            safe_name = re.sub(r'[^\w\-_\.]', '_', filename)
            result['safe_filename'] = safe_name
            
            result['valid'] = True
            result['reason'] = 'File validation passed'
            
        except Exception as e:
            result['reason'] = f'Validation error: {str(e)}'
        
        return result
    
    @staticmethod
    def sanitize_maritime_html(content: str) -> str:
        """
        Sanitize HTML content for maritime data display
        
        Args:
            content: Raw HTML content
            
        Returns:
            str: Sanitized HTML content
        """
        import bleach
        
        return bleach.clean(
            content,
            tags=SecurityConfig.BLEACH_CONFIG['allowed_tags'],
            attributes=SecurityConfig.BLEACH_CONFIG['allowed_attributes'],
            protocols=SecurityConfig.BLEACH_CONFIG['allowed_protocols'],
            strip=SecurityConfig.BLEACH_CONFIG['strip'],
            strip_comments=SecurityConfig.BLEACH_CONFIG['strip_comments'],
        )
    
    @staticmethod
    def validate_maritime_data_input(data: Dict) -> Dict[str, Union[bool, str, List]]:
        """
        Validate maritime data input for security issues
        
        Args:
            data: Input data dictionary
            
        Returns:
            dict: Validation result
        """
        result = {
            'valid': True,
            'issues': [],
            'sanitized_data': {},
        }
        
        try:
            for key, value in data.items():
                if isinstance(value, str):
                    # Check for potential XSS
                    if '<script' in value.lower() or 'javascript:' in value.lower():
                        result['issues'].append(f'Potential XSS in field: {key}')
                        result['valid'] = False
                    
                    # Check for SQL injection patterns
                    sql_patterns = ['union select', 'drop table', 'delete from', '--']
                    if any(pattern in value.lower() for pattern in sql_patterns):
                        result['issues'].append(f'Potential SQL injection in field: {key}')
                        result['valid'] = False
                    
                    # Sanitize HTML content
                    result['sanitized_data'][key] = SecurityValidators.sanitize_maritime_html(value)
                else:
                    result['sanitized_data'][key] = value
            
        except Exception as e:
            result['valid'] = False
            result['issues'].append(f'Validation error: {str(e)}')
        
        return result