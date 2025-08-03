"""
Offline Authentication Manager for Stevedores Dashboard 3.0
Secure offline authentication with encrypted token storage for maritime operations
"""

import os
import json
import hashlib
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from .encrypted_cache import get_encrypted_cache, CacheClassification
from .audit_logger import get_audit_logger, AuditEventType, AuditSeverity

logger = logging.getLogger(__name__)

class OfflineAuthStatus(Enum):
    """Offline authentication status"""
    AUTHENTICATED = "authenticated"
    EXPIRED = "expired"
    INVALID = "invalid"
    PENDING_SYNC = "pending_sync"
    REVOKED = "revoked"
    LOCKED = "locked"

class AuthenticationMethod(Enum):
    """Authentication methods supported offline"""
    PASSWORD = "password"
    PIN = "pin"
    BIOMETRIC = "biometric"
    TOKEN = "token"
    CERTIFICATE = "certificate"

@dataclass
class OfflineAuthToken:
    """Secure offline authentication token"""
    
    token_id: str
    user_id: int
    username: str
    email: str
    
    # Token metadata
    created_at: str
    expires_at: str
    last_used: str
    access_count: int
    
    # Authentication details
    auth_method: AuthenticationMethod
    password_hash: Optional[str]  # For offline password verification
    pin_hash: Optional[str]       # For PIN-based access
    
    # Maritime-specific data
    maritime_roles: List[str]
    vessel_permissions: List[int]
    port_permissions: List[str]
    emergency_access: bool
    
    # Security metadata
    device_fingerprint: str
    session_id: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    
    # Offline capabilities
    offline_permissions: List[str]
    sync_required: bool = False
    failed_attempts: int = 0
    locked_until: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        # Convert enum to string
        data['auth_method'] = self.auth_method.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OfflineAuthToken':
        """Create from dictionary"""
        # Convert string enum back
        data['auth_method'] = AuthenticationMethod(data['auth_method'])
        return cls(**data)
    
    def is_expired(self) -> bool:
        """Check if token has expired"""
        expiry = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
        return datetime.now(timezone.utc) > expiry
    
    def is_locked(self) -> bool:
        """Check if token is locked due to failed attempts"""
        if not self.locked_until:
            return False
        
        lockout_expiry = datetime.fromisoformat(self.locked_until.replace('Z', '+00:00'))
        return datetime.now(timezone.utc) < lockout_expiry
    
    def can_access_vessel(self, vessel_id: int) -> bool:
        """Check if user can access specific vessel"""
        return vessel_id in self.vessel_permissions or self.emergency_access
    
    def can_access_port(self, port_code: str) -> bool:
        """Check if user can access specific port"""
        return port_code in self.port_permissions or self.emergency_access
    
    def has_offline_permission(self, permission: str) -> bool:
        """Check if user has specific offline permission"""
        return permission in self.offline_permissions or self.emergency_access

