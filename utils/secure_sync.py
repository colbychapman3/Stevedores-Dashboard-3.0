"""
Secure Synchronization Manager for Stevedores Dashboard 3.0
End-to-end encrypted synchronization with conflict resolution for maritime operations
"""

import os
import json
import hashlib
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from cryptography.fernet import Fernet
from flask import current_app, g

from .encrypted_cache import get_encrypted_cache, CacheClassification
from .audit_logger import get_audit_logger, AuditEventType, AuditSeverity

logger = logging.getLogger(__name__)

class SyncOperation(Enum):
    """Synchronization operation types"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RECONCILE = "reconcile"
    CONFLICT_RESOLVE = "conflict_resolve"

class SyncStatus(Enum):
    """Synchronization status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"
    CANCELLED = "cancelled"

class ConflictResolution(Enum):
    """Conflict resolution strategies"""
    CLIENT_WINS = "client_wins"
    SERVER_WINS = "server_wins"
    MERGE = "merge"
    MANUAL = "manual"
    TIMESTAMP_WINS = "timestamp_wins"
    MARITIME_PRIORITY = "maritime_priority"

@dataclass
class SyncTransaction:
    """Secure synchronization transaction"""
    
    transaction_id: str
    operation: SyncOperation
    table_name: str
    record_id: str
    encrypted_data: str
    data_hash: str
    timestamp: str
    user_id: Optional[int]
    vessel_id: Optional[int]
    
    # Synchronization metadata
    status: SyncStatus
    retry_count: int
    max_retries: int
    priority: int
    
    # Maritime-specific metadata
    operation_type: Optional[str] = None
    maritime_urgency: str = "normal"  # normal, urgent, critical
    port_context: Optional[str] = None
    compliance_required: bool = False
    
    # Conflict resolution
    conflict_data: Optional[Dict[str, Any]] = None
    resolution_strategy: Optional[ConflictResolution] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        # Convert enums to strings
        data['operation'] = self.operation.value
        data['status'] = self.status.value
        if self.resolution_strategy:
            data['resolution_strategy'] = self.resolution_strategy.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SyncTransaction':
        """Create from dictionary"""
        # Convert string enums back
        data['operation'] = SyncOperation(data['operation'])
        data['status'] = SyncStatus(data['status'])
        if data.get('resolution_strategy'):
            data['resolution_strategy'] = ConflictResolution(data['resolution_strategy'])
        return cls(**data)
    
    def is_expired(self) -> bool:
        """Check if transaction has expired"""
        created = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        expiry_hours = 24 if self.maritime_urgency == "normal" else 6
        return datetime.now(timezone.utc) > created + timedelta(hours=expiry_hours)

