"""
File Security Scanner for Stevedores Dashboard 3.0
Comprehensive file validation, scanning, and security analysis for maritime documents
"""

import os
import hashlib
import logging
import magic
import filetype
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from PIL import Image
import tempfile
import shutil

logger = logging.getLogger(__name__)

class FileSecurityThreat(Enum):
    """File security threat levels"""
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"
    QUARANTINED = "quarantined"
    BLOCKED = "blocked"

class FileValidationResult(Enum):
    """File validation results"""
    VALID = "valid"
    INVALID_TYPE = "invalid_type"
    INVALID_SIZE = "invalid_size"
    INVALID_CONTENT = "invalid_content"
    SECURITY_THREAT = "security_threat"
    CORRUPTED = "corrupted"

@dataclass
class FileSecurityReport:
    """Comprehensive file security analysis report"""
    
    filename: str
    file_size: int
    mime_type: str
    magic_type: str
    file_hash: str
    
    # Validation results
    validation_result: FileValidationResult
    security_threat: FileSecurityThreat
    
    # Analysis details
    analysis_timestamp: str
    scan_duration: float
    
    # Security findings
    threats_detected: List[str]
    suspicious_patterns: List[str]
    metadata_concerns: List[str]
    
    # Maritime document classification
    document_type: Optional[str] = None
    maritime_classification: Optional[str] = None
    compliance_flags: List[str] = None
    
    # Quarantine information
    quarantined: bool = False
    quarantine_reason: Optional[str] = None
    quarantine_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary"""
        return {
            'filename': self.filename,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'magic_type': self.magic_type,
            'file_hash': self.file_hash,
            'validation_result': self.validation_result.value,
            'security_threat': self.security_threat.value,
            'analysis_timestamp': self.analysis_timestamp,
            'scan_duration': self.scan_duration,
            'threats_detected': self.threats_detected,
            'suspicious_patterns': self.suspicious_patterns,
            'metadata_concerns': self.metadata_concerns,
            'document_type': self.document_type,
            'maritime_classification': self.maritime_classification,
            'compliance_flags': self.compliance_flags or [],
            'quarantined': self.quarantined,
            'quarantine_reason': self.quarantine_reason,
            'quarantine_path': self.quarantine_path,
        }

class FileSecurityScanner:
    """Comprehensive file security scanner for maritime documents"""
    
    def __init__(self):
        self.config = self._load_security_config()
        self.quarantine_dir = self._setup_quarantine_directory()
        self.magic_detector = magic.Magic(mime=True)
        
        # Maritime document signatures
        self.maritime_patterns = self._load_maritime_patterns()
        
        # Malicious file signatures (simplified for demo)
        self.malicious_signatures = self._load_malicious_signatures()
        
        logger.info("File security scanner initialized for maritime operations")
    
    def _load_security_config(self) -> Dict[str, Any]:
        """Load file security configuration"""
        return {
            'max_file_size': 50 * 1024 * 1024,  # 50MB
            'allowed_extensions': {
                'pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv',
                'txt', 'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff',
                'json', 'xml', 'zip'
            },
            'allowed_mime_types': {
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'text/csv', 'text/plain', 'text/xml',
                'image/png', 'image/jpeg', 'image/gif', 'image/bmp', 'image/tiff',
                'application/json', 'application/xml',
                'application/zip'
            },
            'quarantine_enabled': True,
            'auto_quarantine_threats': ['malicious'],
            'scan_metadata': True,
            'validate_image_content': True,
            'check_embedded_files': True,
        }
    
    def _setup_quarantine_directory(self) -> str:
        """Set up quarantine directory for suspicious files"""
        quarantine_dir = os.path.join('uploads', 'quarantine')
        os.makedirs(quarantine_dir, exist_ok=True)
        
        # Set restrictive permissions
        try:
            os.chmod(quarantine_dir, 0o700)
        except OSError:
            pass  # May not work on all systems
        
        return quarantine_dir
    
    def _load_maritime_patterns(self) -> Dict[str, List[str]]:
        """Load maritime document patterns and signatures"""
        return {
            'bill_of_lading': [
                b'BILL OF LADING',
                b'B/L NO',
                b'SHIPPER',
                b'CONSIGNEE',
                b'NOTIFY PARTY'
            ],
            'manifest': [
                b'CARGO MANIFEST',
                b'VESSEL NAME',
                b'VOYAGE',
                b'CONTAINER',
                b'CARGO DESCRIPTION'
            ],
            'customs_declaration': [
                b'CUSTOMS DECLARATION',
                b'HARMONIZED CODE',
                b'DUTY',
                b'IMPORT LICENSE'
            ],
            'inspection_report': [
                b'INSPECTION REPORT',
                b'CARGO CONDITION',
                b'SURVEYOR',
                b'CERTIFICATE'
            ]
        }
    
    def _load_malicious_signatures(self) -> List[bytes]:
        """Load known malicious file signatures"""
        return [
            # Common malware signatures (simplified examples)
            b'\x4d\x5a\x90\x00',  # PE executable header
            b'\x50\x4b\x03\x04',  # ZIP with suspicious patterns
            b'<script',           # Embedded scripts
            b'javascript:',       # JavaScript URLs
            b'data:text/html',    # Data URLs with HTML
            b'<%@',              # Server-side includes
            b'<?php',            # PHP code
            b'eval(',            # Code evaluation
        ]
    
    def scan_file(self, file_path: str, filename: str = None) -> FileSecurityReport:
        """
        Perform comprehensive security scan of a file
        
        Args:
            file_path: Path to the file to scan
            filename: Original filename (if different from file_path)
            
        Returns:
            FileSecurityReport: Comprehensive security analysis report
        """
        start_time = datetime.now()
        
        if not filename:
            filename = os.path.basename(file_path)
        
        logger.info(f"Starting security scan of file: {filename}")
        
        try:
            # Basic file information
            file_size = os.path.getsize(file_path)
            file_hash = self._calculate_file_hash(file_path)
            
            # MIME type detection
            mime_type = self._detect_mime_type(file_path)
            magic_type = self._detect_magic_type(file_path)
            
            # Initialize report
            report = FileSecurityReport(
                filename=filename,
                file_size=file_size,
                mime_type=mime_type,
                magic_type=magic_type,
                file_hash=file_hash,
                validation_result=FileValidationResult.VALID,
                security_threat=FileSecurityThreat.CLEAN,
                analysis_timestamp=datetime.now(timezone.utc).isoformat(),
                scan_duration=0.0,
                threats_detected=[],
                suspicious_patterns=[],
                metadata_concerns=[],
                compliance_flags=[]
            )
            
            # Perform validation checks
            self._validate_file_basic(report, file_path)
            self._validate_file_content(report, file_path)
            self._scan_for_threats(report, file_path)
            self._analyze_metadata(report, file_path)
            self._classify_maritime_document(report, file_path)
            
            # Determine final security status
            self._determine_security_status(report)
            
            # Handle quarantine if necessary
            if self._should_quarantine(report):
                self._quarantine_file(report, file_path)
            
            # Calculate scan duration
            scan_duration = (datetime.now() - start_time).total_seconds()
            report.scan_duration = scan_duration
            
            logger.info(f"File scan completed: {filename} - {report.security_threat.value}")
            
            return report
            
        except Exception as e:
            logger.error(f"Error scanning file {filename}: {e}")
            
            # Return error report
            return FileSecurityReport(
                filename=filename,
                file_size=0,
                mime_type='unknown',
                magic_type='unknown',
                file_hash='',
                validation_result=FileValidationResult.CORRUPTED,
                security_threat=FileSecurityThreat.BLOCKED,
                analysis_timestamp=datetime.now(timezone.utc).isoformat(),
                scan_duration=(datetime.now() - start_time).total_seconds(),
                threats_detected=[f'Scan error: {str(e)}'],
                suspicious_patterns=[],
                metadata_concerns=[],
                compliance_flags=['scan_error']
            )
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file"""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating file hash: {e}")
            return ''
    
    def _detect_mime_type(self, file_path: str) -> str:
        """Detect MIME type using multiple methods"""
        try:
            # Try python-magic first
            try:
                mime_type = self.magic_detector.from_file(file_path)
                if mime_type:
                    return mime_type
            except Exception:
                pass
            
            # Try filetype library
            try:
                kind = filetype.guess(file_path)
                if kind:
                    return kind.mime
            except Exception:
                pass
            
            return 'application/octet-stream'
            
        except Exception as e:
            logger.error(f"Error detecting MIME type: {e}")
            return 'unknown'
    
    def _detect_magic_type(self, file_path: str) -> str:
        """Detect file type using magic numbers"""
        try:
            # Read first 512 bytes for magic number analysis
            with open(file_path, 'rb') as f:
                header = f.read(512)
            
            # Check for common file signatures
            if header.startswith(b'%PDF'):
                return 'PDF Document'
            elif header.startswith(b'PK\x03\x04'):
                return 'ZIP Archive (Office Document)'
            elif header.startswith(b'\x89PNG'):
                return 'PNG Image'
            elif header.startswith(b'\xff\xd8\xff'):
                return 'JPEG Image'
            elif header.startswith(b'GIF8'):
                return 'GIF Image'
            elif header.startswith(b'\xd0\xcf\x11\xe0'):
                return 'Microsoft Office Document'
            else:
                return 'Unknown Binary'
                
        except Exception as e:
            logger.error(f"Error detecting magic type: {e}")
            return 'unknown'
    
    def _validate_file_basic(self, report: FileSecurityReport, file_path: str):
        """Perform basic file validation"""
        
        # Check file size
        if report.file_size > self.config['max_file_size']:
            report.validation_result = FileValidationResult.INVALID_SIZE
            report.threats_detected.append(f'File too large: {report.file_size} bytes')
            return
        
        # Check file extension
        ext = Path(report.filename).suffix.lower().lstrip('.')
        if ext not in self.config['allowed_extensions']:
            report.validation_result = FileValidationResult.INVALID_TYPE
            report.threats_detected.append(f'File extension not allowed: .{ext}')
            return
        
        # Check MIME type
        if report.mime_type not in self.config['allowed_mime_types']:
            report.validation_result = FileValidationResult.INVALID_TYPE
            report.threats_detected.append(f'MIME type not allowed: {report.mime_type}')
            return
    
    def _validate_file_content(self, report: FileSecurityReport, file_path: str):
        """Validate file content integrity"""
        
        try:
            # Validate images
            if report.mime_type.startswith('image/'):
                self._validate_image_content(report, file_path)
            
            # Validate PDF documents
            elif report.mime_type == 'application/pdf':
                self._validate_pdf_content(report, file_path)
            
            # Validate Office documents
            elif 'officedocument' in report.mime_type:
                self._validate_office_content(report, file_path)
            
        except Exception as e:
            logger.error(f"Error validating file content: {e}")
            report.suspicious_patterns.append(f'Content validation error: {str(e)}')
    
    def _validate_image_content(self, report: FileSecurityReport, file_path: str):
        """Validate image content using Pillow"""
        
        if not self.config['validate_image_content']:
            return
        
        try:
            with Image.open(file_path) as img:
                # Verify image integrity
                img.verify()
                
                # Reopen for further analysis (verify() closes the image)
                with Image.open(file_path) as img2:
                    # Check for suspicious dimensions
                    width, height = img2.size
                    if width > 50000 or height > 50000:
                        report.suspicious_patterns.append('Unusually large image dimensions')
                    
                    # Check for suspicious metadata
                    if hasattr(img2, '_getexif') and img2._getexif():
                        exif_data = img2._getexif()
                        if exif_data and len(str(exif_data)) > 10000:
                            report.metadata_concerns.append('Excessive EXIF metadata')
                
        except Exception as e:
            report.validation_result = FileValidationResult.INVALID_CONTENT
            report.threats_detected.append(f'Image validation failed: {str(e)}')
    
    def _validate_pdf_content(self, report: FileSecurityReport, file_path: str):
        """Basic PDF validation"""
        
        try:
            # Check for PDF header
            with open(file_path, 'rb') as f:
                header = f.read(8)
                if not header.startswith(b'%PDF'):
                    report.validation_result = FileValidationResult.INVALID_CONTENT
                    report.threats_detected.append('Invalid PDF header')
                    return
                
                # Read more content for analysis
                f.seek(0)
                content = f.read(8192)  # First 8KB
                
                # Check for suspicious patterns in PDF
                suspicious_pdf_patterns = [
                    b'/JavaScript', b'/JS', b'/Launch', b'/EmbeddedFile',
                    b'/OpenAction', b'/AA', b'/XFA'
                ]
                
                for pattern in suspicious_pdf_patterns:
                    if pattern in content:
                        report.suspicious_patterns.append(f'Suspicious PDF element: {pattern.decode("utf-8", errors="ignore")}')
                
        except Exception as e:
            report.suspicious_patterns.append(f'PDF validation error: {str(e)}')
    
    def _validate_office_content(self, report: FileSecurityReport, file_path: str):
        """Basic Office document validation"""
        
        try:
            # Office documents are ZIP files
            import zipfile
            
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                # Check for suspicious files in ZIP
                suspicious_files = []
                for file_info in zip_file.filelist:
                    filename = file_info.filename.lower()
                    
                    # Check for executable files
                    if filename.endswith(('.exe', '.scr', '.bat', '.cmd', '.com')):
                        suspicious_files.append(filename)
                    
                    # Check for macro files
                    if filename.endswith('.bin') and 'macro' in filename:
                        suspicious_files.append(filename)
                
                if suspicious_files:
                    report.suspicious_patterns.extend([f'Suspicious embedded file: {f}' for f in suspicious_files])
                
        except zipfile.BadZipFile:
            report.validation_result = FileValidationResult.INVALID_CONTENT
            report.threats_detected.append('Corrupted Office document')
        except Exception as e:
            report.suspicious_patterns.append(f'Office document validation error: {str(e)}')
    
    def _scan_for_threats(self, report: FileSecurityReport, file_path: str):
        """Scan for security threats and malicious patterns"""
        
        try:
            # Read file content for pattern matching
            with open(file_path, 'rb') as f:
                content = f.read(1024 * 1024)  # Read first 1MB
            
            # Check for malicious signatures
            for signature in self.malicious_signatures:
                if signature in content:
                    report.threats_detected.append(f'Malicious signature detected: {signature[:20]}...')
                    report.security_threat = FileSecurityThreat.MALICIOUS
            
            # Check for suspicious patterns
            suspicious_patterns = [
                b'<script>',
                b'javascript:',
                b'data:text/html',
                b'eval(',
                b'document.write',
                b'base64',
                b'powershell',
                b'cmd.exe',
                b'system(',
                b'exec(',
            ]
            
            for pattern in suspicious_patterns:
                if pattern in content:
                    report.suspicious_patterns.append(f'Suspicious pattern: {pattern.decode("utf-8", errors="ignore")}')
                    if report.security_threat == FileSecurityThreat.CLEAN:
                        report.security_threat = FileSecurityThreat.SUSPICIOUS
            
            # Check file size vs content ratio (potential steganography)
            if len(content) < report.file_size * 0.1:  # Less than 10% readable content
                report.suspicious_patterns.append('Low content-to-size ratio (possible steganography)')
            
        except Exception as e:
            logger.error(f"Error scanning for threats: {e}")
            report.suspicious_patterns.append(f'Threat scan error: {str(e)}')
    
    def _analyze_metadata(self, report: FileSecurityReport, file_path: str):
        """Analyze file metadata for security concerns"""
        
        if not self.config['scan_metadata']:
            return
        
        try:
            # Get file stats
            file_stat = os.stat(file_path)
            
            # Check for suspicious timestamps
            current_time = datetime.now().timestamp()
            
            # File modified in the future
            if file_stat.st_mtime > current_time + 86400:  # More than 1 day in future
                report.metadata_concerns.append('File modified date in the future')
            
            # Very old modification time (potential timestamp manipulation)
            if file_stat.st_mtime < 946684800:  # Before year 2000
                report.metadata_concerns.append('Suspicious modification timestamp')
            
        except Exception as e:
            logger.error(f"Error analyzing metadata: {e}")
    
    def _classify_maritime_document(self, report: FileSecurityReport, file_path: str):
        """Classify maritime document type based on content"""
        
        try:
            # Read file content for classification
            with open(file_path, 'rb') as f:
                content = f.read(8192).lower()  # First 8KB in lowercase
            
            # Check for maritime document patterns
            for doc_type, patterns in self.maritime_patterns.items():
                matches = sum(1 for pattern in patterns if pattern.lower() in content)
                
                if matches >= 2:  # At least 2 patterns match
                    report.document_type = doc_type
                    report.maritime_classification = 'maritime_official'
                    report.compliance_flags.append('maritime_document')
                    break
            
            # If no specific type found but has maritime keywords
            maritime_keywords = [
                b'vessel', b'ship', b'cargo', b'port', b'berth',
                b'container', b'manifest', b'customs', b'stevedore'
            ]
            
            maritime_score = sum(1 for keyword in maritime_keywords if keyword in content)
            
            if maritime_score >= 3 and not report.document_type:
                report.document_type = 'maritime_general'
                report.maritime_classification = 'maritime_related'
                report.compliance_flags.append('maritime_content')
            
        except Exception as e:
            logger.error(f"Error classifying maritime document: {e}")
    
    def _determine_security_status(self, report: FileSecurityReport):
        """Determine final security status based on all findings"""
        
        # Count threats and suspicious patterns
        threat_count = len(report.threats_detected)
        suspicious_count = len(report.suspicious_patterns)
        metadata_concerns = len(report.metadata_concerns)
        
        # Determine threat level
        if threat_count > 0:
            report.security_threat = FileSecurityThreat.MALICIOUS
        elif suspicious_count >= 3 or metadata_concerns >= 2:
            report.security_threat = FileSecurityThreat.SUSPICIOUS
        elif suspicious_count > 0 or metadata_concerns > 0:
            report.security_threat = FileSecurityThreat.SUSPICIOUS
        else:
            report.security_threat = FileSecurityThreat.CLEAN
        
        # Override validation result if security threats found
        if report.security_threat in [FileSecurityThreat.MALICIOUS, FileSecurityThreat.SUSPICIOUS]:
            if report.validation_result == FileValidationResult.VALID:
                report.validation_result = FileValidationResult.SECURITY_THREAT
    
    def _should_quarantine(self, report: FileSecurityReport) -> bool:
        """Determine if file should be quarantined"""
        
        if not self.config['quarantine_enabled']:
            return False
        
        # Auto-quarantine based on configuration
        if report.security_threat.value in self.config['auto_quarantine_threats']:
            return True
        
        # Quarantine if validation failed due to security
        if report.validation_result == FileValidationResult.SECURITY_THREAT:
            return True
        
        # Quarantine if too many suspicious patterns
        if len(report.suspicious_patterns) >= 5:
            return True
        
        return False
    
    def _quarantine_file(self, report: FileSecurityReport, file_path: str):
        """Move file to quarantine directory"""
        
        try:
            # Generate quarantine filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            quarantine_filename = f"{timestamp}_{report.file_hash[:8]}_{report.filename}"
            quarantine_path = os.path.join(self.quarantine_dir, quarantine_filename)
            
            # Copy file to quarantine (don't move original yet)
            shutil.copy2(file_path, quarantine_path)
            
            # Set restrictive permissions
            try:
                os.chmod(quarantine_path, 0o600)
            except OSError:
                pass
            
            # Update report
            report.quarantined = True
            report.quarantine_reason = f'Security threat: {report.security_threat.value}'
            report.quarantine_path = quarantine_path
            
            logger.warning(f"File quarantined: {report.filename} -> {quarantine_path}")
            
        except Exception as e:
            logger.error(f"Error quarantining file: {e}")
            report.metadata_concerns.append(f'Quarantine failed: {str(e)}')

# Global scanner instance
file_scanner = FileSecurityScanner()

def get_file_scanner() -> FileSecurityScanner:
    """Get the global file security scanner instance"""
    return file_scanner

def scan_uploaded_file(file_path: str, filename: str = None) -> FileSecurityReport:
    """
    Scan an uploaded file for security threats
    
    Args:
        file_path: Path to the file to scan
        filename: Original filename
        
    Returns:
        FileSecurityReport: Comprehensive security analysis
    """
    return file_scanner.scan_file(file_path, filename)

def is_file_safe(report: FileSecurityReport) -> bool:
    """
    Check if file is safe based on security report
    
    Args:
        report: File security report
        
    Returns:
        bool: True if file is safe to process
    """
    return (
        report.validation_result == FileValidationResult.VALID and
        report.security_threat == FileSecurityThreat.CLEAN and
        not report.quarantined
    )