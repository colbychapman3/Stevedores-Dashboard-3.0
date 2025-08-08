"""
Comprehensive Audit Logging System for Stevedores Dashboard 3.0
Maritime compliance and security audit trail
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from dataclasses import dataclass, asdict
from flask import request, g, current_app
from functools import wraps

logger = logging.getLogger(__name__)

class AuditEventType(Enum):
    """Audit event types for maritime operations"""
    
    # Authentication events
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILURE = "auth.login.failure"
    LOGOUT = "auth.logout"
    TOKEN_ISSUED = "auth.token.issued"
    TOKEN_REVOKED = "auth.token.revoked"
    
    # Maritime operations
    VESSEL_CREATED = "maritime.vessel.created"
    VESSEL_UPDATED = "maritime.vessel.updated"
    VESSEL_DELETED = "maritime.vessel.deleted"
    CARGO_TALLY_CREATED = "maritime.cargo_tally.created"
    CARGO_TALLY_UPDATED = "maritime.cargo_tally.updated"
    
    # Document operations
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_ACCESSED = "document.accessed"
    DOCUMENT_DELETED = "document.deleted"
    
    # Sync operations
    SYNC_STARTED = "sync.started"
    SYNC_COMPLETED = "sync.completed"
    SYNC_FAILED = "sync.failed"
    CONFLICT_RESOLVED = "sync.conflict.resolved"
    
    # Security events
    SECURITY_VIOLATION = "security.violation"
    RATE_LIMIT_EXCEEDED = "security.rate_limit.exceeded"
    SUSPICIOUS_ACTIVITY = "security.suspicious_activity"
    DATA_EXPORT = "security.data_export"
    
    # Administrative events
    USER_CREATED = "admin.user.created"
    USER_UPDATED = "admin.user.updated"
    USER_DISABLED = "admin.user.disabled"
    PERMISSION_CHANGED = "admin.permission.changed"
    
    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    BACKUP_CREATED = "system.backup.created"
    BACKUP_RESTORED = "system.backup.restored"

class AuditSeverity(Enum):
    """Audit event severity levels"""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class AuditEvent:
    """Audit event data structure"""
    
    event_type: AuditEventType
    timestamp: str
    user_id: Optional[int]
    session_id: Optional[str]
    ip_address: str
    user_agent: str
    endpoint: Optional[str]
    method: Optional[str]
    severity: AuditSeverity
    message: str
    details: Dict[str, Any]
    maritime_context: Dict[str, Any]
    compliance_flags: List[str]
    data_classification: str = "internal"
    retention_days: int = 2555  # 7 years for maritime compliance
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit event to dictionary"""
        return {
            'event_type': self.event_type.value,
            'timestamp': self.timestamp,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'endpoint': self.endpoint,
            'method': self.method,
            'severity': self.severity.value,
            'message': self.message,
            'details': self.details,
            'maritime_context': self.maritime_context,
            'compliance_flags': self.compliance_flags,
            'data_classification': self.data_classification,
            'retention_days': self.retention_days,
        }

