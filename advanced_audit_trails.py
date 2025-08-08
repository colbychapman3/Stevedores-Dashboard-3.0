"""
Advanced Audit Trail System for Stevedores Dashboard 3.0
Blockchain-like integrity with 7-year maritime record retention
"""

import asyncio
import json
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from pathlib import Path
import sqlite3
import uuid
import pickle
import zlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import threading
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AuditEventType(Enum):
    """Types of auditable events in maritime operations"""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    DATA_DELETION = "data_deletion"
    DOCUMENT_UPLOAD = "document_upload"
    DOCUMENT_DOWNLOAD = "document_download"
    COMPLIANCE_CHECK = "compliance_check"
    SECURITY_EVENT = "security_event"
    SYSTEM_CONFIGURATION = "system_configuration"
    VESSEL_OPERATION = "vessel_operation"
    CARGO_HANDLING = "cargo_handling"
    FINANCIAL_TRANSACTION = "financial_transaction"
    REGULATORY_SUBMISSION = "regulatory_submission"
    EMERGENCY_EVENT = "emergency_event"

class AuditSeverity(Enum):
    """Severity levels for audit events"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RetentionPolicy(Enum):
    """Data retention policies for different types of records"""
    OPERATIONAL = 1  # 1 year
    FINANCIAL = 7   # 7 years (maritime standard)
    SAFETY = 10     # 10 years
    REGULATORY = 15 # 15 years
    PERMANENT = 99  # Permanent retention

@dataclass
class AuditEvent:
    """Individual audit event with comprehensive tracking"""
    id: str
    timestamp: datetime
    event_type: AuditEventType
    severity: AuditSeverity
    user_id: str
    session_id: str
    ip_address: str
    user_agent: str
    resource_type: str
    resource_id: str
    action: str
    old_value: Optional[str]
    new_value: Optional[str]
    metadata: Dict[str, Any]
    checksum: str
    digital_signature: Optional[str]
    retention_policy: RetentionPolicy
    chain_hash: str  # Previous block hash for blockchain-like integrity
    merkle_root: str  # Merkle root for batch verification

@dataclass
class AuditChain:
    """Audit chain block for blockchain-like integrity"""
    block_id: str
    timestamp: datetime
    previous_hash: str
    merkle_root: str
    events_count: int
    events_hash: str
    nonce: int
    block_hash: str

@dataclass
class ChainOfCustody:
    """Chain of custody for sensitive maritime documents"""
    document_id: str
    document_type: str
    classification_level: str
    custody_events: List[Dict[str, Any]]
    current_custodian: str
    integrity_hash: str
    last_verification: datetime
    retention_deadline: datetime

class AdvancedAuditTrailSystem:
    """
    Advanced audit trail system with blockchain-like integrity
    Provides 7-year maritime record retention and immutable audit logs
    """
    
    def __init__(self, db_path: str = "advanced_audit_trails.db", 
                 encryption_key: Optional[bytes] = None):
        self.db_path = db_path
        self.encryption_key = encryption_key or self._generate_encryption_key()
        self.fernet = Fernet(self.encryption_key)
        self.audit_cache = {}
        self.chain_cache = {}
        self.custody_tracker = {}
        self.last_block_hash = "0" * 64  # Genesis block hash
        self.lock = threading.RLock()
        self._init_database()
        self._load_last_block_hash()
        
    def _generate_encryption_key(self) -> bytes:
        """Generate encryption key for sensitive audit data"""
        password = b"maritime_audit_trail_system_v3"
        salt = b"stevedores_dashboard_salt"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key
    
    def _init_database(self):
        """Initialize audit trail database with comprehensive schema"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Main audit events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    resource_type TEXT,
                    resource_id TEXT,
                    action TEXT NOT NULL,
                    old_value_encrypted BLOB,
                    new_value_encrypted BLOB,
                    metadata_encrypted BLOB,
                    checksum TEXT NOT NULL,
                    digital_signature TEXT,
                    retention_policy TEXT NOT NULL,
                    retention_deadline TIMESTAMP,
                    chain_hash TEXT NOT NULL,
                    merkle_root TEXT,
                    block_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_timestamp (timestamp),
                    INDEX idx_user_id (user_id),
                    INDEX idx_event_type (event_type),
                    INDEX idx_retention_deadline (retention_deadline)
                )
            ''')
            
            # Audit chain blocks table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_chain_blocks (
                    block_id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    previous_hash TEXT NOT NULL,
                    merkle_root TEXT NOT NULL,
                    events_count INTEGER NOT NULL,
                    events_hash TEXT NOT NULL,
                    nonce INTEGER NOT NULL,
                    block_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_timestamp (timestamp),
                    INDEX idx_block_hash (block_hash)
                )
            ''')
            
            # Chain of custody table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chain_of_custody (
                    document_id TEXT PRIMARY KEY,
                    document_type TEXT NOT NULL,
                    classification_level TEXT NOT NULL,
                    custody_events_encrypted BLOB NOT NULL,
                    current_custodian TEXT NOT NULL,
                    integrity_hash TEXT NOT NULL,
                    last_verification TIMESTAMP NOT NULL,
                    retention_deadline TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_current_custodian (current_custodian),
                    INDEX idx_retention_deadline (retention_deadline)
                )
            ''')
            
            # Retention schedule table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS retention_schedule (
                    id TEXT PRIMARY KEY,
                    record_type TEXT NOT NULL,
                    retention_policy TEXT NOT NULL,
                    created_date TIMESTAMP NOT NULL,
                    scheduled_deletion TIMESTAMP NOT NULL,
                    status TEXT DEFAULT 'active',
                    deletion_confirmed TIMESTAMP,
                    deletion_method TEXT,
                    INDEX idx_scheduled_deletion (scheduled_deletion),
                    INDEX idx_status (status)
                )
            ''')
            
            # Archive storage table for compressed long-term storage
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_archives (
                    archive_id TEXT PRIMARY KEY,
                    start_date TIMESTAMP NOT NULL,
                    end_date TIMESTAMP NOT NULL,
                    events_count INTEGER NOT NULL,
                    compressed_data BLOB NOT NULL,
                    integrity_hash TEXT NOT NULL,
                    archive_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_date_range (start_date, end_date)
                )
            ''')
            
            # Verification log table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS integrity_verifications (
                    id TEXT PRIMARY KEY,
                    verification_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    verification_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    verified_hash TEXT NOT NULL,
                    verification_result TEXT NOT NULL,
                    discrepancies TEXT,
                    verifier TEXT NOT NULL
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Advanced audit trail database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize audit database: {e}")
            raise
    
    def _load_last_block_hash(self):
        """Load the hash of the last block in the chain"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT block_hash FROM audit_chain_blocks 
                ORDER BY timestamp DESC LIMIT 1
            ''')
            
            result = cursor.fetchone()
            if result:
                self.last_block_hash = result[0]
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to load last block hash: {e}")
    
    async def log_audit_event(self, event_data: Dict[str, Any]) -> str:
        """Log comprehensive audit event with blockchain-like integrity"""
        try:
            with self.lock:
                # Create audit event
                event_id = str(uuid.uuid4())
                timestamp = datetime.utcnow()
                
                # Calculate retention deadline
                retention_policy = RetentionPolicy(event_data.get('retention_policy', 'OPERATIONAL'))
                retention_deadline = timestamp + timedelta(days=retention_policy.value * 365)
                
                # Encrypt sensitive data
                old_value_encrypted = None
                new_value_encrypted = None
                metadata_encrypted = None
                
                if event_data.get('old_value'):
                    old_value_encrypted = self.fernet.encrypt(
                        json.dumps(event_data['old_value']).encode()
                    )
                
                if event_data.get('new_value'):
                    new_value_encrypted = self.fernet.encrypt(
                        json.dumps(event_data['new_value']).encode()
                    )
                
                if event_data.get('metadata'):
                    metadata_encrypted = self.fernet.encrypt(
                        json.dumps(event_data['metadata']).encode()
                    )
                
                # Calculate event checksum
                checksum_data = {
                    'id': event_id,
                    'timestamp': timestamp.isoformat(),
                    'event_type': event_data['event_type'],
                    'user_id': event_data['user_id'],
                    'action': event_data['action'],
                    'resource_type': event_data.get('resource_type', ''),
                    'resource_id': event_data.get('resource_id', '')
                }
                
                checksum = hashlib.sha256(
                    json.dumps(checksum_data, sort_keys=True).encode()
                ).hexdigest()
                
                # Calculate chain hash (hash of previous event + current event)
                chain_hash = hashlib.sha256(
                    f"{self.last_block_hash}{checksum}".encode()
                ).hexdigest()
                
                # Create audit event object
                audit_event = AuditEvent(
                    id=event_id,
                    timestamp=timestamp,
                    event_type=AuditEventType(event_data['event_type']),
                    severity=AuditSeverity(event_data.get('severity', 'LOW')),
                    user_id=event_data['user_id'],
                    session_id=event_data.get('session_id', ''),
                    ip_address=event_data.get('ip_address', ''),
                    user_agent=event_data.get('user_agent', ''),
                    resource_type=event_data.get('resource_type', ''),
                    resource_id=event_data.get('resource_id', ''),
                    action=event_data['action'],
                    old_value=event_data.get('old_value'),
                    new_value=event_data.get('new_value'),
                    metadata=event_data.get('metadata', {}),
                    checksum=checksum,
                    digital_signature=None,  # Could be implemented with PKI
                    retention_policy=retention_policy,
                    chain_hash=chain_hash,
                    merkle_root=""  # Will be calculated when creating block
                )
                
                # Store in database
                await self._store_audit_event(audit_event, old_value_encrypted, 
                                            new_value_encrypted, metadata_encrypted, 
                                            retention_deadline)
                
                # Update last block hash
                self.last_block_hash = chain_hash
                
                # Cache for block creation
                self.audit_cache[event_id] = audit_event
                
                # Schedule retention
                await self._schedule_retention(event_id, retention_policy, retention_deadline)
                
                logger.info(f"Audit event logged: {event_id} ({audit_event.event_type.value})")
                return event_id
                
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            raise
    
    async def _store_audit_event(self, event: AuditEvent, old_value_encrypted: bytes,
                                new_value_encrypted: bytes, metadata_encrypted: bytes,
                                retention_deadline: datetime):
        """Store audit event in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO audit_events 
                (id, timestamp, event_type, severity, user_id, session_id, ip_address,
                 user_agent, resource_type, resource_id, action, old_value_encrypted,
                 new_value_encrypted, metadata_encrypted, checksum, digital_signature,
                 retention_policy, retention_deadline, chain_hash, merkle_root)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event.id, event.timestamp, event.event_type.value, event.severity.value,
                event.user_id, event.session_id, event.ip_address, event.user_agent,
                event.resource_type, event.resource_id, event.action,
                old_value_encrypted, new_value_encrypted, metadata_encrypted,
                event.checksum, event.digital_signature, event.retention_policy.value,
                retention_deadline, event.chain_hash, event.merkle_root
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to store audit event: {e}")
            raise
    
    async def _schedule_retention(self, record_id: str, retention_policy: RetentionPolicy,
                                retention_deadline: datetime):
        """Schedule record for retention management"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO retention_schedule 
                (id, record_type, retention_policy, created_date, scheduled_deletion)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), 'audit_event', retention_policy.value,
                datetime.utcnow(), retention_deadline
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to schedule retention: {e}")
    
    async def create_audit_block(self, events_batch: List[str]) -> str:
        """Create blockchain-like audit block from a batch of events"""
        try:
            with self.lock:
                if not events_batch:
                    return None
                
                block_id = str(uuid.uuid4())
                timestamp = datetime.utcnow()
                
                # Get events from cache or database
                events = []
                for event_id in events_batch:
                    if event_id in self.audit_cache:
                        events.append(self.audit_cache[event_id])
                    else:
                        event = await self._load_audit_event(event_id)
                        if event:
                            events.append(event)
                
                # Calculate Merkle root
                merkle_root = self._calculate_merkle_root([e.checksum for e in events])
                
                # Calculate events hash
                events_data = [e.checksum for e in events]
                events_hash = hashlib.sha256(
                    json.dumps(events_data, sort_keys=True).encode()
                ).hexdigest()
                
                # Create block with proof-of-work (simplified)
                nonce = await self._proof_of_work(block_id, timestamp, self.last_block_hash,
                                                merkle_root, len(events), events_hash)
                
                # Calculate block hash
                block_data = {
                    'block_id': block_id,
                    'timestamp': timestamp.isoformat(),
                    'previous_hash': self.last_block_hash,
                    'merkle_root': merkle_root,
                    'events_count': len(events),
                    'events_hash': events_hash,
                    'nonce': nonce
                }
                
                block_hash = hashlib.sha256(
                    json.dumps(block_data, sort_keys=True).encode()
                ).hexdigest()
                
                # Create audit chain block
                audit_block = AuditChain(
                    block_id=block_id,
                    timestamp=timestamp,
                    previous_hash=self.last_block_hash,
                    merkle_root=merkle_root,
                    events_count=len(events),
                    events_hash=events_hash,
                    nonce=nonce,
                    block_hash=block_hash
                )
                
                # Store block
                await self._store_audit_block(audit_block)
                
                # Update events with block information
                await self._update_events_with_block(events_batch, block_id, merkle_root)
                
                # Update last block hash
                self.last_block_hash = block_hash
                
                # Clear processed events from cache
                for event_id in events_batch:
                    self.audit_cache.pop(event_id, None)
                
                logger.info(f"Audit block created: {block_id} with {len(events)} events")
                return block_id
                
        except Exception as e:
            logger.error(f"Failed to create audit block: {e}")
            raise
    
    def _calculate_merkle_root(self, hashes: List[str]) -> str:
        """Calculate Merkle root for batch of event hashes"""
        if not hashes:
            return ""
        
        if len(hashes) == 1:
            return hashes[0]
        
        # Make sure we have even number of hashes
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])
        
        new_hashes = []
        for i in range(0, len(hashes), 2):
            combined = f"{hashes[i]}{hashes[i+1]}"
            new_hash = hashlib.sha256(combined.encode()).hexdigest()
            new_hashes.append(new_hash)
        
        return self._calculate_merkle_root(new_hashes)
    
    async def _proof_of_work(self, block_id: str, timestamp: datetime, previous_hash: str,
                           merkle_root: str, events_count: int, events_hash: str,
                           difficulty: int = 4) -> int:
        """Simple proof-of-work algorithm for block validation"""
        target = "0" * difficulty
        nonce = 0
        
        while True:
            block_data = {
                'block_id': block_id,
                'timestamp': timestamp.isoformat(),
                'previous_hash': previous_hash,
                'merkle_root': merkle_root,
                'events_count': events_count,
                'events_hash': events_hash,
                'nonce': nonce
            }
            
            hash_result = hashlib.sha256(
                json.dumps(block_data, sort_keys=True).encode()
            ).hexdigest()
            
            if hash_result.startswith(target):
                return nonce
            
            nonce += 1
            
            # Prevent infinite loop in production
            if nonce > 1000000:
                logger.warning("Proof-of-work difficulty too high, using current nonce")
                return nonce
    
    async def _store_audit_block(self, block: AuditChain):
        """Store audit block in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO audit_chain_blocks 
                (block_id, timestamp, previous_hash, merkle_root, events_count,
                 events_hash, nonce, block_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                block.block_id, block.timestamp, block.previous_hash,
                block.merkle_root, block.events_count, block.events_hash,
                block.nonce, block.block_hash
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to store audit block: {e}")
            raise
    
    async def _update_events_with_block(self, event_ids: List[str], block_id: str, merkle_root: str):
        """Update events with their block information"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for event_id in event_ids:
                cursor.execute('''
                    UPDATE audit_events 
                    SET block_id = ?, merkle_root = ?
                    WHERE id = ?
                ''', (block_id, merkle_root, event_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to update events with block info: {e}")
    
    async def _load_audit_event(self, event_id: str) -> Optional[AuditEvent]:
        """Load audit event from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, timestamp, event_type, severity, user_id, session_id,
                       ip_address, user_agent, resource_type, resource_id, action,
                       old_value_encrypted, new_value_encrypted, metadata_encrypted,
                       checksum, digital_signature, retention_policy, chain_hash, merkle_root
                FROM audit_events WHERE id = ?
            ''', (event_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            # Decrypt sensitive data
            old_value = None
            new_value = None
            metadata = {}
            
            if row[11]:  # old_value_encrypted
                old_value = json.loads(self.fernet.decrypt(row[11]).decode())
            
            if row[12]:  # new_value_encrypted
                new_value = json.loads(self.fernet.decrypt(row[12]).decode())
            
            if row[13]:  # metadata_encrypted
                metadata = json.loads(self.fernet.decrypt(row[13]).decode())
            
            return AuditEvent(
                id=row[0],
                timestamp=datetime.fromisoformat(row[1]),
                event_type=AuditEventType(row[2]),
                severity=AuditSeverity(row[3]),
                user_id=row[4],
                session_id=row[5] or "",
                ip_address=row[6] or "",
                user_agent=row[7] or "",
                resource_type=row[8] or "",
                resource_id=row[9] or "",
                action=row[10],
                old_value=old_value,
                new_value=new_value,
                metadata=metadata,
                checksum=row[14],
                digital_signature=row[15],
                retention_policy=RetentionPolicy(row[16]),
                chain_hash=row[17],
                merkle_root=row[18] or ""
            )
            
        except Exception as e:
            logger.error(f"Failed to load audit event {event_id}: {e}")
            return None
    
    async def establish_chain_of_custody(self, document_id: str, document_type: str,
                                       classification_level: str, initial_custodian: str) -> str:
        """Establish chain of custody for sensitive maritime documents"""
        try:
            # Calculate document integrity hash
            integrity_hash = hashlib.sha256(f"{document_id}:{document_type}:{datetime.utcnow().isoformat()}".encode()).hexdigest()
            
            # Initialize custody events
            custody_events = [{
                'event_id': str(uuid.uuid4()),
                'timestamp': datetime.utcnow().isoformat(),
                'event_type': 'custody_established',
                'from_custodian': 'system',
                'to_custodian': initial_custodian,
                'reason': 'Initial custody establishment',
                'location': 'system',
                'witness': 'system',
                'signature_hash': integrity_hash
            }]
            
            # Calculate retention deadline based on document type
            retention_years = 7  # Default maritime retention
            if 'safety' in document_type.lower():
                retention_years = 10
            elif 'regulatory' in document_type.lower():
                retention_years = 15
            
            retention_deadline = datetime.utcnow() + timedelta(days=retention_years * 365)
            
            # Create chain of custody record
            custody_record = ChainOfCustody(
                document_id=document_id,
                document_type=document_type,
                classification_level=classification_level,
                custody_events=custody_events,
                current_custodian=initial_custodian,
                integrity_hash=integrity_hash,
                last_verification=datetime.utcnow(),
                retention_deadline=retention_deadline
            )
            
            # Encrypt custody events
            custody_events_encrypted = self.fernet.encrypt(
                json.dumps(custody_events).encode()
            )
            
            # Store in database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO chain_of_custody 
                (document_id, document_type, classification_level, custody_events_encrypted,
                 current_custodian, integrity_hash, last_verification, retention_deadline)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                document_id, document_type, classification_level, custody_events_encrypted,
                initial_custodian, integrity_hash, datetime.utcnow(), retention_deadline
            ))
            
            conn.commit()
            conn.close()
            
            # Log audit event
            await self.log_audit_event({
                'event_type': 'DOCUMENT_UPLOAD',
                'severity': 'MEDIUM',
                'user_id': initial_custodian,
                'action': 'establish_chain_of_custody',
                'resource_type': 'document',
                'resource_id': document_id,
                'metadata': {
                    'document_type': document_type,
                    'classification_level': classification_level,
                    'integrity_hash': integrity_hash
                },
                'retention_policy': 'FINANCIAL'
            })
            
            self.custody_tracker[document_id] = custody_record
            logger.info(f"Chain of custody established for document: {document_id}")
            
            return integrity_hash
            
        except Exception as e:
            logger.error(f"Failed to establish chain of custody: {e}")
            raise
    
    async def transfer_custody(self, document_id: str, from_custodian: str,
                             to_custodian: str, reason: str, location: str,
                             witness: Optional[str] = None) -> str:
        """Transfer custody of a document with full audit trail"""
        try:
            # Load existing custody record
            custody_record = await self._load_custody_record(document_id)
            if not custody_record:
                raise ValueError(f"No custody record found for document: {document_id}")
            
            # Verify current custodian
            if custody_record.current_custodian != from_custodian:
                raise ValueError(f"Custody transfer denied: current custodian is {custody_record.current_custodian}, not {from_custodian}")
            
            # Create custody transfer event
            transfer_event = {
                'event_id': str(uuid.uuid4()),
                'timestamp': datetime.utcnow().isoformat(),
                'event_type': 'custody_transfer',
                'from_custodian': from_custodian,
                'to_custodian': to_custodian,
                'reason': reason,
                'location': location,
                'witness': witness or 'none',
                'signature_hash': hashlib.sha256(f"{document_id}:{from_custodian}:{to_custodian}:{datetime.utcnow().isoformat()}".encode()).hexdigest()
            }
            
            # Update custody record
            custody_record.custody_events.append(transfer_event)
            custody_record.current_custodian = to_custodian
            custody_record.last_verification = datetime.utcnow()
            
            # Update database
            await self._update_custody_record(custody_record)
            
            # Log audit event
            await self.log_audit_event({
                'event_type': 'DOCUMENT_UPLOAD',
                'severity': 'HIGH',
                'user_id': from_custodian,
                'action': 'transfer_custody',
                'resource_type': 'document',
                'resource_id': document_id,
                'old_value': {'custodian': from_custodian},
                'new_value': {'custodian': to_custodian},
                'metadata': {
                    'reason': reason,
                    'location': location,
                    'witness': witness,
                    'transfer_event_id': transfer_event['event_id']
                },
                'retention_policy': 'FINANCIAL'
            })
            
            logger.info(f"Custody transferred for document {document_id}: {from_custodian} -> {to_custodian}")
            return transfer_event['event_id']
            
        except Exception as e:
            logger.error(f"Failed to transfer custody: {e}")
            raise
    
    async def _load_custody_record(self, document_id: str) -> Optional[ChainOfCustody]:
        """Load chain of custody record from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT document_type, classification_level, custody_events_encrypted,
                       current_custodian, integrity_hash, last_verification, retention_deadline
                FROM chain_of_custody WHERE document_id = ?
            ''', (document_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            # Decrypt custody events
            custody_events = json.loads(self.fernet.decrypt(row[2]).decode())
            
            return ChainOfCustody(
                document_id=document_id,
                document_type=row[0],
                classification_level=row[1],
                custody_events=custody_events,
                current_custodian=row[3],
                integrity_hash=row[4],
                last_verification=datetime.fromisoformat(row[5]),
                retention_deadline=datetime.fromisoformat(row[6])
            )
            
        except Exception as e:
            logger.error(f"Failed to load custody record: {e}")
            return None
    
    async def _update_custody_record(self, custody_record: ChainOfCustody):
        """Update chain of custody record in database"""
        try:
            # Encrypt custody events
            custody_events_encrypted = self.fernet.encrypt(
                json.dumps(custody_record.custody_events).encode()
            )
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE chain_of_custody 
                SET custody_events_encrypted = ?, current_custodian = ?,
                    last_verification = ?, updated_at = ?
                WHERE document_id = ?
            ''', (
                custody_events_encrypted, custody_record.current_custodian,
                custody_record.last_verification, datetime.utcnow(), custody_record.document_id
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to update custody record: {e}")
            raise
    
    async def verify_audit_chain_integrity(self, start_date: Optional[datetime] = None,
                                         end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Verify integrity of audit chain using blockchain-like verification"""
        try:
            verification_id = str(uuid.uuid4())
            verification_date = datetime.utcnow()
            
            if not start_date:
                start_date = datetime.utcnow() - timedelta(days=30)
            if not end_date:
                end_date = datetime.utcnow()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all blocks in date range
            cursor.execute('''
                SELECT block_id, timestamp, previous_hash, merkle_root, events_count,
                       events_hash, nonce, block_hash
                FROM audit_chain_blocks
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp ASC
            ''', (start_date, end_date))
            
            blocks = cursor.fetchall()
            
            verification_results = {
                'verification_id': verification_id,
                'verification_date': verification_date.isoformat(),
                'period_start': start_date.isoformat(),
                'period_end': end_date.isoformat(),
                'total_blocks': len(blocks),
                'verified_blocks': 0,
                'integrity_violations': [],
                'overall_status': 'VALID'
            }
            
            previous_hash = None
            
            for i, block_data in enumerate(blocks):
                block_id, timestamp, prev_hash, merkle_root, events_count, events_hash, nonce, block_hash = block_data
                
                # Verify block hash
                reconstructed_data = {
                    'block_id': block_id,
                    'timestamp': timestamp,
                    'previous_hash': prev_hash,
                    'merkle_root': merkle_root,
                    'events_count': events_count,
                    'events_hash': events_hash,
                    'nonce': nonce
                }
                
                reconstructed_hash = hashlib.sha256(
                    json.dumps(reconstructed_data, sort_keys=True).encode()
                ).hexdigest()
                
                if reconstructed_hash != block_hash:
                    verification_results['integrity_violations'].append({
                        'block_id': block_id,
                        'violation_type': 'HASH_MISMATCH',
                        'expected_hash': block_hash,
                        'calculated_hash': reconstructed_hash
                    })
                    verification_results['overall_status'] = 'COMPROMISED'
                
                # Verify chain linkage
                if previous_hash and prev_hash != previous_hash:
                    verification_results['integrity_violations'].append({
                        'block_id': block_id,
                        'violation_type': 'CHAIN_BREAK',
                        'expected_previous_hash': previous_hash,
                        'actual_previous_hash': prev_hash
                    })
                    verification_results['overall_status'] = 'COMPROMISED'
                
                # Verify events in block
                cursor.execute('''
                    SELECT checksum FROM audit_events 
                    WHERE block_id = ? ORDER BY timestamp ASC
                ''', (block_id,))
                
                event_checksums = [row[0] for row in cursor.fetchall()]
                
                if len(event_checksums) != events_count:
                    verification_results['integrity_violations'].append({
                        'block_id': block_id,
                        'violation_type': 'EVENT_COUNT_MISMATCH',
                        'expected_count': events_count,
                        'actual_count': len(event_checksums)
                    })
                
                # Verify Merkle root
                calculated_merkle = self._calculate_merkle_root(event_checksums)
                if calculated_merkle != merkle_root:
                    verification_results['integrity_violations'].append({
                        'block_id': block_id,
                        'violation_type': 'MERKLE_ROOT_MISMATCH',
                        'expected_merkle': merkle_root,
                        'calculated_merkle': calculated_merkle
                    })
                
                if not verification_results['integrity_violations']:
                    verification_results['verified_blocks'] += 1
                
                previous_hash = block_hash
            
            conn.close()
            
            # Log verification
            cursor.execute('''
                INSERT INTO integrity_verifications 
                (id, verification_type, target_id, verified_hash, verification_result, 
                 discrepancies, verifier)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                verification_id, 'CHAIN_INTEGRITY', 'audit_chain',
                f"{start_date.isoformat()}:{end_date.isoformat()}",
                verification_results['overall_status'],
                json.dumps(verification_results['integrity_violations']),
                'system'
            ))
            
            logger.info(f"Chain integrity verification completed: {verification_results['overall_status']}")
            return verification_results
            
        except Exception as e:
            logger.error(f"Failed to verify audit chain integrity: {e}")
            raise
    
    async def get_audit_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive audit trail statistics"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Basic event statistics
            cursor.execute('''
                SELECT event_type, COUNT(*) as count
                FROM audit_events 
                WHERE timestamp >= ?
                GROUP BY event_type
                ORDER BY count DESC
            ''', (start_date,))
            
            event_types = dict(cursor.fetchall())
            
            # Severity distribution
            cursor.execute('''
                SELECT severity, COUNT(*) as count
                FROM audit_events 
                WHERE timestamp >= ?
                GROUP BY severity
            ''', (start_date,))
            
            severity_dist = dict(cursor.fetchall())
            
            # User activity
            cursor.execute('''
                SELECT user_id, COUNT(*) as count
                FROM audit_events 
                WHERE timestamp >= ?
                GROUP BY user_id
                ORDER BY count DESC
                LIMIT 10
            ''', (start_date,))
            
            top_users = cursor.fetchall()
            
            # Chain statistics
            cursor.execute('''
                SELECT COUNT(*) as block_count,
                       SUM(events_count) as total_events,
                       AVG(events_count) as avg_events_per_block
                FROM audit_chain_blocks
                WHERE timestamp >= ?
            ''', (start_date,))
            
            chain_stats = cursor.fetchone()
            
            # Retention statistics
            cursor.execute('''
                SELECT retention_policy, COUNT(*) as count
                FROM audit_events
                WHERE timestamp >= ?
                GROUP BY retention_policy
            ''', (start_date,))
            
            retention_dist = dict(cursor.fetchall())
            
            conn.close()
            
            statistics = {
                'reporting_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': datetime.utcnow().isoformat(),
                    'days': days
                },
                'event_statistics': {
                    'total_events': sum(event_types.values()),
                    'by_type': event_types,
                    'by_severity': severity_dist,
                    'top_users': [{'user_id': u[0], 'event_count': u[1]} for u in top_users]
                },
                'chain_statistics': {
                    'total_blocks': chain_stats[0] or 0,
                    'total_events_in_blocks': chain_stats[1] or 0,
                    'average_events_per_block': round(chain_stats[2] or 0, 2)
                },
                'retention_statistics': {
                    'by_policy': retention_dist
                },
                'generated_at': datetime.utcnow().isoformat()
            }
            
            return statistics
            
        except Exception as e:
            logger.error(f"Failed to get audit statistics: {e}")
            raise
    
    async def search_audit_events(self, criteria: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        """Search audit events with flexible criteria"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build query
            where_conditions = []
            params = []
            
            if criteria.get('start_date'):
                where_conditions.append('timestamp >= ?')
                params.append(criteria['start_date'])
            
            if criteria.get('end_date'):
                where_conditions.append('timestamp <= ?')
                params.append(criteria['end_date'])
            
            if criteria.get('event_type'):
                where_conditions.append('event_type = ?')
                params.append(criteria['event_type'])
            
            if criteria.get('user_id'):
                where_conditions.append('user_id = ?')
                params.append(criteria['user_id'])
            
            if criteria.get('resource_type'):
                where_conditions.append('resource_type = ?')
                params.append(criteria['resource_type'])
            
            if criteria.get('resource_id'):
                where_conditions.append('resource_id = ?')
                params.append(criteria['resource_id'])
            
            if criteria.get('severity'):
                where_conditions.append('severity = ?')
                params.append(criteria['severity'])
            
            where_clause = ' AND '.join(where_conditions) if where_conditions else '1=1'
            
            query = f'''
                SELECT id, timestamp, event_type, severity, user_id, session_id,
                       ip_address, resource_type, resource_id, action, checksum,
                       retention_policy, chain_hash, block_id
                FROM audit_events
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ?
            '''
            
            params.append(limit)
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row[0],
                    'timestamp': row[1],
                    'event_type': row[2],
                    'severity': row[3],
                    'user_id': row[4],
                    'session_id': row[5],
                    'ip_address': row[6],
                    'resource_type': row[7],
                    'resource_id': row[8],
                    'action': row[9],
                    'checksum': row[10],
                    'retention_policy': row[11],
                    'chain_hash': row[12],
                    'block_id': row[13]
                })
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Failed to search audit events: {e}")
            raise
    
    async def process_retention_schedule(self) -> Dict[str, Any]:
        """Process retention schedule and archive/delete expired records"""
        try:
            now = datetime.utcnow()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Find records due for retention processing
            cursor.execute('''
                SELECT rs.id, rs.record_type, rs.retention_policy, rs.scheduled_deletion,
                       ae.id as event_id, ae.timestamp, ae.event_type
                FROM retention_schedule rs
                LEFT JOIN audit_events ae ON rs.id = ae.id
                WHERE rs.scheduled_deletion <= ? AND rs.status = 'active'
                ORDER BY rs.scheduled_deletion ASC
            ''', (now,))
            
            retention_candidates = cursor.fetchall()
            
            results = {
                'processed_date': now.isoformat(),
                'total_candidates': len(retention_candidates),
                'archived': 0,
                'deleted': 0,
                'errors': []
            }
            
            for record in retention_candidates:
                try:
                    retention_id, record_type, retention_policy, scheduled_deletion, event_id, timestamp, event_type = record
                    
                    if retention_policy in ['FINANCIAL', 'SAFETY', 'REGULATORY']:
                        # Archive long-term retention records
                        await self._archive_audit_record(event_id, retention_policy)
                        
                        # Mark as archived
                        cursor.execute('''
                            UPDATE retention_schedule 
                            SET status = 'archived', deletion_confirmed = ?, deletion_method = 'archived'
                            WHERE id = ?
                        ''', (now, retention_id))
                        
                        results['archived'] += 1
                        
                    else:
                        # Delete operational records after retention period
                        cursor.execute('DELETE FROM audit_events WHERE id = ?', (event_id,))
                        
                        # Mark as deleted
                        cursor.execute('''
                            UPDATE retention_schedule 
                            SET status = 'deleted', deletion_confirmed = ?, deletion_method = 'deleted'
                            WHERE id = ?
                        ''', (now, retention_id))
                        
                        results['deleted'] += 1
                        
                except Exception as e:
                    results['errors'].append({
                        'record_id': retention_id,
                        'error': str(e)
                    })
            
            conn.commit()
            conn.close()
            
            logger.info(f"Retention processing completed: {results['archived']} archived, {results['deleted']} deleted")
            return results
            
        except Exception as e:
            logger.error(f"Failed to process retention schedule: {e}")
            raise
    
    async def _archive_audit_record(self, event_id: str, retention_policy: str):
        """Archive audit record for long-term storage"""
        try:
            # Load full event data
            event = await self._load_audit_event(event_id)
            if not event:
                return
            
            # Compress event data
            event_data = asdict(event)
            compressed_data = zlib.compress(json.dumps(event_data).encode())
            
            # Calculate archive integrity hash
            integrity_hash = hashlib.sha256(compressed_data).hexdigest()
            
            # Store in archive
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if archive exists for this date range
            archive_date = event.timestamp.date()
            archive_id = f"archive_{archive_date.isoformat()}_{retention_policy}"
            
            cursor.execute('''
                SELECT archive_id FROM audit_archives 
                WHERE archive_id = ?
            ''', (archive_id,))
            
            if cursor.fetchone():
                # Update existing archive
                cursor.execute('''
                    UPDATE audit_archives 
                    SET events_count = events_count + 1,
                        compressed_data = compressed_data || ?,
                        integrity_hash = ?
                    WHERE archive_id = ?
                ''', (compressed_data, integrity_hash, archive_id))
            else:
                # Create new archive
                cursor.execute('''
                    INSERT INTO audit_archives 
                    (archive_id, start_date, end_date, events_count, compressed_data, integrity_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    archive_id, archive_date, archive_date, 1, compressed_data, integrity_hash
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to archive audit record: {e}")
            raise

# Example usage and testing
async def main():
    """Example usage of Advanced Audit Trail System"""
    try:
        # Initialize audit system
        audit_system = AdvancedAuditTrailSystem()
        
        # Log sample audit events
        event_ids = []
        
        # User login event
        login_event_id = await audit_system.log_audit_event({
            'event_type': 'USER_LOGIN',
            'severity': 'LOW',
            'user_id': 'captain_smith',
            'session_id': 'session_12345',
            'ip_address': '192.168.1.100',
            'user_agent': 'Maritime Dashboard v3.0',
            'action': 'successful_login',
            'metadata': {
                'login_method': 'certificate',
                'vessel_id': 'MV_ENTERPRISE'
            },
            'retention_policy': 'OPERATIONAL'
        })
        event_ids.append(login_event_id)
        
        # Document access event
        doc_event_id = await audit_system.log_audit_event({
            'event_type': 'DOCUMENT_DOWNLOAD',
            'severity': 'MEDIUM',
            'user_id': 'safety_officer',
            'action': 'download_safety_certificate',
            'resource_type': 'safety_document',
            'resource_id': 'CERT_SOLAS_2024_001',
            'metadata': {
                'document_classification': 'restricted',
                'download_reason': 'port_state_control_inspection'
            },
            'retention_policy': 'SAFETY'
        })
        event_ids.append(doc_event_id)
        
        # Financial transaction event
        financial_event_id = await audit_system.log_audit_event({
            'event_type': 'FINANCIAL_TRANSACTION',
            'severity': 'HIGH',
            'user_id': 'port_accountant',
            'action': 'process_port_fees',
            'resource_type': 'financial_record',
            'resource_id': 'TXN_PORT_2024_0157',
            'old_value': {'amount': 0, 'status': 'pending'},
            'new_value': {'amount': 15000, 'status': 'processed'},
            'metadata': {
                'vessel_id': 'MV_ENTERPRISE',
                'fee_type': 'berthing_charges',
                'currency': 'USD'
            },
            'retention_policy': 'FINANCIAL'
        })
        event_ids.append(financial_event_id)
        
        print(f"Logged {len(event_ids)} audit events")
        
        # Create audit block
        block_id = await audit_system.create_audit_block(event_ids)
        print(f"Created audit block: {block_id}")
        
        # Establish chain of custody for a document
        custody_hash = await audit_system.establish_chain_of_custody(
            document_id="CERT_SOLAS_2024_001",
            document_type="safety_certificate",
            classification_level="restricted",
            initial_custodian="safety_officer"
        )
        print(f"Chain of custody established with integrity hash: {custody_hash}")
        
        # Transfer custody
        transfer_event_id = await audit_system.transfer_custody(
            document_id="CERT_SOLAS_2024_001",
            from_custodian="safety_officer",
            to_custodian="port_manager",
            reason="port_state_control_inspection",
            location="port_office",
            witness="deputy_manager"
        )
        print(f"Custody transferred: {transfer_event_id}")
        
        # Verify audit chain integrity
        verification_result = await audit_system.verify_audit_chain_integrity()
        print(f"Chain integrity verification: {verification_result['overall_status']}")
        print(f"Verified {verification_result['verified_blocks']}/{verification_result['total_blocks']} blocks")
        
        # Get audit statistics
        stats = await audit_system.get_audit_statistics(days=7)
        print(f"Total events in last 7 days: {stats['event_statistics']['total_events']}")
        print(f"Chain blocks created: {stats['chain_statistics']['total_blocks']}")
        
        # Search audit events
        search_results = await audit_system.search_audit_events({
            'user_id': 'safety_officer',
            'event_type': 'DOCUMENT_DOWNLOAD'
        }, limit=10)
        print(f"Found {len(search_results)} matching events")
        
        # Process retention schedule (would be run periodically)
        retention_results = await audit_system.process_retention_schedule()
        print(f"Retention processing: {retention_results['archived']} archived, {retention_results['deleted']} deleted")
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")

if __name__ == "__main__":
    asyncio.run(main())