class SecureSyncManager:
    """Secure synchronization manager with maritime-specific features"""
    
    def __init__(self):
        self.cache = get_encrypted_cache()
        self.audit_logger = get_audit_logger()
        
        # Synchronization configuration
        self.sync_queue_dir = os.path.join('sync', 'queue')
        self.conflict_dir = os.path.join('sync', 'conflicts')
        self.backup_dir = os.path.join('sync', 'backups')
        
        # Maritime-specific settings
        self.priority_tables = {
            'vessels': 10,
            'cargo_tallies': 9,
            'emergency_reports': 10,
            'damage_reports': 8,
            'customs_declarations': 7,
            'manifests': 6,
            'users': 5,
            'settings': 3
        }
        
        # Conflict resolution rules
        self.conflict_rules = {
            'vessels': ConflictResolution.MARITIME_PRIORITY,
            'cargo_tallies': ConflictResolution.TIMESTAMP_WINS,
            'emergency_reports': ConflictResolution.CLIENT_WINS,
            'damage_reports': ConflictResolution.MERGE,
            'users': ConflictResolution.SERVER_WINS
        }
        
        # Initialize directories
        self._setup_sync_directories()
        
        logger.info("Secure sync manager initialized for maritime operations")
    
    def _setup_sync_directories(self):
        """Set up secure synchronization directory structure"""
        try:
            for directory in [self.sync_queue_dir, self.conflict_dir, self.backup_dir]:
                os.makedirs(directory, exist_ok=True)
                
                # Set restrictive permissions
                try:
                    os.chmod(directory, 0o700)
                except OSError:
                    pass
            
            logger.info("Sync directory structure created")
            
        except Exception as e:
            logger.error(f"Failed to setup sync directories: {e}")
            raise
    
    def _encrypt_sync_data(self, data: Any) -> Tuple[str, str]:
        """Encrypt data for synchronization and return encrypted data + hash"""
        try:
            # Serialize data
            if isinstance(data, (dict, list)):
                data_json = json.dumps(data, default=str, sort_keys=True)
            else:
                data_json = str(data)
            
            data_bytes = data_json.encode('utf-8')
            
            # Calculate hash before encryption
            data_hash = hashlib.sha256(data_bytes).hexdigest()
            
            # Encrypt using cache encryption system
            encrypted_data = self.cache.cipher_suite.encrypt(data_bytes)
            encrypted_b64 = encrypted_data.hex()
            
            return encrypted_b64, data_hash
            
        except Exception as e:
            logger.error(f"Failed to encrypt sync data: {e}")
            raise
    
    def _decrypt_sync_data(self, encrypted_data: str, expected_hash: str) -> Any:
        """Decrypt and verify synchronization data"""
        try:
            # Decrypt data
            encrypted_bytes = bytes.fromhex(encrypted_data)
            decrypted_bytes = self.cache.cipher_suite.decrypt(encrypted_bytes)
            
            # Verify hash
            actual_hash = hashlib.sha256(decrypted_bytes).hexdigest()
            if actual_hash != expected_hash:
                raise ValueError("Data integrity check failed - hash mismatch")
            
            # Deserialize
            data_str = decrypted_bytes.decode('utf-8')
            try:
                return json.loads(data_str)
            except json.JSONDecodeError:
                return data_str
            
        except Exception as e:
            logger.error(f"Failed to decrypt sync data: {e}")
            raise
    
    def _get_transaction_priority(self, table_name: str, operation: SyncOperation, data: Dict[str, Any]) -> int:
        """Calculate transaction priority based on maritime urgency"""
        base_priority = self.priority_tables.get(table_name, 5)
        
        # Emergency and damage reports get highest priority
        if table_name in ['emergency_reports', 'damage_reports']:
            return 10
        
        # Vessel status changes are high priority
        if table_name == 'vessels' and operation == SyncOperation.UPDATE:
            status = data.get('status', '')
            if status in ['emergency', 'distress', 'aground']:
                return 10
            elif status in ['arrived', 'departed', 'berthed']:
                return 9
        
        # Cargo operations during working hours
        if table_name == 'cargo_tallies':
            return 9 if self._is_working_hours() else 7
        
        return base_priority
    
    def _is_working_hours(self) -> bool:
        """Check if current time is within maritime working hours"""
        now = datetime.now()
        hour = now.hour
        # Maritime operations typically 06:00 - 22:00
        return 6 <= hour <= 22
    
    def _get_user_id(self) -> Optional[int]:
        """Get current user ID from Flask context"""
        try:
            if hasattr(g, 'jwt_user_id'):
                return g.jwt_user_id
            elif hasattr(g, 'current_user') and g.current_user:
                return g.current_user.id
        except RuntimeError:
            pass  # Outside request context
        return None
    
    def queue_sync_operation(
        self,
        operation: SyncOperation,
        table_name: str,
        record_id: str,
        data: Dict[str, Any],
        vessel_id: Optional[int] = None,
        operation_type: Optional[str] = None,
        maritime_urgency: str = "normal",
        compliance_required: bool = False
    ) -> str:
        """
        Queue a synchronization operation with encryption
        
        Args:
            operation: Type of sync operation
            table_name: Database table name
            record_id: Record identifier
            data: Data to synchronize
            vessel_id: Associated vessel ID
            operation_type: Type of maritime operation
            maritime_urgency: Urgency level (normal, urgent, critical)
            compliance_required: Whether operation requires compliance logging
            
        Returns:
            str: Transaction ID
        """
        try:
            # Generate transaction ID
            transaction_id = hashlib.sha256(
                f"{table_name}_{record_id}_{operation.value}_{datetime.now().isoformat()}".encode()
            ).hexdigest()[:16]
            
            # Encrypt data
            encrypted_data, data_hash = self._encrypt_sync_data(data)
            
            # Calculate priority
            priority = self._get_transaction_priority(table_name, operation, data)
            
            # Create transaction
            transaction = SyncTransaction(
                transaction_id=transaction_id,
                operation=operation,
                table_name=table_name,
                record_id=record_id,
                encrypted_data=encrypted_data,
                data_hash=data_hash,
                timestamp=datetime.now(timezone.utc).isoformat(),
                user_id=self._get_user_id(),
                vessel_id=vessel_id,
                status=SyncStatus.PENDING,
                retry_count=0,
                max_retries=3 if maritime_urgency == "normal" else 5,
                priority=priority,
                operation_type=operation_type,
                maritime_urgency=maritime_urgency,
                compliance_required=compliance_required
            )
            
            # Save to queue
            queue_file = os.path.join(self.sync_queue_dir, f"{transaction_id}.sync")
            with open(queue_file, 'w') as f:
                json.dump(transaction.to_dict(), f)
            
            # Cache transaction for quick access
            self.cache.store(
                key=f"sync_transaction_{transaction_id}",
                data=transaction.to_dict(),
                ttl=86400,  # 24 hours
                classification=CacheClassification.INTERNAL,
                vessel_id=vessel_id,
                operation_type="sync_operation"
            )
            
            # Log sync operation
            self.audit_logger.log_event(
                AuditEventType.DATA_SYNC,
                f"Sync operation queued: {operation.value} {table_name}",
                details={
                    'transaction_id': transaction_id,
                    'table_name': table_name,
                    'record_id': record_id,
                    'operation': operation.value,
                    'priority': priority,
                    'maritime_urgency': maritime_urgency,
                    'vessel_id': vessel_id,
                    'compliance_required': compliance_required
                },
                severity=AuditSeverity.LOW if maritime_urgency == "normal" else AuditSeverity.MEDIUM,
                maritime_context={
                    'sync_operation': True,
                    'table_name': table_name,
                    'maritime_urgency': maritime_urgency,
                    'vessel_id': vessel_id
                }
            )
            
            logger.info(f"Queued sync operation: {transaction_id} ({operation.value} {table_name})")
            return transaction_id
            
        except Exception as e:
            logger.error(f"Failed to queue sync operation: {e}")
            raise
    
    def get_pending_transactions(self, limit: int = 50) -> List[SyncTransaction]:
        """Get pending synchronization transactions ordered by priority"""
        try:
            transactions = []
            
            # Get all sync files
            if not os.path.exists(self.sync_queue_dir):
                return transactions
            
            for filename in os.listdir(self.sync_queue_dir):
                if not filename.endswith('.sync'):
                    continue
                
                file_path = os.path.join(self.sync_queue_dir, filename)
                
                try:
                    with open(file_path, 'r') as f:
                        transaction_data = json.load(f)
                    
                    transaction = SyncTransaction.from_dict(transaction_data)
                    
                    # Skip expired transactions
                    if transaction.is_expired():
                        os.unlink(file_path)
                        continue
                    
                    # Only include pending transactions
                    if transaction.status == SyncStatus.PENDING:
                        transactions.append(transaction)
                
                except Exception as e:
                    logger.warning(f"Failed to load sync transaction {filename}: {e}")
                    # Remove corrupted files
                    try:
                        os.unlink(file_path)
                    except Exception:
                        pass
            
            # Sort by priority (higher first) and then by timestamp
            transactions.sort(key=lambda x: (-x.priority, x.timestamp))
            
            return transactions[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get pending transactions: {e}")
            return []
    
    def process_sync_transaction(self, transaction: SyncTransaction) -> bool:
        """
        Process a synchronization transaction with conflict detection
        
        Args:
            transaction: Transaction to process
            
        Returns:
            bool: Success status
        """
        try:
            # Update transaction status
            transaction.status = SyncStatus.IN_PROGRESS
            self._save_transaction(transaction)
            
            # Decrypt data
            decrypted_data = self._decrypt_sync_data(
                transaction.encrypted_data,
                transaction.data_hash
            )
            
            # Check for conflicts
            conflict_data = self._check_for_conflicts(transaction, decrypted_data)
            
            if conflict_data:
                # Handle conflict
                return self._handle_sync_conflict(transaction, decrypted_data, conflict_data)
            
            # No conflict - proceed with sync
            success = self._execute_sync_operation(transaction, decrypted_data)
            
            if success:
                transaction.status = SyncStatus.COMPLETED
                self._cleanup_transaction(transaction)
                
                # Log successful sync
                self.audit_logger.log_maritime_operation(
                    AuditEventType.DATA_SYNC,
                    f"Sync completed: {transaction.operation.value} {transaction.table_name}",
                    vessel_id=transaction.vessel_id,
                    details={
                        'transaction_id': transaction.transaction_id,
                        'table_name': transaction.table_name,
                        'record_id': transaction.record_id,
                        'retry_count': transaction.retry_count
                    }
                )
                
                logger.info(f"Sync transaction completed: {transaction.transaction_id}")
                return True
            else:
                # Retry logic
                transaction.retry_count += 1
                
                if transaction.retry_count >= transaction.max_retries:
                    transaction.status = SyncStatus.FAILED
                    logger.error(f"Sync transaction failed after {transaction.max_retries} retries: {transaction.transaction_id}")
                else:
                    transaction.status = SyncStatus.PENDING
                    logger.warning(f"Sync transaction retry {transaction.retry_count}: {transaction.transaction_id}")
                
                self._save_transaction(transaction)
                return False
                
        except Exception as e:
            logger.error(f"Failed to process sync transaction {transaction.transaction_id}: {e}")
            
            transaction.status = SyncStatus.FAILED
            self._save_transaction(transaction)
            
            # Log sync failure
            self.audit_logger.log_security_event(
                AuditEventType.SECURITY_VIOLATION,
                f"Sync transaction failed: {str(e)}",
                details={
                    'transaction_id': transaction.transaction_id,
                    'table_name': transaction.table_name,
                    'error': str(e)
                }
            )
            
            return False
    
    def _check_for_conflicts(self, transaction: SyncTransaction, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check for synchronization conflicts"""
        try:
            # This would integrate with the database layer to check for conflicts
            # For now, return None (no conflicts)
            # In a real implementation, this would:
            # 1. Query current server state
            # 2. Compare timestamps and data hashes
            # 3. Detect conflicting changes
            # 4. Return conflict information if found
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to check for conflicts: {e}")
            return None
    
    def _handle_sync_conflict(
        self,
        transaction: SyncTransaction,
        client_data: Dict[str, Any],
        server_data: Dict[str, Any]
    ) -> bool:
        """Handle synchronization conflicts based on resolution strategy"""
        try:
            # Get resolution strategy
            resolution = self.conflict_rules.get(
                transaction.table_name,
                ConflictResolution.MANUAL
            )
            
            # Apply conflict resolution
            if resolution == ConflictResolution.CLIENT_WINS:
                resolved_data = client_data
                
            elif resolution == ConflictResolution.SERVER_WINS:
                resolved_data = server_data
                
            elif resolution == ConflictResolution.TIMESTAMP_WINS:
                client_timestamp = client_data.get('updated_at', transaction.timestamp)
                server_timestamp = server_data.get('updated_at', '')
                
                if client_timestamp > server_timestamp:
                    resolved_data = client_data
                else:
                    resolved_data = server_data
                    
            elif resolution == ConflictResolution.MARITIME_PRIORITY:
                # Maritime-specific conflict resolution
                resolved_data = self._resolve_maritime_conflict(
                    transaction, client_data, server_data
                )
                
            elif resolution == ConflictResolution.MERGE:
                resolved_data = self._merge_data(client_data, server_data)
                
            else:  # MANUAL
                # Save conflict for manual resolution
                return self._save_conflict_for_manual_resolution(
                    transaction, client_data, server_data
                )
            
            # Execute with resolved data
            success = self._execute_sync_operation(transaction, resolved_data)
            
            if success:
                transaction.status = SyncStatus.COMPLETED
                transaction.resolution_strategy = resolution
                
                # Log conflict resolution
                self.audit_logger.log_event(
                    AuditEventType.DATA_SYNC,
                    f"Sync conflict resolved: {resolution.value}",
                    details={
                        'transaction_id': transaction.transaction_id,
                        'resolution_strategy': resolution.value,
                        'table_name': transaction.table_name
                    },
                    severity=AuditSeverity.MEDIUM
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to handle sync conflict: {e}")
            return False
    
    def _resolve_maritime_conflict(
        self,
        transaction: SyncTransaction,
        client_data: Dict[str, Any],
        server_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolve conflicts using maritime-specific rules"""
        
        # Emergency and safety data always wins
        if transaction.table_name in ['emergency_reports', 'damage_reports']:
            return client_data  # Latest report is most important
        
        # Vessel status changes - most urgent wins
        if transaction.table_name == 'vessels':
            client_status = client_data.get('status', '')
            server_status = server_data.get('status', '')
            
            # Emergency statuses take priority
            emergency_statuses = ['emergency', 'distress', 'aground', 'collision']
            
            if client_status in emergency_statuses:
                return client_data
            elif server_status in emergency_statuses:
                return server_data
            
            # Operational statuses by importance
            status_priority = {
                'departed': 10, 'arrived': 9, 'berthed': 8, 'operations_active': 7,
                'operations_complete': 6, 'expected': 5, 'delayed': 4
            }
            
            client_priority = status_priority.get(client_status, 0)
            server_priority = status_priority.get(server_status, 0)
            
            return client_data if client_priority >= server_priority else server_data
        
        # Cargo tallies - combine counts
        if transaction.table_name == 'cargo_tallies':
            merged = server_data.copy()
            merged['cargo_count'] = client_data.get('cargo_count', 0) + server_data.get('cargo_count', 0)
            merged['updated_at'] = max(
                client_data.get('updated_at', ''),
                server_data.get('updated_at', '')
            )
            return merged
        
        # Default to timestamp wins
        client_timestamp = client_data.get('updated_at', transaction.timestamp)
        server_timestamp = server_data.get('updated_at', '')
        
        return client_data if client_timestamp > server_timestamp else server_data
    
    def _merge_data(self, client_data: Dict[str, Any], server_data: Dict[str, Any]) -> Dict[str, Any]:
        """Merge client and server data intelligently"""
        merged = server_data.copy()
        
        # Merge non-conflicting fields
        for key, value in client_data.items():
            if key not in server_data or server_data[key] is None:
                merged[key] = value
            elif key == 'updated_at':
                # Use latest timestamp
                merged[key] = max(client_data.get(key, ''), server_data.get(key, ''))
        
        return merged
    
    def _save_conflict_for_manual_resolution(
        self,
        transaction: SyncTransaction,
        client_data: Dict[str, Any],
        server_data: Dict[str, Any]
    ) -> bool:
        """Save conflict data for manual resolution"""
        try:
            conflict_data = {
                'transaction_id': transaction.transaction_id,
                'table_name': transaction.table_name,
                'record_id': transaction.record_id,
                'client_data': client_data,
                'server_data': server_data,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'user_id': transaction.user_id,
                'vessel_id': transaction.vessel_id
            }
            
            # Save conflict file
            conflict_file = os.path.join(
                self.conflict_dir,
                f"{transaction.transaction_id}_conflict.json"
            )
            
            with open(conflict_file, 'w') as f:
                json.dump(conflict_data, f, indent=2)
            
            # Update transaction status
            transaction.status = SyncStatus.CONFLICT
            transaction.conflict_data = conflict_data
            self._save_transaction(transaction)
            
            # Log conflict
            self.audit_logger.log_event(
                AuditEventType.DATA_SYNC,
                f"Sync conflict requires manual resolution: {transaction.table_name}",
                details={
                    'transaction_id': transaction.transaction_id,
                    'conflict_file': conflict_file
                },
                severity=AuditSeverity.HIGH
            )
            
            logger.warning(f"Sync conflict saved for manual resolution: {transaction.transaction_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save conflict for manual resolution: {e}")
            return False
    
    def _execute_sync_operation(self, transaction: SyncTransaction, data: Dict[str, Any]) -> bool:
        """Execute the actual synchronization operation"""
        try:
            # This would integrate with the actual database/API layer
            # For now, simulate success
            # In a real implementation, this would:
            # 1. Connect to the server API
            # 2. Perform the CREATE/UPDATE/DELETE operation
            # 3. Handle any server-side validation errors
            # 4. Return success/failure status
            
            logger.info(f"Executing sync operation: {transaction.operation.value} {transaction.table_name}")
            
            # Simulate network operation
            import time
            time.sleep(0.1)  # Simulate network delay
            
            # For demo purposes, return success
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute sync operation: {e}")
            return False
    
    def _save_transaction(self, transaction: SyncTransaction):
        """Save transaction to file"""
        try:
            queue_file = os.path.join(self.sync_queue_dir, f"{transaction.transaction_id}.sync")
            with open(queue_file, 'w') as f:
                json.dump(transaction.to_dict(), f)
            
            # Update cache
            self.cache.store(
                key=f"sync_transaction_{transaction.transaction_id}",
                data=transaction.to_dict(),
                ttl=86400,  # 24 hours
                classification=CacheClassification.INTERNAL,
                vessel_id=transaction.vessel_id,
                operation_type="sync_operation"
            )
            
        except Exception as e:
            logger.error(f"Failed to save transaction {transaction.transaction_id}: {e}")
    
    def _cleanup_transaction(self, transaction: SyncTransaction):
        """Clean up completed transaction"""
        try:
            # Remove from queue
            queue_file = os.path.join(self.sync_queue_dir, f"{transaction.transaction_id}.sync")
            if os.path.exists(queue_file):
                os.unlink(queue_file)
            
            # Remove from cache
            self.cache.delete(f"sync_transaction_{transaction.transaction_id}")
            
            logger.debug(f"Cleaned up transaction: {transaction.transaction_id}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup transaction {transaction.transaction_id}: {e}")
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get overall synchronization status"""
        try:
            status = {
                'pending_transactions': 0,
                'failed_transactions': 0,
                'conflict_transactions': 0,
                'by_table': {},
                'by_priority': {},
                'oldest_pending': None,
                'total_size': 0
            }
            
            if not os.path.exists(self.sync_queue_dir):
                return status
            
            for filename in os.listdir(self.sync_queue_dir):
                if not filename.endswith('.sync'):
                    continue
                
                file_path = os.path.join(self.sync_queue_dir, filename)
                
                try:
                    file_size = os.path.getsize(file_path)
                    status['total_size'] += file_size
                    
                    with open(file_path, 'r') as f:
                        transaction_data = json.load(f)
                    
                    transaction = SyncTransaction.from_dict(transaction_data)
                    
                    # Count by status
                    if transaction.status == SyncStatus.PENDING:
                        status['pending_transactions'] += 1
                        
                        # Track oldest pending
                        if not status['oldest_pending'] or transaction.timestamp < status['oldest_pending']:
                            status['oldest_pending'] = transaction.timestamp
                            
                    elif transaction.status == SyncStatus.FAILED:
                        status['failed_transactions'] += 1
                        
                    elif transaction.status == SyncStatus.CONFLICT:
                        status['conflict_transactions'] += 1
                    
                    # Count by table
                    if transaction.table_name not in status['by_table']:
                        status['by_table'][transaction.table_name] = 0
                    status['by_table'][transaction.table_name] += 1
                    
                    # Count by priority
                    priority_key = f"priority_{transaction.priority}"
                    if priority_key not in status['by_priority']:
                        status['by_priority'][priority_key] = 0
                    status['by_priority'][priority_key] += 1
                
                except Exception:
                    continue
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get sync status: {e}")
            return {}
    
    def process_sync_batch(self, batch_size: int = 10) -> Dict[str, Any]:
        """Process a batch of synchronization transactions"""
        try:
            transactions = self.get_pending_transactions(batch_size)
            
            results = {
                'processed': 0,
                'succeeded': 0,
                'failed': 0,
                'conflicts': 0,
                'transactions': []
            }
            
            for transaction in transactions:
                try:
                    success = self.process_sync_transaction(transaction)
                    
                    result = {
                        'transaction_id': transaction.transaction_id,
                        'table_name': transaction.table_name,
                        'operation': transaction.operation.value,
                        'success': success,
                        'status': transaction.status.value
                    }
                    
                    results['transactions'].append(result)
                    results['processed'] += 1
                    
                    if success:
                        results['succeeded'] += 1
                    elif transaction.status == SyncStatus.CONFLICT:
                        results['conflicts'] += 1
                    else:
                        results['failed'] += 1
                        
                except Exception as e:
                    logger.error(f"Error processing transaction {transaction.transaction_id}: {e}")
                    results['failed'] += 1
            
            # Log batch results
            if results['processed'] > 0:
                self.audit_logger.log_event(
                    AuditEventType.DATA_SYNC,
                    f"Sync batch processed: {results['succeeded']}/{results['processed']} succeeded",
                    details=results,
                    severity=AuditSeverity.LOW
                )
                
                logger.info(f"Sync batch processed: {results['succeeded']}/{results['processed']} succeeded")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to process sync batch: {e}")
            return {'error': str(e)}
    
    def cleanup_expired_transactions(self) -> int:
        """Clean up expired transactions"""
        cleaned_count = 0
        
        try:
            if not os.path.exists(self.sync_queue_dir):
                return 0
            
            for filename in os.listdir(self.sync_queue_dir):
                if not filename.endswith('.sync'):
                    continue
                
                file_path = os.path.join(self.sync_queue_dir, filename)
                
                try:
                    with open(file_path, 'r') as f:
                        transaction_data = json.load(f)
                    
                    transaction = SyncTransaction.from_dict(transaction_data)
                    
                    if transaction.is_expired():
                        os.unlink(file_path)
                        cleaned_count += 1
                        
                        # Remove from cache
                        self.cache.delete(f"sync_transaction_{transaction.transaction_id}")
                
                except Exception:
                    # Remove corrupted files
                    try:
                        os.unlink(file_path)
                        cleaned_count += 1
                    except Exception:
                        pass
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired sync transactions")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired transactions: {e}")
            return 0

# Global secure sync manager
secure_sync = SecureSyncManager()

def get_secure_sync_manager() -> SecureSyncManager:
    """Get the global secure sync manager"""
    return secure_sync

def queue_maritime_sync(
    operation: str,
    table_name: str,
    record_id: str,
    data: Dict[str, Any],
    vessel_id: Optional[int] = None,
    urgency: str = "normal"
) -> str:
    """
    Convenience function to queue maritime data synchronization
    
    Args:
        operation: sync operation (create, update, delete)
        table_name: database table
        record_id: record identifier  
        data: data to sync
        vessel_id: associated vessel
        urgency: urgency level
        
    Returns:
        str: transaction ID
    """
    sync_op = SyncOperation(operation)
    return secure_sync.queue_sync_operation(
        operation=sync_op,
        table_name=table_name,
        record_id=record_id,
        data=data,
        vessel_id=vessel_id,
        maritime_urgency=urgency
    )