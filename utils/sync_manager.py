"""
Sync Manager for Offline/Online Data Synchronization
Handles conflict resolution and data consistency for maritime operations
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass, asdict

class SyncStatus(Enum):
    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    CONFLICT = "conflict"
    ERROR = "error"

class ConflictResolution(Enum):
    CLIENT_WINS = "client_wins"
    SERVER_WINS = "server_wins"
    MERGE = "merge"
    MANUAL = "manual"

@dataclass
class SyncRecord:
    """Represents a data record for synchronization"""
    id: str
    table: str
    operation: str  # create, update, delete
    data: Dict[str, Any]
    timestamp: str
    client_hash: str
    server_hash: Optional[str] = None
    status: SyncStatus = SyncStatus.PENDING
    conflict_data: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    last_sync_attempt: Optional[str] = None

class SyncManager:
    """Manages offline/online data synchronization with conflict resolution"""
    
    def __init__(self):
        self.sync_queue = []
        self.conflict_resolvers = {
            'vessels': self._resolve_vessel_conflict,
            'cargo_tallies': self._resolve_cargo_tally_conflict,
            'users': self._resolve_user_conflict
        }
        self.max_retry_count = 3
        self.sync_batch_size = 10
        
    def add_to_sync_queue(self, table: str, operation: str, data: Dict[str, Any], record_id: Optional[str] = None) -> str:
        """Add a record to the sync queue"""
        sync_id = record_id or self._generate_sync_id(table, data)
        
        # Calculate data hash for conflict detection
        data_hash = self._calculate_hash(data)
        
        sync_record = SyncRecord(
            id=sync_id,
            table=table,
            operation=operation,
            data=data,
            timestamp=datetime.utcnow().isoformat(),
            client_hash=data_hash
        )
        
        # Remove existing record with same ID to avoid duplicates
        self.sync_queue = [r for r in self.sync_queue if r.id != sync_id]
        self.sync_queue.append(sync_record)
        
        return sync_id
    
    def get_pending_sync_records(self, limit: Optional[int] = None) -> List[SyncRecord]:
        """Get pending sync records"""
        pending = [r for r in self.sync_queue if r.status == SyncStatus.PENDING]
        if limit:
            return pending[:limit]
        return pending
    
    def mark_as_syncing(self, sync_id: str) -> bool:
        """Mark a sync record as currently syncing"""
        for record in self.sync_queue:
            if record.id == sync_id:
                record.status = SyncStatus.SYNCING
                record.last_sync_attempt = datetime.utcnow().isoformat()
                return True
        return False
    
    def mark_as_synced(self, sync_id: str, server_hash: str) -> bool:
        """Mark a sync record as successfully synced"""
        for record in self.sync_queue:
            if record.id == sync_id:
                record.status = SyncStatus.SYNCED
                record.server_hash = server_hash
                return True
        return False
    
    def mark_as_conflict(self, sync_id: str, server_data: Dict[str, Any]) -> bool:
        """Mark a sync record as having a conflict"""
        for record in self.sync_queue:
            if record.id == sync_id:
                record.status = SyncStatus.CONFLICT
                record.conflict_data = server_data
                return True
        return False
    
    def mark_as_error(self, sync_id: str, error_message: str) -> bool:
        """Mark a sync record as having an error"""
        for record in self.sync_queue:
            if record.id == sync_id:
                record.status = SyncStatus.ERROR
                record.retry_count += 1
                # Reset to pending if under retry limit
                if record.retry_count < self.max_retry_count:
                    record.status = SyncStatus.PENDING
                return True
        return False
    
    def resolve_conflict(self, sync_id: str, resolution: ConflictResolution = ConflictResolution.MERGE) -> Optional[Dict[str, Any]]:
        """Resolve a conflict between client and server data"""
        for record in self.sync_queue:
            if record.id == sync_id and record.status == SyncStatus.CONFLICT:
                if record.table in self.conflict_resolvers:
                    resolver = self.conflict_resolvers[record.table]
                    resolved_data = resolver(record.data, record.conflict_data, resolution)
                    
                    if resolved_data:
                        # Update record with resolved data
                        record.data = resolved_data
                        record.client_hash = self._calculate_hash(resolved_data)
                        record.status = SyncStatus.PENDING
                        record.conflict_data = None
                        
                        return resolved_data
                    
        return None
    
    def get_sync_statistics(self) -> Dict[str, Any]:
        """Get sync queue statistics"""
        stats = {
            'total_records': len(self.sync_queue),
            'pending': len([r for r in self.sync_queue if r.status == SyncStatus.PENDING]),
            'syncing': len([r for r in self.sync_queue if r.status == SyncStatus.SYNCING]),
            'synced': len([r for r in self.sync_queue if r.status == SyncStatus.SYNCED]),
            'conflicts': len([r for r in self.sync_queue if r.status == SyncStatus.CONFLICT]),
            'errors': len([r for r in self.sync_queue if r.status == SyncStatus.ERROR]),
            'by_table': {}
        }
        
        # Count by table
        for record in self.sync_queue:
            table = record.table
            if table not in stats['by_table']:
                stats['by_table'][table] = {
                    'total': 0,
                    'pending': 0,
                    'synced': 0,
                    'conflicts': 0,
                    'errors': 0
                }
            
            stats['by_table'][table]['total'] += 1
            stats['by_table'][table][record.status.value] += 1
        
        return stats
    
    def cleanup_synced_records(self, older_than_hours: int = 24) -> int:
        """Clean up old synced records"""
        cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)
        original_count = len(self.sync_queue)
        
        self.sync_queue = [
            record for record in self.sync_queue
            if not (record.status == SyncStatus.SYNCED and 
                   datetime.fromisoformat(record.timestamp) < cutoff_time)
        ]
        
        return original_count - len(self.sync_queue)
    
    def get_conflicts(self) -> List[SyncRecord]:
        """Get all records with conflicts"""
        return [r for r in self.sync_queue if r.status == SyncStatus.CONFLICT]
    
    def _generate_sync_id(self, table: str, data: Dict[str, Any]) -> str:
        """Generate a unique sync ID"""
        # Use table + timestamp + data hash for uniqueness
        base_data = f"{table}_{datetime.utcnow().isoformat()}_{json.dumps(data, sort_keys=True)}"
        return hashlib.sha256(base_data.encode()).hexdigest()[:16]
    
    def _calculate_hash(self, data: Dict[str, Any]) -> str:
        """Calculate hash of data for conflict detection"""
        # Exclude timestamp fields from hash calculation
        filtered_data = {k: v for k, v in data.items() 
                        if not k.endswith(('_at', '_timestamp', 'updated_at', 'created_at'))}
        data_str = json.dumps(filtered_data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]
    
    def _resolve_vessel_conflict(self, client_data: Dict, server_data: Dict, resolution: ConflictResolution) -> Optional[Dict]:
        """Resolve conflicts for vessel data"""
        if resolution == ConflictResolution.CLIENT_WINS:
            return client_data
        elif resolution == ConflictResolution.SERVER_WINS:
            return server_data
        elif resolution == ConflictResolution.MERGE:
            # Merge strategy for vessels: prefer client operational data, server for static data
            merged = server_data.copy()
            
            # Client wins for operational fields
            operational_fields = [
                'status', 'progress_percentage', 'current_berth', 
                'shift_start', 'shift_end', 'drivers_assigned',
                'tico_vehicles_needed'
            ]
            
            for field in operational_fields:
                if field in client_data and client_data[field] is not None:
                    merged[field] = client_data[field]
            
            # Always use latest timestamp
            if 'updated_at' in client_data and 'updated_at' in server_data:
                client_time = datetime.fromisoformat(client_data['updated_at'])
                server_time = datetime.fromisoformat(server_data['updated_at'])
                merged['updated_at'] = max(client_time, server_time).isoformat()
            
            return merged
        
        return None
    
    def _resolve_cargo_tally_conflict(self, client_data: Dict, server_data: Dict, resolution: ConflictResolution) -> Optional[Dict]:
        """Resolve conflicts for cargo tally data"""
        if resolution == ConflictResolution.CLIENT_WINS:
            return client_data
        elif resolution == ConflictResolution.SERVER_WINS:
            return server_data
        elif resolution == ConflictResolution.MERGE:
            # For cargo tallies, use the one with the latest timestamp
            client_time = datetime.fromisoformat(client_data.get('timestamp', '1970-01-01'))
            server_time = datetime.fromisoformat(server_data.get('timestamp', '1970-01-01'))
            
            return client_data if client_time >= server_time else server_data
        
        return None
    
    def _resolve_user_conflict(self, client_data: Dict, server_data: Dict, resolution: ConflictResolution) -> Optional[Dict]:
        """Resolve conflicts for user data"""
        # Users are typically server authoritative
        if resolution in [ConflictResolution.SERVER_WINS, ConflictResolution.MERGE]:
            return server_data
        return client_data

class NetworkStatus:
    """Track network connectivity status"""
    
    def __init__(self):
        self.is_online = True
        self.last_online_check = datetime.utcnow()
        self.connection_quality = "good"  # good, poor, offline
        self.failed_requests = 0
        
    def mark_online(self):
        """Mark as online"""
        self.is_online = True
        self.failed_requests = 0
        self.connection_quality = "good"
        self.last_online_check = datetime.utcnow()
    
    def mark_offline(self):
        """Mark as offline"""
        self.is_online = False
        self.connection_quality = "offline"
        self.failed_requests += 1
    
    def mark_poor_connection(self):
        """Mark as poor connection"""
        self.is_online = True
        self.connection_quality = "poor"
        self.failed_requests += 1
    
    def get_status(self) -> Dict[str, Any]:
        """Get current network status"""
        return {
            'is_online': self.is_online,
            'connection_quality': self.connection_quality,
            'failed_requests': self.failed_requests,
            'last_online_check': self.last_online_check.isoformat()
        }

class BackgroundSyncScheduler:
    """Schedule and manage background sync operations"""
    
    def __init__(self, sync_manager: SyncManager):
        self.sync_manager = sync_manager
        self.network_status = NetworkStatus()
        self.sync_interval = 30  # seconds
        self.last_sync = None
        self.sync_in_progress = False
        
    def should_sync(self) -> bool:
        """Determine if sync should be performed"""
        if self.sync_in_progress:
            return False
            
        if not self.network_status.is_online:
            return False
            
        if not self.sync_manager.get_pending_sync_records():
            return False
            
        if self.last_sync is None:
            return True
            
        time_since_last_sync = datetime.utcnow() - self.last_sync
        return time_since_last_sync.total_seconds() >= self.sync_interval
    
    def start_sync(self) -> bool:
        """Start a sync operation"""
        if self.should_sync():
            self.sync_in_progress = True
            self.last_sync = datetime.utcnow()
            return True
        return False
    
    def complete_sync(self, success: bool):
        """Mark sync operation as complete"""
        self.sync_in_progress = False
        if not success:
            self.network_status.mark_poor_connection()
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync scheduler status"""
        return {
            'sync_in_progress': self.sync_in_progress,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'next_sync_in_seconds': max(0, self.sync_interval - (
                (datetime.utcnow() - self.last_sync).total_seconds() 
                if self.last_sync else 0
            )),
            'network_status': self.network_status.get_status(),
            'sync_statistics': self.sync_manager.get_sync_statistics()
        }