class AuditLogger:
    """Comprehensive audit logging system for maritime compliance"""
    
    def __init__(self, app=None):
        self.app = app
        self.log_file_path = None
        self.audit_logger = None
        self.sensitive_fields = {
            'password', 'token', 'secret', 'key', 'api_key',
            'ssn', 'credit_card', 'passport', 'personal_id'
        }
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize audit logger with Flask app"""
        self.app = app
        
        # Configure audit log file
        log_dir = os.path.join(app.instance_path if hasattr(app, 'instance_path') else '.', 'logs', 'audit')
        os.makedirs(log_dir, exist_ok=True)
        
        self.log_file_path = os.path.join(log_dir, 'maritime_audit.log')
        
        # Create dedicated audit logger
        self.audit_logger = logging.getLogger('maritime_audit')
        self.audit_logger.setLevel(logging.INFO)
        
        # Create file handler with rotation
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            self.log_file_path,
            maxBytes=100*1024*1024,  # 100MB
            backupCount=10
        )
        file_handler.setLevel(logging.INFO)
        
        # Create formatter for structured logging
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        self.audit_logger.addHandler(file_handler)
        
        # Set up request context processor
        self._setup_request_context(app)
        
        logger.info("Audit logging system initialized for maritime compliance")
    
    def _setup_request_context(self, app):
        """Set up request context for audit logging"""
        
        @app.before_request
        def before_request_audit():
            """Capture request context for audit logging"""
            g.audit_context = {
                'request_id': self._generate_request_id(),
                'start_time': datetime.now(timezone.utc),
                'ip_address': self._get_client_ip(),
                'user_agent': request.headers.get('User-Agent', 'Unknown'),
                'endpoint': request.endpoint,
                'method': request.method,
                'url': request.url,
            }
        
        @app.after_request
        def after_request_audit(response):
            """Log request completion for audit trail"""
            if hasattr(g, 'audit_context'):
                duration = (datetime.now(timezone.utc) - g.audit_context['start_time']).total_seconds()
                
                # Log API requests for audit trail
                if request.path.startswith('/api/'):
                    self.log_api_request(
                        response.status_code,
                        duration,
                        g.audit_context
                    )
            
            return response
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID"""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def _get_client_ip(self) -> str:
        """Get client IP address from request"""
        return request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr) or 'unknown'
    
    def _get_user_context(self) -> Dict[str, Any]:
        """Get current user context for audit logging"""
        user_id = None
        session_id = None
        
        # Try to get user from JWT claims
        if hasattr(g, 'jwt_claims'):
            user_id = g.jwt_claims.get('user_id')
        
        # Try to get user from Flask-Login
        try:
            from flask_login import current_user
            if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
                user_id = getattr(current_user, 'id', None)
        except:
            pass
        
        # Try to get session ID
        try:
            from flask import session
            session_id = session.get('_id')
        except:
            pass
        
        return {
            'user_id': user_id,
            'session_id': session_id,
        }
    
    def _sanitize_data(self, data: Any) -> Any:
        """Sanitize sensitive data for audit logging"""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in self.sensitive_fields):
                    sanitized[key] = '[REDACTED]'
                else:
                    sanitized[key] = self._sanitize_data(value)
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_data(item) for item in data]
        else:
            return data
    
    def log_event(
        self,
        event_type: AuditEventType,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: AuditSeverity = AuditSeverity.MEDIUM,
        maritime_context: Optional[Dict[str, Any]] = None,
        compliance_flags: Optional[List[str]] = None,
        data_classification: str = "internal"
    ):
        """
        Log an audit event
        
        Args:
            event_type: Type of audit event
            message: Human-readable message
            details: Additional event details
            severity: Event severity level
            maritime_context: Maritime-specific context
            compliance_flags: Compliance requirement flags
            data_classification: Data classification level
        """
        try:
            user_context = self._get_user_context()
            request_context = getattr(g, 'audit_context', {})
            
            # Sanitize sensitive data
            sanitized_details = self._sanitize_data(details or {})
            
            # Create audit event
            audit_event = AuditEvent(
                event_type=event_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
                user_id=user_context.get('user_id'),
                session_id=user_context.get('session_id'),
                ip_address=request_context.get('ip_address', 'unknown'),
                user_agent=request_context.get('user_agent', 'unknown'),
                endpoint=request_context.get('endpoint'),
                method=request_context.get('method'),
                severity=severity,
                message=message,
                details=sanitized_details,
                maritime_context=maritime_context or {},
                compliance_flags=compliance_flags or [],
                data_classification=data_classification
            )
            
            # Log to audit file
            self.audit_logger.info(json.dumps(audit_event.to_dict()))
            
            # Log critical events to main logger as well
            if severity == AuditSeverity.CRITICAL:
                logger.critical(f"AUDIT: {event_type.value} - {message}")
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
    
    def log_api_request(self, status_code: int, duration: float, context: Dict[str, Any]):
        """Log API request for audit trail"""
        severity = AuditSeverity.LOW
        
        # Determine severity based on status code
        if status_code >= 500:
            severity = AuditSeverity.HIGH
        elif status_code >= 400:
            severity = AuditSeverity.MEDIUM
        
        self.log_event(
            event_type=AuditEventType.SYSTEM_STARTUP,  # Generic for API calls
            message=f"API request: {context['method']} {context['endpoint']}",
            details={
                'status_code': status_code,
                'duration_seconds': duration,
                'request_id': context.get('request_id'),
                'url': context.get('url'),
            },
            severity=severity,
            maritime_context={
                'api_call': True,
                'response_time': duration,
            }
        )
    
    def log_authentication_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[int],
        success: bool,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log authentication-related events"""
        severity = AuditSeverity.MEDIUM if success else AuditSeverity.HIGH
        
        self.log_event(
            event_type=event_type,
            message=f"Authentication event: {event_type.value}",
            details=details or {},
            severity=severity,
            compliance_flags=['authentication', 'access_control'],
            data_classification="confidential"
        )
    
    def log_maritime_operation(
        self,
        event_type: AuditEventType,
        operation: str,
        vessel_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log maritime operation events"""
        maritime_context = {
            'operation': operation,
            'vessel_id': vessel_id,
            'maritime_critical': True,
        }
        
        self.log_event(
            event_type=event_type,
            message=f"Maritime operation: {operation}",
            details=details or {},
            severity=AuditSeverity.MEDIUM,
            maritime_context=maritime_context,
            compliance_flags=['maritime_operations', 'cargo_handling'],
            data_classification="internal"
        )
    
    def log_security_event(
        self,
        event_type: AuditEventType,
        threat_description: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log security-related events"""
        self.log_event(
            event_type=event_type,
            message=f"Security event: {threat_description}",
            details=details or {},
            severity=AuditSeverity.HIGH,
            compliance_flags=['security', 'threat_detection'],
            data_classification="restricted"
        )
    
    def get_audit_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get audit log summary for the specified time period"""
        try:
            from datetime import timedelta
            
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            # This is a simplified implementation
            # In production, you'd query a database or parse log files
            return {
                'period_hours': hours,
                'total_events': 0,
                'critical_events': 0,
                'security_events': 0,
                'maritime_operations': 0,
                'authentication_events': 0,
                'summary_generated_at': datetime.now(timezone.utc).isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Failed to generate audit summary: {e}")
            return {'error': 'Failed to generate summary'}

# Global audit logger instance
audit_logger = AuditLogger()

def init_audit_logger(app) -> AuditLogger:
    """Initialize audit logger with Flask app"""
    audit_logger.init_app(app)
    return audit_logger

def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance"""
    return audit_logger

def audit_log(
    event_type: AuditEventType,
    message: str = None,
    severity: AuditSeverity = AuditSeverity.MEDIUM,
    **kwargs
):
    """
    Decorator to automatically audit log function calls
    
    Usage:
        @audit_log(AuditEventType.VESSEL_CREATED, "New vessel created")
        def create_vessel(vessel_data):
            # Function implementation
            return vessel
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **dec_kwargs):
            try:
                # Execute function
                result = f(*args, **dec_kwargs)
                
                # Log successful execution
                audit_logger.log_event(
                    event_type=event_type,
                    message=message or f"Function {f.__name__} executed successfully",
                    details={
                        'function_name': f.__name__,
                        'args_count': len(args),
                        'kwargs_count': len(dec_kwargs),
                    },
                    severity=severity,
                    **kwargs
                )
                
                return result
                
            except Exception as e:
                # Log failed execution
                audit_logger.log_event(
                    event_type=AuditEventType.SECURITY_VIOLATION,
                    message=f"Function {f.__name__} failed: {str(e)}",
                    details={
                        'function_name': f.__name__,
                        'error': str(e),
                        'error_type': type(e).__name__,
                    },
                    severity=AuditSeverity.HIGH
                )
                
                raise
        
        return decorated_function
    return decorator