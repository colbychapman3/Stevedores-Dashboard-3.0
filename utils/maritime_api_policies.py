"""
Maritime API Security Policies for Stevedores Dashboard 3.0
Domain-specific security policies and access control
"""

import logging
from typing import Dict, Any, Optional, List, Set
from enum import Enum
from dataclasses import dataclass
from functools import wraps
from flask import request, jsonify, g

logger = logging.getLogger(__name__)

class MaritimeRole(Enum):
    """Maritime operational roles"""
    
    STEVEDORE = "stevedore"                    # Cargo handling operations
    VESSEL_OPERATOR = "vessel_operator"        # Vessel management
    PORT_AUTHORITY = "port_authority"          # Port oversight
    CUSTOMS_OFFICER = "customs_officer"        # Customs clearance
    CARGO_INSPECTOR = "cargo_inspector"        # Quality control
    TERMINAL_OPERATOR = "terminal_operator"    # Terminal management
    PILOT = "pilot"                           # Vessel navigation
    TUGBOAT_OPERATOR = "tugboat_operator"     # Vessel assistance
    ADMIN = "admin"                           # System administration
    AUDITOR = "auditor"                       # Compliance monitoring

class MaritimePermission(Enum):
    """Maritime operational permissions"""
    
    # Vessel operations
    VIEW_VESSELS = "vessels.view"
    CREATE_VESSEL = "vessels.create"
    UPDATE_VESSEL = "vessels.update"
    DELETE_VESSEL = "vessels.delete"
    MANAGE_VESSEL_STATUS = "vessels.manage_status"
    
    # Cargo operations
    VIEW_CARGO = "cargo.view"
    CREATE_CARGO_TALLY = "cargo.create_tally"
    UPDATE_CARGO_TALLY = "cargo.update_tally"
    DELETE_CARGO_TALLY = "cargo.delete_tally"
    APPROVE_CARGO_OPERATIONS = "cargo.approve_operations"
    
    # Document management
    VIEW_DOCUMENTS = "documents.view"
    UPLOAD_DOCUMENTS = "documents.upload"
    DELETE_DOCUMENTS = "documents.delete"
    APPROVE_DOCUMENTS = "documents.approve"
    EXPORT_DOCUMENTS = "documents.export"
    
    # Sync operations
    SYNC_DATA = "sync.data"
    RESOLVE_CONFLICTS = "sync.resolve_conflicts"
    VIEW_SYNC_STATUS = "sync.view_status"
    
    # Reporting and analytics
    VIEW_REPORTS = "reports.view"
    CREATE_REPORTS = "reports.create"
    EXPORT_REPORTS = "reports.export"
    VIEW_ANALYTICS = "analytics.view"
    
    # Administrative functions
    MANAGE_USERS = "admin.manage_users"
    VIEW_AUDIT_LOGS = "admin.view_audit_logs"
    MANAGE_SYSTEM = "admin.manage_system"
    VIEW_PERFORMANCE = "admin.view_performance"
    
    # Maritime compliance
    VIEW_COMPLIANCE_DATA = "compliance.view_data"
    MANAGE_COMPLIANCE = "compliance.manage"
    AUDIT_OPERATIONS = "compliance.audit_operations"

@dataclass
class MaritimeSecurityPolicy:
    """Maritime security policy definition"""
    
    name: str
    description: str
    roles: Set[MaritimeRole]
    permissions: Set[MaritimePermission]
    restrictions: Dict[str, Any]
    time_restrictions: Optional[Dict[str, Any]] = None
    location_restrictions: Optional[List[str]] = None
    data_classification_access: Optional[List[str]] = None

