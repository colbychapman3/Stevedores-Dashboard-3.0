"""
Secure File Upload Handler for Stevedores Dashboard 3.0
Comprehensive file upload security with quarantine system and maritime document processing
"""

import os
import tempfile
import shutil
import logging
from typing import Dict, Any, Optional, List, Tuple, BinaryIO
from datetime import datetime, timezone
from pathlib import Path
from flask import request, current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
import hashlib
import json

from .file_security_scanner import get_file_scanner, FileSecurityReport, FileSecurityThreat, FileValidationResult
from .audit_logger import get_audit_logger, AuditEventType, AuditSeverity
from utils.security_config import SecurityConfig

logger = logging.getLogger(__name__)

class SecureFileUploadResult:
    """Result of secure file upload operation"""
    
    def __init__(self):
        self.success = False
        self.file_id = None
        self.secure_path = None
        self.security_report = None
        self.error_message = None
        self.quarantined = False
        self.processing_time = 0.0
        self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            'success': self.success,
            'file_id': self.file_id,
            'secure_path': self.secure_path,
            'security_report': self.security_report.to_dict() if self.security_report else None,
            'error_message': self.error_message,
            'quarantined': self.quarantined,
            'processing_time': self.processing_time,
            'metadata': self.metadata,
        }

class SecureFileHandler:
    """Secure file upload handler with comprehensive security validation"""
    
    def __init__(self):
        self.config = SecurityConfig()
        self.scanner = get_file_scanner()
        self.audit_logger = get_audit_logger()
        
        # Upload directories
        self.upload_dir = self._setup_upload_directory()
        self.temp_dir = self._setup_temp_directory()
        self.secure_dir = self._setup_secure_directory()
        
        # File processing tracking
        self.upload_registry = {}
        
        logger.info("Secure file handler initialized for maritime operations")
    
    def _setup_upload_directory(self) -> str:
        """Set up main upload directory"""
        upload_dir = self.config.FILE_UPLOAD_SECURITY['upload_folder']
        os.makedirs(upload_dir, exist_ok=True)
        
        # Create subdirectories for organization
        subdirs = [
            'documents', 'images', 'manifests', 'reports', 
            'temporary', 'processed', 'archived'
        ]
        
        for subdir in subdirs:
            os.makedirs(os.path.join(upload_dir, subdir), exist_ok=True)
        
        return upload_dir
    
    def _setup_temp_directory(self) -> str:
        """Set up temporary processing directory"""
        temp_dir = self.config.FILE_UPLOAD_SECURITY['temp_folder']
        os.makedirs(temp_dir, exist_ok=True)
        
        # Set restrictive permissions
        try:
            os.chmod(temp_dir, 0o700)
        except OSError:
            pass
        
        return temp_dir
    
    def _setup_secure_directory(self) -> str:
        """Set up secure storage directory for validated files"""
        secure_dir = os.path.join(self.upload_dir, 'secure')
        os.makedirs(secure_dir, exist_ok=True)
        
        # Set restrictive permissions
        try:
            os.chmod(secure_dir, 0o755)
        except OSError:
            pass
        
        return secure_dir
    
    def handle_upload(
        self, 
        file_storage: FileStorage,
        user_id: int,
        document_type: str = 'general',
        vessel_id: Optional[int] = None,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> SecureFileUploadResult:
        """
        Handle secure file upload with comprehensive validation
        
        Args:
            file_storage: Flask FileStorage object
            user_id: ID of user uploading file
            document_type: Type of maritime document
            vessel_id: Associated vessel ID (if applicable)
            additional_metadata: Additional file metadata
            
        Returns:
            SecureFileUploadResult: Upload processing result
        """
        start_time = datetime.now()
        result = SecureFileUploadResult()
        
        try:
            logger.info(f"Processing file upload: {file_storage.filename} for user {user_id}")
            
            # Validate file storage object
            if not self._validate_file_storage(file_storage, result):
                return result
            
            # Generate secure filename and paths
            original_filename = file_storage.filename
            secure_name = self._generate_secure_filename(original_filename)
            temp_path = os.path.join(self.temp_dir, secure_name)
            
            # Save to temporary location for scanning
            file_storage.save(temp_path)
            
            # Perform comprehensive security scan
            security_report = self.scanner.scan_file(temp_path, original_filename)
            result.security_report = security_report
            
            # Log upload attempt
            self.audit_logger.log_event(
                AuditEventType.DOCUMENT_UPLOADED,
                f"File upload attempted: {original_filename}",
                details={
                    'original_filename': original_filename,
                    'secure_filename': secure_name,
                    'file_size': security_report.file_size,
                    'mime_type': security_report.mime_type,
                    'document_type': document_type,
                    'vessel_id': vessel_id,
                    'user_id': user_id,
                },
                severity=AuditSeverity.MEDIUM,
                maritime_context={
                    'upload_operation': True,
                    'document_type': document_type,
                    'vessel_id': vessel_id,
                },
                compliance_flags=['file_upload', 'maritime_document']
            )
            
            # Process based on security scan results
            if self._should_reject_file(security_report):
                result.success = False
                result.error_message = self._get_rejection_reason(security_report)
                result.quarantined = security_report.quarantined
                
                # Log security rejection
                self.audit_logger.log_security_event(
                    AuditEventType.SECURITY_VIOLATION,
                    f"File upload rejected: {original_filename}",
                    details={
                        'rejection_reason': result.error_message,
                        'security_threats': security_report.threats_detected,
                        'suspicious_patterns': security_report.suspicious_patterns,
                    }
                )
                
                # Clean up temp file if not quarantined
                if not security_report.quarantined:
                    self._safe_delete_file(temp_path)
                
                return result
            
            # File passed security checks - process for secure storage
            file_id = self._generate_file_id(security_report, user_id)
            secure_path = self._move_to_secure_storage(
                temp_path, file_id, document_type, security_report
            )
            
            # Create file metadata
            metadata = self._create_file_metadata(
                file_id, original_filename, secure_name, security_report,
                user_id, document_type, vessel_id, additional_metadata
            )
            
            # Store in registry
            self.upload_registry[file_id] = metadata
            
            # Update result
            result.success = True
            result.file_id = file_id
            result.secure_path = secure_path
            result.metadata = metadata
            result.quarantined = security_report.quarantined
            
            # Log successful upload
            self.audit_logger.log_maritime_operation(
                AuditEventType.DOCUMENT_UPLOADED,
                f"File upload successful: {original_filename}",
                vessel_id=vessel_id,
                details={
                    'file_id': file_id,
                    'secure_path': secure_path,
                    'security_status': security_report.security_threat.value,
                    'document_classification': security_report.maritime_classification,
                }
            )
            
            logger.info(f"File upload successful: {file_id}")
            
        except Exception as e:
            logger.error(f"Error processing file upload: {e}")
            result.success = False
            result.error_message = f"Upload processing failed: {str(e)}"
            
            # Log upload error
            self.audit_logger.log_security_event(
                AuditEventType.SECURITY_VIOLATION,
                f"File upload error: {str(e)}",
                details={'original_filename': file_storage.filename if file_storage else 'unknown'}
            )
            
            # Clean up temp file
            if 'temp_path' in locals():
                self._safe_delete_file(temp_path)
        
        finally:
            # Calculate processing time
            result.processing_time = (datetime.now() - start_time).total_seconds()
        
        return result
    
    def _validate_file_storage(self, file_storage: FileStorage, result: SecureFileUploadResult) -> bool:
        """Validate Flask FileStorage object"""
        
        if not file_storage:
            result.error_message = "No file provided"
            return False
        
        if not file_storage.filename:
            result.error_message = "No filename provided"
            return False
        
        if file_storage.filename == '':
            result.error_message = "Empty filename provided"
            return False
        
        # Check for path traversal in filename
        if '..' in file_storage.filename or '/' in file_storage.filename or '\\' in file_storage.filename:
            result.error_message = "Invalid filename - path traversal detected"
            self.audit_logger.log_security_event(
                AuditEventType.SECURITY_VIOLATION,
                f"Path traversal attempt in filename: {file_storage.filename}"
            )
            return False
        
        return True
    
    def _generate_secure_filename(self, original_filename: str) -> str:
        """Generate secure filename for processing"""
        
        # Use werkzeug's secure_filename as base
        base_secure = secure_filename(original_filename)
        
        # Add timestamp and random component for uniqueness
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        random_component = os.urandom(4).hex()
        
        # Preserve original extension
        name, ext = os.path.splitext(base_secure)
        
        return f"{timestamp}_{random_component}_{name}{ext}"
    
    def _should_reject_file(self, security_report: FileSecurityReport) -> bool:
        """Determine if file should be rejected based on security report"""
        
        # Reject malicious files
        if security_report.security_threat == FileSecurityThreat.MALICIOUS:
            return True
        
        # Reject invalid files
        if security_report.validation_result != FileValidationResult.VALID:
            return True
        
        # Reject files with too many threats
        if len(security_report.threats_detected) > 0:
            return True
        
        # Allow suspicious files but log them (they may be quarantined)
        return False
    
    def _get_rejection_reason(self, security_report: FileSecurityReport) -> str:
        """Get human-readable rejection reason"""
        
        if security_report.security_threat == FileSecurityThreat.MALICIOUS:
            return f"File rejected due to security threats: {', '.join(security_report.threats_detected)}"
        
        if security_report.validation_result == FileValidationResult.INVALID_TYPE:
            return "File type not allowed"
        
        if security_report.validation_result == FileValidationResult.INVALID_SIZE:
            return "File size exceeds maximum allowed size"
        
        if security_report.validation_result == FileValidationResult.INVALID_CONTENT:
            return "File content is invalid or corrupted"
        
        if security_report.validation_result == FileValidationResult.SECURITY_THREAT:
            return "File contains security threats"
        
        if len(security_report.threats_detected) > 0:
            return f"Security threats detected: {', '.join(security_report.threats_detected)}"
        
        return "File rejected due to security policy"
    
    def _generate_file_id(self, security_report: FileSecurityReport, user_id: int) -> str:
        """Generate unique file ID"""
        
        # Combine file hash, user ID, and timestamp
        timestamp = datetime.now().isoformat()
        combined = f"{security_report.file_hash}_{user_id}_{timestamp}"
        
        # Generate short hash
        file_id_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]
        
        return f"file_{file_id_hash}"
    
    def _move_to_secure_storage(
        self, 
        temp_path: str, 
        file_id: str, 
        document_type: str,
        security_report: FileSecurityReport
    ) -> str:
        """Move file from temp to secure storage"""
        
        # Determine storage subdirectory based on document type
        subdir_map = {
            'bill_of_lading': 'documents',
            'manifest': 'manifests',
            'customs_declaration': 'documents',
            'inspection_report': 'reports',
            'damage_report': 'reports',
            'tally_sheet': 'documents',
            'delivery_receipt': 'documents',
            'image': 'images',
            'other': 'documents',
            'general': 'documents',
        }
        
        subdir = subdir_map.get(document_type, 'documents')
        
        # Create year/month subdirectories for organization
        now = datetime.now()
        date_path = os.path.join(subdir, str(now.year), f"{now.month:02d}")
        full_dir = os.path.join(self.secure_dir, date_path)
        os.makedirs(full_dir, exist_ok=True)
        
        # Generate secure storage filename
        original_ext = Path(security_report.filename).suffix
        secure_filename = f"{file_id}{original_ext}"
        secure_path = os.path.join(full_dir, secure_filename)
        
        # Move file to secure storage
        shutil.move(temp_path, secure_path)
        
        # Set appropriate permissions
        try:
            os.chmod(secure_path, 0o644)
        except OSError:
            pass
        
        return secure_path
    
    def _create_file_metadata(
        self,
        file_id: str,
        original_filename: str,
        secure_filename: str,
        security_report: FileSecurityReport,
        user_id: int,
        document_type: str,
        vessel_id: Optional[int],
        additional_metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create comprehensive file metadata"""
        
        metadata = {
            'file_id': file_id,
            'original_filename': original_filename,
            'secure_filename': secure_filename,
            'upload_timestamp': datetime.now(timezone.utc).isoformat(),
            'user_id': user_id,
            'document_type': document_type,
            'vessel_id': vessel_id,
            
            # Security information
            'security_report': security_report.to_dict(),
            'security_status': security_report.security_threat.value,
            'validation_status': security_report.validation_result.value,
            'quarantined': security_report.quarantined,
            
            # File information
            'file_size': security_report.file_size,
            'mime_type': security_report.mime_type,
            'file_hash': security_report.file_hash,
            
            # Maritime classification
            'maritime_document_type': security_report.document_type,
            'maritime_classification': security_report.maritime_classification,
            'compliance_flags': security_report.compliance_flags,
            
            # Processing information
            'scan_duration': security_report.scan_duration,
            'threats_detected': security_report.threats_detected,
            'suspicious_patterns': security_report.suspicious_patterns,
            'metadata_concerns': security_report.metadata_concerns,
        }
        
        # Add additional metadata if provided
        if additional_metadata:
            metadata['additional'] = additional_metadata
        
        return metadata
    
    def _safe_delete_file(self, file_path: str):
        """Safely delete a file"""
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                logger.debug(f"Deleted file: {file_path}")
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
    
    def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file metadata by ID"""
        return self.upload_registry.get(file_id)
    
    def get_secure_file_path(self, file_id: str) -> Optional[str]:
        """Get secure file path by ID"""
        metadata = self.get_file_metadata(file_id)
        if metadata:
            return metadata.get('secure_path')
        return None
    
    def list_user_files(
        self, 
        user_id: int, 
        document_type: Optional[str] = None,
        vessel_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """List files uploaded by user with optional filters"""
        
        user_files = []
        
        for file_id, metadata in self.upload_registry.items():
            if metadata.get('user_id') != user_id:
                continue
            
            if document_type and metadata.get('document_type') != document_type:
                continue
            
            if vessel_id and metadata.get('vessel_id') != vessel_id:
                continue
            
            # Return sanitized metadata (remove sensitive security details)
            sanitized = {
                'file_id': metadata['file_id'],
                'original_filename': metadata['original_filename'],
                'upload_timestamp': metadata['upload_timestamp'],
                'document_type': metadata['document_type'],
                'vessel_id': metadata['vessel_id'],
                'file_size': metadata['file_size'],
                'mime_type': metadata['mime_type'],
                'security_status': metadata['security_status'],
                'maritime_document_type': metadata.get('maritime_document_type'),
                'quarantined': metadata['quarantined'],
            }
            
            user_files.append(sanitized)
        
        # Sort by upload timestamp (newest first)
        user_files.sort(key=lambda x: x['upload_timestamp'], reverse=True)
        
        return user_files
    
    def delete_file(self, file_id: str, user_id: int) -> bool:
        """Delete a file (with user permission check)"""
        
        try:
            metadata = self.get_file_metadata(file_id)
            if not metadata:
                return False
            
            # Check user permission
            if metadata.get('user_id') != user_id:
                logger.warning(f"User {user_id} attempted to delete file {file_id} owned by user {metadata.get('user_id')}")
                return False
            
            # Delete physical file
            secure_path = metadata.get('secure_path')
            if secure_path and os.path.exists(secure_path):
                os.unlink(secure_path)
            
            # Remove from registry
            del self.upload_registry[file_id]
            
            # Log deletion
            self.audit_logger.log_event(
                AuditEventType.DOCUMENT_DELETED,
                f"File deleted: {metadata['original_filename']}",
                details={
                    'file_id': file_id,
                    'user_id': user_id,
                    'document_type': metadata.get('document_type'),
                },
                severity=AuditSeverity.MEDIUM
            )
            
            logger.info(f"File deleted: {file_id} by user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file {file_id}: {e}")
            return False
    
    def cleanup_temp_files(self, max_age_hours: int = 24):
        """Clean up old temporary files"""
        
        try:
            cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
            cleaned_count = 0
            
            for filename in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, filename)
                
                if os.path.isfile(file_path):
                    file_stat = os.stat(file_path)
                    
                    if file_stat.st_mtime < cutoff_time:
                        os.unlink(file_path)
                        cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} temporary files older than {max_age_hours} hours")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {e}")
            return 0

# Global secure file handler instance
secure_file_handler = SecureFileHandler()

def get_secure_file_handler() -> SecureFileHandler:
    """Get the global secure file handler instance"""
    return secure_file_handler

def handle_secure_upload(
    file_storage: FileStorage,
    user_id: int,
    document_type: str = 'general',
    vessel_id: Optional[int] = None,
    additional_metadata: Optional[Dict[str, Any]] = None
) -> SecureFileUploadResult:
    """
    Handle secure file upload with comprehensive validation
    
    Args:
        file_storage: Flask FileStorage object
        user_id: ID of user uploading file
        document_type: Type of maritime document
        vessel_id: Associated vessel ID (if applicable)
        additional_metadata: Additional file metadata
        
    Returns:
        SecureFileUploadResult: Upload processing result
    """
    return secure_file_handler.handle_upload(
        file_storage, user_id, document_type, vessel_id, additional_metadata
    )