class OfflineAuthenticationManager:
    """Secure offline authentication manager for maritime operations"""
    
    def __init__(self):
        self.cache = get_encrypted_cache()
        self.audit_logger = get_audit_logger()
        
        # Authentication configuration
        self.config = {
            'max_offline_days': 7,        # Maximum offline authentication period
            'pin_attempts_before_lock': 3, # PIN attempts before lockout
            'lockout_duration_minutes': 30, # Lockout duration
            'password_min_length': 8,     # Minimum password length
            'session_timeout_hours': 8,   # Session timeout for maritime shifts
            'emergency_override_enabled': True,  # Emergency access override
            'biometric_backup_required': True,   # Require backup auth method
        }
        
        # Maritime-specific settings
        self.maritime_config = {
            'emergency_roles': ['port_authority', 'coast_guard', 'pilot'],
            'critical_permissions': [
                'emergency_response', 'vessel_control', 'port_security',
                'customs_clearance', 'damage_reporting'
            ],
            'offline_restrictions': {
                'financial_operations': False,
                'customs_declarations': False,  # Requires online verification
                'emergency_reporting': True,    # Must work offline
                'cargo_tallies': True,
                'vessel_tracking': True
            }
        }
        
        # Initialize encryption for sensitive data
        self.auth_cipher = self._initialize_auth_encryption()
        
        logger.info("Offline authentication manager initialized")
    
    def _initialize_auth_encryption(self) -> Fernet:
        """Initialize encryption specifically for authentication data"""
        try:
            # Generate key from maritime-specific salt
            salt = b'stevedores-maritime-auth-2024'
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            
            # Use a combination of system and maritime identifiers
            key_material = f"maritime-auth-{os.environ.get('STEVEDORES_AUTH_KEY', 'default-key')}".encode()
            key = base64.urlsafe_b64encode(kdf.derive(key_material))
            
            return Fernet(key)
            
        except Exception as e:
            logger.error(f"Failed to initialize auth encryption: {e}")
            raise
    
    def _hash_password(self, password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """Hash password with salt for secure storage"""
        try:
            if salt is None:
                salt = base64.b64encode(os.urandom(32)).decode('utf-8')
            
            # Use PBKDF2 with maritime-specific parameters
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt.encode(),
                iterations=120000,  # High iteration count for security
            )
            
            password_hash = base64.b64encode(kdf.derive(password.encode())).decode('utf-8')
            
            return password_hash, salt
            
        except Exception as e:
            logger.error(f"Failed to hash password: {e}")
            raise
    
    def _verify_password(self, password: str, stored_hash: str, salt: str) -> bool:
        """Verify password against stored hash"""
        try:
            computed_hash, _ = self._hash_password(password, salt)
            return computed_hash == stored_hash
            
        except Exception as e:
            logger.error(f"Password verification failed: {e}")
            return False
    
    def _generate_device_fingerprint(self, user_agent: str, additional_data: Dict[str, Any] = None) -> str:
        """Generate device fingerprint for authentication tracking"""
        try:
            fingerprint_data = {
                'user_agent': user_agent,
                'timestamp': datetime.now().isoformat(),
                'maritime_context': True,
                **(additional_data or {})
            }
            
            fingerprint_json = json.dumps(fingerprint_data, sort_keys=True)
            fingerprint_hash = hashlib.sha256(fingerprint_json.encode()).hexdigest()
            
            return fingerprint_hash[:16]  # Use first 16 characters
            
        except Exception as e:
            logger.warning(f"Failed to generate device fingerprint: {e}")
            return 'unknown-device'
    
    def create_offline_token(
        self,
        user_id: int,
        username: str,
        email: str,
        password: str,
        auth_method: AuthenticationMethod = AuthenticationMethod.PASSWORD,
        maritime_roles: List[str] = None,
        vessel_permissions: List[int] = None,
        port_permissions: List[str] = None,
        user_agent: str = None,
        ip_address: str = None,
        emergency_access: bool = False
    ) -> OfflineAuthToken:
        """
        Create secure offline authentication token
        
        Args:
            user_id: User ID
            username: Username
            email: User email
            password: User password for offline verification
            auth_method: Authentication method
            maritime_roles: User's maritime roles
            vessel_permissions: Vessels user can access
            port_permissions: Ports user can access
            user_agent: Client user agent
            ip_address: Client IP address
            emergency_access: Emergency access override
            
        Returns:
            OfflineAuthToken: Created authentication token
        """
        try:
            # Generate token ID
            token_id = hashlib.sha256(
                f"{user_id}_{username}_{datetime.now().isoformat()}".encode()
            ).hexdigest()[:16]
            
            # Hash password for offline verification
            password_hash, salt = self._hash_password(password)
            
            # Generate session ID
            session_id = hashlib.sha256(
                f"session_{token_id}_{datetime.now().timestamp()}".encode()
            ).hexdigest()[:16]
            
            # Generate device fingerprint
            device_fingerprint = self._generate_device_fingerprint(
                user_agent or 'unknown',
                {'user_id': user_id, 'ip': ip_address}
            )
            
            # Determine offline permissions based on maritime roles
            offline_permissions = self._calculate_offline_permissions(
                maritime_roles or [],
                emergency_access
            )
            
            # Create token
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(days=self.config['max_offline_days'])
            
            token = OfflineAuthToken(
                token_id=token_id,
                user_id=user_id,
                username=username,
                email=email,
                created_at=now.isoformat(),
                expires_at=expires_at.isoformat(),
                last_used=now.isoformat(),
                access_count=0,
                auth_method=auth_method,
                password_hash=f"{password_hash}:{salt}",  # Store hash with salt
                pin_hash=None,
                maritime_roles=maritime_roles or [],
                vessel_permissions=vessel_permissions or [],
                port_permissions=port_permissions or [],
                emergency_access=emergency_access,
                device_fingerprint=device_fingerprint,
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent,
                offline_permissions=offline_permissions
            )
            
            # Encrypt and store token
            encrypted_token_data = self._encrypt_token_data(token.to_dict())
            
            # Store in encrypted cache
            self.cache.store(
                key=f"offline_auth_{token_id}",
                data=encrypted_token_data,
                ttl=self.config['max_offline_days'] * 86400,  # Convert days to seconds
                classification=CacheClassification.CONFIDENTIAL,
                vessel_id=vessel_permissions[0] if vessel_permissions else None,
                operation_type="offline_authentication"
            )
            
            # Store user index for lookups
            self.cache.store(
                key=f"offline_user_index_{user_id}",
                data={'token_id': token_id, 'username': username},
                ttl=self.config['max_offline_days'] * 86400,
                classification=CacheClassification.INTERNAL,
                operation_type="user_index"
            )
            
            # Log token creation
            self.audit_logger.log_authentication_event(
                AuditEventType.TOKEN_ISSUED,
                user_id,
                True,
                details={
                    'token_id': token_id,
                    'auth_method': auth_method.value,
                    'offline_access': True,
                    'emergency_access': emergency_access,
                    'maritime_roles': maritime_roles,
                    'expires_at': expires_at.isoformat(),
                    'device_fingerprint': device_fingerprint
                }
            )
            
            logger.info(f"Created offline authentication token for user {user_id}: {token_id}")
            return token
            
        except Exception as e:
            logger.error(f"Failed to create offline token: {e}")
            raise
    
    def _encrypt_token_data(self, token_data: Dict[str, Any]) -> str:
        """Encrypt token data for secure storage"""
        try:
            token_json = json.dumps(token_data)
            encrypted_data = self.auth_cipher.encrypt(token_json.encode())
            return base64.b64encode(encrypted_data).decode()
            
        except Exception as e:
            logger.error(f"Failed to encrypt token data: {e}")
            raise
    
    def _decrypt_token_data(self, encrypted_data: str) -> Dict[str, Any]:
        """Decrypt token data from storage"""
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            decrypted_bytes = self.auth_cipher.decrypt(encrypted_bytes)
            return json.loads(decrypted_bytes.decode())
            
        except Exception as e:
            logger.error(f"Failed to decrypt token data: {e}")
            raise
    
    def _calculate_offline_permissions(self, maritime_roles: List[str], emergency_access: bool) -> List[str]:
        """Calculate offline permissions based on maritime roles"""
        
        permissions = []
        
        # Emergency access gets all permissions
        if emergency_access:
            return list(self.maritime_config['offline_restrictions'].keys())
        
        # Role-based permissions
        for role in maritime_roles:
            if role == 'stevedore':
                permissions.extend(['cargo_tallies', 'vessel_tracking', 'damage_reporting'])
            elif role == 'vessel_operator':
                permissions.extend(['vessel_tracking', 'cargo_tallies', 'port_communications'])
            elif role == 'port_authority':
                permissions.extend(['vessel_control', 'port_security', 'emergency_response'])
            elif role == 'customs_officer':
                permissions.extend(['cargo_inspection', 'document_review'])
            elif role == 'cargo_inspector':
                permissions.extend(['cargo_tallies', 'damage_reporting', 'quality_control'])
            elif role == 'admin':
                permissions.extend(['system_management', 'user_management'])
        
        # Filter based on offline restrictions
        allowed_permissions = []
        for permission in permissions:
            if self.maritime_config['offline_restrictions'].get(permission, True):
                allowed_permissions.append(permission)
        
        return list(set(allowed_permissions))  # Remove duplicates
    
    def authenticate_offline(
        self,
        username: str,
        password: str,
        pin: Optional[str] = None,
        device_fingerprint: Optional[str] = None
    ) -> Tuple[OfflineAuthStatus, Optional[OfflineAuthToken]]:
        """
        Authenticate user for offline access
        
        Args:
            username: Username
            password: Password (if using password auth)
            pin: PIN (if using PIN auth)
            device_fingerprint: Device fingerprint for security
            
        Returns:
            Tuple of (auth_status, token_if_successful)
        """
        try:
            # Find user's offline token
            token = self._find_user_token(username)
            
            if not token:
                self.audit_logger.log_authentication_event(
                    AuditEventType.LOGIN_FAILURE,
                    None,
                    False,
                    details={'username': username, 'reason': 'no_offline_token'}
                )
                return OfflineAuthStatus.INVALID, None
            
            # Check if token is expired
            if token.is_expired():
                self.audit_logger.log_authentication_event(
                    AuditEventType.LOGIN_FAILURE,
                    token.user_id,
                    False,
                    details={'username': username, 'reason': 'token_expired'}
                )
                return OfflineAuthStatus.EXPIRED, None
            
            # Check if account is locked
            if token.is_locked():
                self.audit_logger.log_authentication_event(
                    AuditEventType.LOGIN_FAILURE,
                    token.user_id,
                    False,
                    details={'username': username, 'reason': 'account_locked'}
                )
                return OfflineAuthStatus.LOCKED, None
            
            # Verify authentication credentials
            auth_success = False
            
            if token.auth_method == AuthenticationMethod.PASSWORD and password:
                auth_success = self._verify_stored_password(password, token.password_hash)
            elif token.auth_method == AuthenticationMethod.PIN and pin:
                auth_success = self._verify_stored_password(pin, token.pin_hash)
            
            if not auth_success:
                # Increment failed attempts
                token.failed_attempts += 1
                
                # Lock account if too many failures
                if token.failed_attempts >= self.config['pin_attempts_before_lock']:
                    lockout_until = datetime.now(timezone.utc) + timedelta(
                        minutes=self.config['lockout_duration_minutes']
                    )
                    token.locked_until = lockout_until.isoformat()
                    
                    self.audit_logger.log_security_event(
                        AuditEventType.SECURITY_VIOLATION,
                        f"Account locked due to failed attempts: {username}",
                        details={'failed_attempts': token.failed_attempts}
                    )
                
                # Update token with failed attempt
                self._update_token(token)
                
                self.audit_logger.log_authentication_event(
                    AuditEventType.LOGIN_FAILURE,
                    token.user_id,
                    False,
                    details={
                        'username': username,
                        'reason': 'invalid_credentials',
                        'failed_attempts': token.failed_attempts
                    }
                )
                
                return OfflineAuthStatus.INVALID, None
            
            # Authentication successful
            token.failed_attempts = 0  # Reset failed attempts
            token.locked_until = None  # Clear any lockout
            token.access_count += 1
            token.last_used = datetime.now(timezone.utc).isoformat()
            
            # Verify device fingerprint if provided
            if device_fingerprint and device_fingerprint != token.device_fingerprint:
                logger.warning(f"Device fingerprint mismatch for user {username}")
                # Still allow access but log security event
                self.audit_logger.log_security_event(
                    AuditEventType.SECURITY_VIOLATION,
                    f"Device fingerprint mismatch for offline auth: {username}",
                    details={
                        'expected': token.device_fingerprint,
                        'received': device_fingerprint
                    }
                )
            
            # Update token
            self._update_token(token)
            
            # Log successful authentication
            self.audit_logger.log_authentication_event(
                AuditEventType.LOGIN_SUCCESS,
                token.user_id,
                True,
                details={
                    'username': username,
                    'offline_access': True,
                    'auth_method': token.auth_method.value,
                    'access_count': token.access_count
                }
            )
            
            logger.info(f"Offline authentication successful for user {username}")
            return OfflineAuthStatus.AUTHENTICATED, token
            
        except Exception as e:
            logger.error(f"Offline authentication error: {e}")
            return OfflineAuthStatus.INVALID, None
    
    def _find_user_token(self, username: str) -> Optional[OfflineAuthToken]:
        """Find user's offline authentication token"""
        try:
            # First, try to find by username in user index
            user_data = None
            for user_id in range(1, 1000):  # Practical limit for searching
                index_data = self.cache.retrieve(f"offline_user_index_{user_id}")
                if index_data and index_data.get('username') == username:
                    user_data = index_data
                    break
            
            if not user_data:
                return None
            
            # Get the token
            token_id = user_data['token_id']
            encrypted_token_data = self.cache.retrieve(f"offline_auth_{token_id}")
            
            if not encrypted_token_data:
                return None
            
            # Decrypt token data
            token_data = self._decrypt_token_data(encrypted_token_data)
            return OfflineAuthToken.from_dict(token_data)
            
        except Exception as e:
            logger.error(f"Failed to find user token for {username}: {e}")
            return None
    
    def _verify_stored_password(self, password: str, stored_hash: str) -> bool:
        """Verify password against stored hash"""
        try:
            if not stored_hash or ':' not in stored_hash:
                return False
            
            hash_part, salt = stored_hash.split(':', 1)
            return self._verify_password(password, hash_part, salt)
            
        except Exception as e:
            logger.error(f"Failed to verify stored password: {e}")
            return False
    
    def _update_token(self, token: OfflineAuthToken):
        """Update token in storage"""
        try:
            encrypted_token_data = self._encrypt_token_data(token.to_dict())
            
            self.cache.store(
                key=f"offline_auth_{token.token_id}",
                data=encrypted_token_data,
                ttl=self.config['max_offline_days'] * 86400,
                classification=CacheClassification.CONFIDENTIAL,
                vessel_id=token.vessel_permissions[0] if token.vessel_permissions else None,
                operation_type="offline_authentication"
            )
            
        except Exception as e:
            logger.error(f"Failed to update token {token.token_id}: {e}")
    
    def revoke_offline_token(self, token_id: str, reason: str = "manual_revocation") -> bool:
        """
        Revoke offline authentication token
        
        Args:
            token_id: Token ID to revoke
            reason: Reason for revocation
            
        Returns:
            bool: Success status
        """
        try:
            # Remove token from cache
            success = self.cache.delete(f"offline_auth_{token_id}")
            
            if success:
                # Log revocation
                self.audit_logger.log_event(
                    AuditEventType.TOKEN_REVOKED,
                    f"Offline token revoked: {token_id}",
                    details={
                        'token_id': token_id,
                        'reason': reason,
                        'revoked_at': datetime.now(timezone.utc).isoformat()
                    },
                    severity=AuditSeverity.MEDIUM
                )
                
                logger.info(f"Revoked offline token: {token_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to revoke offline token {token_id}: {e}")
            return False
    
    def cleanup_expired_tokens(self) -> int:
        """Clean up expired offline authentication tokens"""
        try:
            cleaned_count = 0
            
            # This would ideally iterate through all stored tokens
            # For now, we rely on the cache's own expiration mechanism
            # In a full implementation, we'd maintain a token registry
            
            # Clean up expired cache entries (done by cache manager)
            cleaned_count = self.cache.clear_expired()
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired offline tokens")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired tokens: {e}")
            return 0
    
    def get_offline_auth_status(self) -> Dict[str, Any]:
        """Get overall offline authentication status"""
        try:
            # Get cache statistics
            cache_stats = self.cache.get_cache_stats()
            
            # Filter for authentication entries
            auth_entries = 0
            for classification, stats in cache_stats.get('by_classification', {}).items():
                if classification == 'confidential':  # Auth tokens are confidential
                    auth_entries += stats.get('count', 0)
            
            status = {
                'total_offline_tokens': auth_entries,
                'cache_size': cache_stats.get('total_size', 0),
                'expired_tokens': cache_stats.get('expired_entries', 0),
                'authentication_enabled': True,
                'max_offline_days': self.config['max_offline_days'],
                'lockout_enabled': True,
                'emergency_access_enabled': self.config['emergency_override_enabled']
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get offline auth status: {e}")
            return {}

# Global offline authentication manager
offline_auth = OfflineAuthenticationManager()

def get_offline_auth_manager() -> OfflineAuthenticationManager:
    """Get the global offline authentication manager"""
    return offline_auth

def create_maritime_offline_token(
    user_id: int,
    username: str,
    email: str,
    password: str,
    maritime_roles: List[str],
    vessel_permissions: List[int] = None,
    emergency_access: bool = False
) -> OfflineAuthToken:
    """
    Convenience function to create maritime offline authentication token
    
    Args:
        user_id: User ID
        username: Username
        email: User email
        password: Password for offline verification
        maritime_roles: User's maritime roles
        vessel_permissions: Vessels user can access
        emergency_access: Emergency access override
        
    Returns:
        OfflineAuthToken: Created token
    """
    return offline_auth.create_offline_token(
        user_id=user_id,
        username=username,
        email=email,
        password=password,
        maritime_roles=maritime_roles,
        vessel_permissions=vessel_permissions or [],
        emergency_access=emergency_access
    )

def authenticate_maritime_user_offline(
    username: str,
    password: str
) -> Tuple[OfflineAuthStatus, Optional[OfflineAuthToken]]:
    """
    Convenience function for maritime offline authentication
    
    Args:
        username: Username
        password: Password
        
    Returns:
        Tuple of (auth_status, token_if_successful)
    """
    return offline_auth.authenticate_offline(username, password)