"""
Encrypted Cache System for Stevedores Dashboard 3.0
Secure offline data storage with AES encryption for maritime operations
"""

import os
import json
import base64
import hashlib
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from flask import current_app, g

logger = logging.getLogger(__name__)

class CacheClassification(Enum):
    """Data classification levels for maritime cache"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"

class CacheOperation(Enum):
    """Cache operation types for audit logging"""
    STORE = "store"
    RETRIEVE = "retrieve"
    DELETE = "delete"
    ENCRYPT = "encrypt"
    DECRYPT = "decrypt"
    PURGE = "purge"

@dataclass
class EncryptedCacheEntry:
    """Encrypted cache entry with maritime metadata"""
    
    key: str
    encrypted_data: str
    metadata: Dict[str, Any]
    classification: CacheClassification
    created_at: str
    expires_at: Optional[str]
    access_count: int
    last_accessed: str
    
    # Maritime-specific metadata
    vessel_id: Optional[int] = None
    operation_type: Optional[str] = None
    user_id: Optional[int] = None
    data_hash: Optional[str] = None
    compression_used: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncryptedCacheEntry':
        """Create from dictionary"""
        # Handle enum conversion
        if isinstance(data.get('classification'), str):
            data['classification'] = CacheClassification(data['classification'])
        return cls(**data)
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        if not self.expires_at:
            return False
        
        expiry = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
        return datetime.now(timezone.utc) > expiry

class EncryptedCacheManager:
    """Secure encrypted cache manager for maritime data"""
    
    def __init__(self, cache_dir: str = None, master_key: str = None):
        self.cache_dir = cache_dir or os.path.join('cache', 'encrypted')
        self.master_key = master_key or self._generate_master_key()
        self.cipher_suite = self._initialize_encryption()
        
        # Cache configuration
        self.max_cache_size = 100 * 1024 * 1024  # 100MB
        self.default_ttl = 24 * 3600  # 24 hours
        self.cleanup_interval = 3600  # 1 hour
        
        # Maritime-specific settings
        self.sensitive_patterns = [
            'password', 'token', 'key', 'secret', 'credential',
            'imo_number', 'vessel_registration', 'customs_id'
        ]
        
        # Initialize cache directory
        self._setup_cache_directory()
        
        # Initialize audit logger
        self.audit_logger = self._get_audit_logger()
        
        logger.info(f"Encrypted cache manager initialized: {self.cache_dir}")
    
    def _generate_master_key(self) -> str:
        """Generate master encryption key from environment or create new"""
        
        # Try to get key from environment
        env_key = os.environ.get('STEVEDORES_CACHE_KEY')
        if env_key:
            return env_key
        
        # Try to get key from Flask config
        try:
            if current_app:
                config_key = current_app.config.get('CACHE_ENCRYPTION_KEY')
                if config_key:
                    return config_key
        except RuntimeError:
            pass  # Outside application context
        
        # Generate new key (should be persisted in production)
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(b'stevedores-maritime-cache'))
        
        logger.warning("Generated new cache encryption key - should be persisted for production")
        return key.decode()
    
    def _initialize_encryption(self) -> Fernet:
        """Initialize Fernet encryption suite"""
        try:
            # Ensure key is properly formatted
            if isinstance(self.master_key, str):
                key_bytes = self.master_key.encode()
            else:
                key_bytes = self.master_key
            
            # Create Fernet key from master key
            if len(key_bytes) != 44:  # Standard Fernet key length
                # Derive proper Fernet key from master key
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'stevedores-salt',
                    iterations=100000,
                )
                fernet_key = base64.urlsafe_b64encode(kdf.derive(key_bytes))
            else:
                fernet_key = key_bytes
            
            return Fernet(fernet_key)
            
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            raise
    
    def _setup_cache_directory(self):
        """Set up secure cache directory structure"""
        try:
            # Create main cache directory
            os.makedirs(self.cache_dir, exist_ok=True)
            
            # Create classification-based subdirectories
            for classification in CacheClassification:
                class_dir = os.path.join(self.cache_dir, classification.value)
                os.makedirs(class_dir, exist_ok=True)
                
                # Set restrictive permissions for sensitive data
                if classification in [CacheClassification.CONFIDENTIAL, CacheClassification.RESTRICTED]:
                    try:
                        os.chmod(class_dir, 0o700)
                    except OSError:
                        pass  # May not work on all systems
            
            # Create metadata index directory
            os.makedirs(os.path.join(self.cache_dir, 'index'), exist_ok=True)
            
            logger.info(f"Cache directory structure created: {self.cache_dir}")
            
        except Exception as e:
            logger.error(f"Failed to setup cache directory: {e}")
            raise
    
    def _get_audit_logger(self):
        """Get audit logger for cache operations"""
        try:
            from utils.audit_logger import get_audit_logger
            return get_audit_logger()
        except ImportError:
            logger.warning("Audit logger not available - cache operations will not be audited")
            return None
    
    def _log_cache_operation(
        self, 
        operation: CacheOperation, 
        key: str, 
        classification: CacheClassification,
        success: bool = True,
        details: Dict[str, Any] = None
    ):
        """Log cache operations for security audit"""
        if not self.audit_logger:
            return
        
        try:
            from utils.audit_logger import AuditEventType, AuditSeverity
            
            # Determine severity based on classification and operation
            severity = AuditSeverity.LOW
            if classification in [CacheClassification.CONFIDENTIAL, CacheClassification.RESTRICTED]:
                severity = AuditSeverity.MEDIUM
            if operation == CacheOperation.DELETE:
                severity = AuditSeverity.MEDIUM
            
            self.audit_logger.log_event(
                AuditEventType.DATA_ACCESS if operation == CacheOperation.RETRIEVE else AuditEventType.DATA_MODIFIED,
                f"Cache {operation.value}: {key}",
                details={
                    'cache_operation': operation.value,
                    'cache_key': key,
                    'classification': classification.value,
                    'success': success,
                    **(details or {})
                },
                severity=severity,
                maritime_context={
                    'cache_operation': True,
                    'data_classification': classification.value,
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to log cache operation: {e}")
    
    def _classify_data(self, key: str, data: Any) -> CacheClassification:
        """Automatically classify data based on content and key"""
        
        # Check key for sensitive patterns
        key_lower = key.lower()
        for pattern in self.sensitive_patterns:
            if pattern in key_lower:
                return CacheClassification.CONFIDENTIAL
        
        # Check data content if it's a dictionary
        if isinstance(data, dict):
            data_str = json.dumps(data, default=str).lower()
            for pattern in self.sensitive_patterns:
                if pattern in data_str:
                    return CacheClassification.CONFIDENTIAL
            
            # Maritime-specific classification
            maritime_sensitive_fields = [
                'imo_number', 'vessel_registration', 'customs_declaration',
                'cargo_manifest', 'bill_of_lading', 'inspection_report'
            ]
            
            for field in maritime_sensitive_fields:
                if field in data_str:
                    return CacheClassification.RESTRICTED
        
        # Default to internal for authenticated data
        return CacheClassification.INTERNAL
    
    def _get_cache_file_path(self, key: str, classification: CacheClassification) -> str:
        """Get file path for cache entry"""
        # Hash the key to create safe filename
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        filename = f"{key_hash}.cache"
        return os.path.join(self.cache_dir, classification.value, filename)
    
    def _compress_data(self, data: bytes) -> bytes:
        """Compress data if beneficial"""
        try:
            import gzip
            if len(data) > 1024:  # Only compress larger data
                compressed = gzip.compress(data)
                if len(compressed) < len(data) * 0.9:  # Only if significant compression
                    return compressed
        except Exception:
            pass  # Fallback to uncompressed
        
        return data
    
    def _decompress_data(self, data: bytes, compressed: bool) -> bytes:
        """Decompress data if needed"""
        if not compressed:
            return data
        
        try:
            import gzip
            return gzip.decompress(data)
        except Exception as e:
            logger.error(f"Failed to decompress cache data: {e}")
            raise
    
    def store(
        self,
        key: str,
        data: Any,
        ttl: Optional[int] = None,
        classification: Optional[CacheClassification] = None,
        vessel_id: Optional[int] = None,
        operation_type: Optional[str] = None
    ) -> bool:
        """
        Store data in encrypted cache
        
        Args:
            key: Cache key
            data: Data to cache
            ttl: Time to live in seconds
            classification: Data classification level
            vessel_id: Associated vessel ID
            operation_type: Type of maritime operation
            
        Returns:
            bool: Success status
        """
        try:
            # Auto-classify data if not provided
            if classification is None:
                classification = self._classify_data(key, data)
            
            # Serialize data
            if isinstance(data, (dict, list)):
                data_bytes = json.dumps(data, default=str).encode('utf-8')
            elif isinstance(data, str):
                data_bytes = data.encode('utf-8')
            else:
                data_bytes = str(data).encode('utf-8')
            
            # Compress data if beneficial
            compressed_data = self._compress_data(data_bytes)
            compression_used = len(compressed_data) < len(data_bytes)
            
            # Encrypt data
            encrypted_data = self.cipher_suite.encrypt(compressed_data)
            encrypted_b64 = base64.b64encode(encrypted_data).decode('utf-8')
            
            # Calculate data hash for integrity
            data_hash = hashlib.sha256(data_bytes).hexdigest()
            
            # Create cache entry
            now = datetime.now(timezone.utc)
            expires_at = None
            if ttl:
                expires_at = now + timedelta(seconds=ttl)
            
            # Get user ID from Flask context
            user_id = None
            try:
                if hasattr(g, 'jwt_user_id'):
                    user_id = g.jwt_user_id
                elif hasattr(g, 'current_user') and g.current_user:
                    user_id = g.current_user.id
            except RuntimeError:
                pass  # Outside request context
            
            cache_entry = EncryptedCacheEntry(
                key=key,
                encrypted_data=encrypted_b64,
                metadata={
                    'original_size': len(data_bytes),
                    'compressed_size': len(compressed_data),
                    'encrypted_size': len(encrypted_data),
                    'data_type': type(data).__name__
                },
                classification=classification,
                created_at=now.isoformat(),
                expires_at=expires_at.isoformat() if expires_at else None,
                access_count=0,
                last_accessed=now.isoformat(),
                vessel_id=vessel_id,
                operation_type=operation_type,
                user_id=user_id,
                data_hash=data_hash,
                compression_used=compression_used
            )
            
            # Save to file
            cache_file_path = self._get_cache_file_path(key, classification)
            with open(cache_file_path, 'w') as f:
                json.dump(cache_entry.to_dict(), f)
            
            # Set restrictive permissions for sensitive files
            if classification in [CacheClassification.CONFIDENTIAL, CacheClassification.RESTRICTED]:
                try:
                    os.chmod(cache_file_path, 0o600)
                except OSError:
                    pass
            
            # Log cache operation
            self._log_cache_operation(
                CacheOperation.STORE,
                key,
                classification,
                success=True,
                details={
                    'data_size': len(data_bytes),
                    'compressed': compression_used,
                    'ttl': ttl,
                    'vessel_id': vessel_id,
                    'operation_type': operation_type
                }
            )
            
            logger.debug(f"Stored encrypted cache entry: {key} ({classification.value})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store cache entry {key}: {e}")
            self._log_cache_operation(
                CacheOperation.STORE,
                key,
                classification or CacheClassification.INTERNAL,
                success=False,
                details={'error': str(e)}
            )
            return False
    
    def retrieve(self, key: str, classification: Optional[CacheClassification] = None) -> Optional[Any]:
        """
        Retrieve data from encrypted cache
        
        Args:
            key: Cache key
            classification: Expected data classification
            
        Returns:
            Cached data or None if not found/expired
        """
        try:
            # If classification not provided, try all classifications
            classifications_to_try = [classification] if classification else list(CacheClassification)
            
            for class_level in classifications_to_try:
                cache_file_path = self._get_cache_file_path(key, class_level)
                
                if not os.path.exists(cache_file_path):
                    continue
                
                # Load cache entry
                with open(cache_file_path, 'r') as f:
                    entry_data = json.load(f)
                
                cache_entry = EncryptedCacheEntry.from_dict(entry_data)
                
                # Check if expired
                if cache_entry.is_expired():
                    self._delete_cache_file(cache_file_path, cache_entry.classification)
                    continue
                
                # Decrypt data
                encrypted_data = base64.b64decode(cache_entry.encrypted_data.encode('utf-8'))
                decrypted_data = self.cipher_suite.decrypt(encrypted_data)
                
                # Decompress if needed
                final_data = self._decompress_data(decrypted_data, cache_entry.compression_used)
                
                # Verify data integrity
                data_hash = hashlib.sha256(final_data).hexdigest()
                if data_hash != cache_entry.data_hash:
                    logger.warning(f"Cache integrity check failed for key: {key}")
                    self._delete_cache_file(cache_file_path, cache_entry.classification)
                    continue
                
                # Deserialize data based on original type
                try:
                    if cache_entry.metadata.get('data_type') in ['dict', 'list']:
                        result = json.loads(final_data.decode('utf-8'))
                    else:
                        result = final_data.decode('utf-8')
                except json.JSONDecodeError:
                    result = final_data.decode('utf-8')
                
                # Update access statistics
                cache_entry.access_count += 1
                cache_entry.last_accessed = datetime.now(timezone.utc).isoformat()
                
                # Save updated entry
                with open(cache_file_path, 'w') as f:
                    json.dump(cache_entry.to_dict(), f)
                
                # Log cache operation
                self._log_cache_operation(
                    CacheOperation.RETRIEVE,
                    key,
                    cache_entry.classification,
                    success=True,
                    details={
                        'access_count': cache_entry.access_count,
                        'vessel_id': cache_entry.vessel_id,
                        'operation_type': cache_entry.operation_type
                    }
                )
                
                logger.debug(f"Retrieved encrypted cache entry: {key} ({cache_entry.classification.value})")
                return result
            
            # Not found in any classification
            logger.debug(f"Cache entry not found: {key}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve cache entry {key}: {e}")
            self._log_cache_operation(
                CacheOperation.RETRIEVE,
                key,
                classification or CacheClassification.INTERNAL,
                success=False,
                details={'error': str(e)}
            )
            return None
    
    def delete(self, key: str, classification: Optional[CacheClassification] = None) -> bool:
        """
        Delete cache entry
        
        Args:
            key: Cache key
            classification: Data classification (if known)
            
        Returns:
            bool: Success status
        """
        try:
            deleted = False
            
            # If classification not provided, try all classifications
            classifications_to_try = [classification] if classification else list(CacheClassification)
            
            for class_level in classifications_to_try:
                cache_file_path = self._get_cache_file_path(key, class_level)
                
                if os.path.exists(cache_file_path):
                    deleted = self._delete_cache_file(cache_file_path, class_level)
                    
                    # Log cache operation
                    self._log_cache_operation(
                        CacheOperation.DELETE,
                        key,
                        class_level,
                        success=deleted
                    )
                    
                    if deleted:
                        logger.debug(f"Deleted encrypted cache entry: {key} ({class_level.value})")
                        break
            
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to delete cache entry {key}: {e}")
            return False
    
    def _delete_cache_file(self, file_path: str, classification: CacheClassification) -> bool:
        """Securely delete cache file"""
        try:
            # For sensitive data, overwrite before deletion
            if classification in [CacheClassification.CONFIDENTIAL, CacheClassification.RESTRICTED]:
                try:
                    with open(file_path, 'r+b') as f:
                        length = f.seek(0, 2)
                        f.seek(0)
                        f.write(os.urandom(length))
                        f.flush()
                        os.fsync(f.fileno())
                except Exception:
                    pass  # Fallback to simple deletion
            
            os.unlink(file_path)
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete cache file {file_path}: {e}")
            return False
    
    def exists(self, key: str, classification: Optional[CacheClassification] = None) -> bool:
        """Check if cache entry exists and is not expired"""
        try:
            result = self.retrieve(key, classification)
            return result is not None
        except Exception:
            return False
    
    def clear_expired(self) -> int:
        """Clear all expired cache entries"""
        cleared_count = 0
        
        try:
            for classification in CacheClassification:
                class_dir = os.path.join(self.cache_dir, classification.value)
                
                if not os.path.exists(class_dir):
                    continue
                
                for filename in os.listdir(class_dir):
                    if not filename.endswith('.cache'):
                        continue
                    
                    file_path = os.path.join(class_dir, filename)
                    
                    try:
                        with open(file_path, 'r') as f:
                            entry_data = json.load(f)
                        
                        cache_entry = EncryptedCacheEntry.from_dict(entry_data)
                        
                        if cache_entry.is_expired():
                            if self._delete_cache_file(file_path, classification):
                                cleared_count += 1
                    
                    except Exception as e:
                        logger.warning(f"Failed to check expiry for {file_path}: {e}")
                        # Delete corrupted cache files
                        try:
                            os.unlink(file_path)
                            cleared_count += 1
                        except Exception:
                            pass
            
            if cleared_count > 0:
                logger.info(f"Cleared {cleared_count} expired cache entries")
            
            return cleared_count
            
        except Exception as e:
            logger.error(f"Failed to clear expired cache entries: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            'total_entries': 0,
            'total_size': 0,
            'by_classification': {},
            'by_vessel': {},
            'expired_entries': 0,
            'cache_hit_rate': 0,
            'most_accessed_keys': []
        }
        
        try:
            all_entries = []
            
            for classification in CacheClassification:
                class_dir = os.path.join(self.cache_dir, classification.value)
                class_stats = {'count': 0, 'size': 0, 'expired': 0}
                
                if not os.path.exists(class_dir):
                    stats['by_classification'][classification.value] = class_stats
                    continue
                
                for filename in os.listdir(class_dir):
                    if not filename.endswith('.cache'):
                        continue
                    
                    file_path = os.path.join(class_dir, filename)
                    
                    try:
                        file_size = os.path.getsize(file_path)
                        
                        with open(file_path, 'r') as f:
                            entry_data = json.load(f)
                        
                        cache_entry = EncryptedCacheEntry.from_dict(entry_data)
                        
                        class_stats['count'] += 1
                        class_stats['size'] += file_size
                        
                        if cache_entry.is_expired():
                            class_stats['expired'] += 1
                            stats['expired_entries'] += 1
                        
                        all_entries.append(cache_entry)
                        
                        # Track by vessel
                        if cache_entry.vessel_id:
                            vessel_key = f"vessel_{cache_entry.vessel_id}"
                            if vessel_key not in stats['by_vessel']:
                                stats['by_vessel'][vessel_key] = 0
                            stats['by_vessel'][vessel_key] += 1
                    
                    except Exception:
                        continue
                
                stats['by_classification'][classification.value] = class_stats
                stats['total_entries'] += class_stats['count']
                stats['total_size'] += class_stats['size']
            
            # Calculate most accessed keys
            all_entries.sort(key=lambda x: x.access_count, reverse=True)
            stats['most_accessed_keys'] = [
                {'key': entry.key, 'access_count': entry.access_count}
                for entry in all_entries[:10]
            ]
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return stats
    
    def purge_all(self, classification: Optional[CacheClassification] = None) -> int:
        """Purge all cache entries (or specific classification)"""
        purged_count = 0
        
        try:
            classifications_to_purge = [classification] if classification else list(CacheClassification)
            
            for class_level in classifications_to_purge:
                class_dir = os.path.join(self.cache_dir, class_level.value)
                
                if not os.path.exists(class_dir):
                    continue
                
                for filename in os.listdir(class_dir):
                    if filename.endswith('.cache'):
                        file_path = os.path.join(class_dir, filename)
                        if self._delete_cache_file(file_path, class_level):
                            purged_count += 1
                
                # Log purge operation
                self._log_cache_operation(
                    CacheOperation.PURGE,
                    f"all_{class_level.value}",
                    class_level,
                    success=True,
                    details={'purged_count': purged_count}
                )
            
            logger.info(f"Purged {purged_count} cache entries")
            return purged_count
            
        except Exception as e:
            logger.error(f"Failed to purge cache: {e}")
            return 0

# Global encrypted cache manager
encrypted_cache = EncryptedCacheManager()

def get_encrypted_cache() -> EncryptedCacheManager:
    """Get the global encrypted cache manager"""
    return encrypted_cache

def cache_maritime_data(
    key: str,
    data: Any,
    ttl: Optional[int] = None,
    vessel_id: Optional[int] = None,
    operation_type: Optional[str] = None
) -> bool:
    """
    Convenience function to cache maritime data with automatic classification
    
    Args:
        key: Cache key
        data: Data to cache
        ttl: Time to live in seconds
        vessel_id: Associated vessel ID
        operation_type: Type of maritime operation
        
    Returns:
        bool: Success status
    """
    return encrypted_cache.store(
        key=key,
        data=data,
        ttl=ttl,
        vessel_id=vessel_id,
        operation_type=operation_type
    )

def get_cached_maritime_data(key: str) -> Optional[Any]:
    """
    Convenience function to retrieve cached maritime data
    
    Args:
        key: Cache key
        
    Returns:
        Cached data or None
    """
    return encrypted_cache.retrieve(key)

def clear_vessel_cache(vessel_id: int) -> int:
    """
    Clear all cached data for a specific vessel
    
    Args:
        vessel_id: Vessel ID to clear cache for
        
    Returns:
        Number of entries cleared
    """
    cleared_count = 0
    
    try:
        for classification in CacheClassification:
            class_dir = os.path.join(encrypted_cache.cache_dir, classification.value)
            
            if not os.path.exists(class_dir):
                continue
            
            for filename in os.listdir(class_dir):
                if not filename.endswith('.cache'):
                    continue
                
                file_path = os.path.join(class_dir, filename)
                
                try:
                    with open(file_path, 'r') as f:
                        entry_data = json.load(f)
                    
                    cache_entry = EncryptedCacheEntry.from_dict(entry_data)
                    
                    if cache_entry.vessel_id == vessel_id:
                        if encrypted_cache._delete_cache_file(file_path, classification):
                            cleared_count += 1
                
                except Exception:
                    continue
        
        if cleared_count > 0:
            logger.info(f"Cleared {cleared_count} cache entries for vessel {vessel_id}")
        
        return cleared_count
        
    except Exception as e:
        logger.error(f"Failed to clear vessel cache for {vessel_id}: {e}")
        return 0