class MaritimePolicyManager:
    """Maritime API security policy manager"""
    
    def __init__(self):
        self.policies = {}
        self.role_permissions = {}
        self._initialize_default_policies()
    
    def _initialize_default_policies(self):
        """Initialize default maritime security policies"""
        
        # Stevedore policy - cargo handling operations
        self.add_policy(MaritimeSecurityPolicy(
            name="stevedore_operations",
            description="Cargo handling and tally operations",
            roles={MaritimeRole.STEVEDORE},
            permissions={
                MaritimePermission.VIEW_VESSELS,
                MaritimePermission.VIEW_CARGO,
                MaritimePermission.CREATE_CARGO_TALLY,
                MaritimePermission.UPDATE_CARGO_TALLY,
                MaritimePermission.VIEW_DOCUMENTS,
                MaritimePermission.SYNC_DATA,
            },
            restrictions={
                'max_cargo_tally_per_hour': 100,
                'allowed_vessel_types': ['container', 'bulk_carrier', 'general_cargo'],
                'require_supervisor_approval': False,
            },
            time_restrictions={
                'allowed_hours': list(range(6, 22)),  # 6 AM to 10 PM
                'timezone': 'local',
            },
            data_classification_access=['public', 'internal']
        ))
        
        # Vessel operator policy - vessel management
        self.add_policy(MaritimeSecurityPolicy(
            name="vessel_operations",
            description="Vessel management and status updates",
            roles={MaritimeRole.VESSEL_OPERATOR},
            permissions={
                MaritimePermission.VIEW_VESSELS,
                MaritimePermission.UPDATE_VESSEL,
                MaritimePermission.MANAGE_VESSEL_STATUS,
                MaritimePermission.VIEW_CARGO,
                MaritimePermission.VIEW_DOCUMENTS,
                MaritimePermission.UPLOAD_DOCUMENTS,
                MaritimePermission.SYNC_DATA,
                MaritimePermission.VIEW_REPORTS,
            },
            restrictions={
                'vessel_access_scope': 'assigned_vessels_only',
                'max_vessel_updates_per_day': 50,
                'require_authentication_renewal': 8,  # hours
            },
            data_classification_access=['public', 'internal', 'confidential']
        ))
        
        # Port authority policy - oversight and regulation
        self.add_policy(MaritimeSecurityPolicy(
            name="port_authority",
            description="Port oversight and regulatory compliance",
            roles={MaritimeRole.PORT_AUTHORITY},
            permissions={
                MaritimePermission.VIEW_VESSELS,
                MaritimePermission.CREATE_VESSEL,
                MaritimePermission.UPDATE_VESSEL,
                MaritimePermission.MANAGE_VESSEL_STATUS,
                MaritimePermission.VIEW_CARGO,
                MaritimePermission.APPROVE_CARGO_OPERATIONS,
                MaritimePermission.VIEW_DOCUMENTS,
                MaritimePermission.APPROVE_DOCUMENTS,
                MaritimePermission.VIEW_REPORTS,
                MaritimePermission.CREATE_REPORTS,
                MaritimePermission.VIEW_ANALYTICS,
                MaritimePermission.VIEW_COMPLIANCE_DATA,
                MaritimePermission.AUDIT_OPERATIONS,
            },
            restrictions={
                'full_port_access': True,
                'override_permissions': ['cargo_approval', 'document_approval'],
                'audit_all_actions': True,
            },
            data_classification_access=['public', 'internal', 'confidential', 'restricted']
        ))
        
        # Customs officer policy - customs clearance and inspection
        self.add_policy(MaritimeSecurityPolicy(
            name="customs_operations",
            description="Customs clearance and cargo inspection",
            roles={MaritimeRole.CUSTOMS_OFFICER},
            permissions={
                MaritimePermission.VIEW_VESSELS,
                MaritimePermission.VIEW_CARGO,
                MaritimePermission.VIEW_DOCUMENTS,
                MaritimePermission.UPLOAD_DOCUMENTS,
                MaritimePermission.APPROVE_DOCUMENTS,
                MaritimePermission.VIEW_REPORTS,
                MaritimePermission.EXPORT_DOCUMENTS,
                MaritimePermission.VIEW_COMPLIANCE_DATA,
            },
            restrictions={
                'document_types': ['customs_declaration', 'inspection_report', 'bill_of_lading'],
                'vessel_inspection_access': True,
                'require_digital_signature': True,
            },
            data_classification_access=['public', 'internal', 'confidential', 'restricted']
        ))
        
        # Administrator policy - full system access
        self.add_policy(MaritimeSecurityPolicy(
            name="system_administration",
            description="Full system administration access",
            roles={MaritimeRole.ADMIN},
            permissions=set(MaritimePermission),  # All permissions
            restrictions={
                'require_mfa': True,
                'session_timeout': 4,  # hours
                'audit_all_actions': True,
                'require_approval_for_destructive_operations': True,
            },
            data_classification_access=['public', 'internal', 'confidential', 'restricted']
        ))
        
        # Map roles to their default permissions
        self._build_role_permission_map()
    
    def add_policy(self, policy: MaritimeSecurityPolicy):
        """Add a maritime security policy"""
        self.policies[policy.name] = policy
        logger.info(f"Added maritime policy: {policy.name}")
    
    def get_policy(self, name: str) -> Optional[MaritimeSecurityPolicy]:
        """Get a maritime security policy by name"""
        return self.policies.get(name)
    
    def _build_role_permission_map(self):
        """Build mapping of roles to permissions"""
        self.role_permissions = {}
        
        for policy in self.policies.values():
            for role in policy.roles:
                if role not in self.role_permissions:
                    self.role_permissions[role] = set()
                self.role_permissions[role].update(policy.permissions)
    
    def get_role_permissions(self, role: MaritimeRole) -> Set[MaritimePermission]:
        """Get permissions for a maritime role"""
        return self.role_permissions.get(role, set())
    
    def check_permission(
        self, 
        user_roles: List[MaritimeRole], 
        required_permission: MaritimePermission,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if user roles have required permission
        
        Args:
            user_roles: List of user's maritime roles
            required_permission: Required permission
            context: Additional context for policy evaluation
            
        Returns:
            bool: True if permission granted
        """
        # Check if any role has the required permission
        for role in user_roles:
            role_permissions = self.get_role_permissions(role)
            if required_permission in role_permissions:
                # Additional context-based checks
                if context and not self._check_policy_restrictions(role, context):
                    continue
                return True
        
        return False
    
    def _check_policy_restrictions(
        self, 
        role: MaritimeRole, 
        context: Dict[str, Any]
    ) -> bool:
        """Check policy-specific restrictions"""
        try:
            # Find policy for role
            policy = None
            for p in self.policies.values():
                if role in p.roles:
                    policy = p
                    break
            
            if not policy:
                return True  # No restrictions if no policy found
            
            # Check time restrictions
            if policy.time_restrictions:
                if not self._check_time_restrictions(policy.time_restrictions, context):
                    return False
            
            # Check location restrictions
            if policy.location_restrictions:
                user_location = context.get('location')
                if user_location and user_location not in policy.location_restrictions:
                    return False
            
            # Check data classification access
            if policy.data_classification_access:
                required_classification = context.get('data_classification')
                if (required_classification and 
                    required_classification not in policy.data_classification_access):
                    return False
            
            # Check specific restrictions
            restrictions = policy.restrictions
            
            # Example: vessel access scope
            if 'vessel_access_scope' in restrictions:
                if restrictions['vessel_access_scope'] == 'assigned_vessels_only':
                    vessel_id = context.get('vessel_id')
                    assigned_vessels = context.get('assigned_vessels', [])
                    if vessel_id and vessel_id not in assigned_vessels:
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking policy restrictions: {e}")
            return False
    
    def _check_time_restrictions(
        self, 
        time_restrictions: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> bool:
        """Check time-based access restrictions"""
        try:
            from datetime import datetime
            
            allowed_hours = time_restrictions.get('allowed_hours')
            if allowed_hours:
                current_hour = datetime.now().hour
                if current_hour not in allowed_hours:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking time restrictions: {e}")
            return True  # Allow access on error
    
    def get_user_maritime_context(self, user_id: int) -> Dict[str, Any]:
        """Get maritime context for user (placeholder for database lookup)"""
        # In production, this would query user roles from database
        return {
            'roles': [MaritimeRole.STEVEDORE],  # Default role
            'assigned_vessels': [],
            'location': None,
            'shift_hours': list(range(6, 18)),  # Day shift
        }

# Global policy manager
policy_manager = MaritimePolicyManager()

def get_policy_manager() -> MaritimePolicyManager:
    """Get the global maritime policy manager"""
    return policy_manager

def require_maritime_permission(permission: MaritimePermission):
    """
    Decorator to require specific maritime permission
    
    Args:
        permission: Required maritime permission
    
    Usage:
        @app.route('/api/vessels', methods=['POST'])
        @require_maritime_permission(MaritimePermission.CREATE_VESSEL)
        def create_vessel():
            return jsonify({'success': True})
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get user context
            user_id = getattr(g, 'jwt_user_id', None)
            if not user_id:
                return jsonify({
                    'success': False,
                    'error': 'Authentication required',
                    'required_permission': permission.value
                }), 401
            
            # Get user maritime context
            maritime_context = policy_manager.get_user_maritime_context(user_id)
            user_roles = maritime_context.get('roles', [])
            
            # Prepare context for permission check
            context = {
                'user_id': user_id,
                'endpoint': request.endpoint,
                'method': request.method,
                'vessel_id': kwargs.get('vessel_id'),
                'assigned_vessels': maritime_context.get('assigned_vessels', []),
                'location': maritime_context.get('location'),
            }
            
            # Check permission
            if not policy_manager.check_permission(user_roles, permission, context):
                return jsonify({
                    'success': False,
                    'error': 'Insufficient maritime permissions',
                    'required_permission': permission.value,
                    'user_roles': [role.value for role in user_roles]
                }), 403
            
            # Store maritime context in g for use in endpoint
            g.maritime_context = maritime_context
            g.maritime_roles = user_roles
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def require_maritime_role(*required_roles: MaritimeRole):
    """
    Decorator to require specific maritime roles
    
    Args:
        required_roles: Required maritime roles
    
    Usage:
        @app.route('/api/admin/users')
        @require_maritime_role(MaritimeRole.ADMIN, MaritimeRole.PORT_AUTHORITY)
        def admin_endpoint():
            return jsonify({'data': 'admin only'})
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = getattr(g, 'jwt_user_id', None)
            if not user_id:
                return jsonify({
                    'success': False,
                    'error': 'Authentication required'
                }), 401
            
            # Get user roles
            maritime_context = policy_manager.get_user_maritime_context(user_id)
            user_roles = set(maritime_context.get('roles', []))
            required_roles_set = set(required_roles)
            
            # Check if user has any of the required roles
            if not user_roles.intersection(required_roles_set):
                return jsonify({
                    'success': False,
                    'error': 'Insufficient maritime role',
                    'required_roles': [role.value for role in required_roles],
                    'user_roles': [role.value for role in user_roles]
                }), 403
            
            g.maritime_context = maritime_context
            g.maritime_roles = list(user_roles)
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def maritime_data_classification(classification: str):
    """
    Decorator to enforce data classification access control
    
    Args:
        classification: Data classification level
    
    Usage:
        @app.route('/api/restricted-data')
        @maritime_data_classification('restricted')
        def restricted_endpoint():
            return jsonify({'sensitive': 'data'})
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = getattr(g, 'jwt_user_id', None)
            if not user_id:
                return jsonify({
                    'success': False,
                    'error': 'Authentication required'
                }), 401
            
            # Get user context and check data classification access
            maritime_context = policy_manager.get_user_maritime_context(user_id)
            user_roles = maritime_context.get('roles', [])
            
            # Check if any role allows access to this classification level
            access_allowed = False
            for role in user_roles:
                for policy in policy_manager.policies.values():
                    if (role in policy.roles and 
                        policy.data_classification_access and
                        classification in policy.data_classification_access):
                        access_allowed = True
                        break
                if access_allowed:
                    break
            
            if not access_allowed:
                return jsonify({
                    'success': False,
                    'error': 'Insufficient data classification access',
                    'required_classification': classification,
                    'user_roles': [role.value for role in user_roles]
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator