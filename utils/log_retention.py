"""
Log Retention and Archival System for Stevedores Dashboard 3.0
Cost-effective log management with maritime compliance requirements
"""

import os
import gzip
import shutil
import time
import json
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import hashlib
import tarfile
from pathlib import Path
from collections import defaultdict

# Import components
from .structured_logger import get_structured_logger, ComponentType


class RetentionPolicy(Enum):
    """Log retention policies"""
    DEBUG_LOGS = "debug"           # 7 days
    INFO_LOGS = "info"            # 30 days
    WARNING_LOGS = "warning"      # 90 days
    ERROR_LOGS = "error"          # 365 days (1 year)
    CRITICAL_LOGS = "critical"    # 2555 days (7 years)
    AUDIT_LOGS = "audit"          # 2555 days (7 years - maritime compliance)
    MARITIME_LOGS = "maritime"    # 2555 days (7 years - regulatory requirement)
    SECURITY_LOGS = "security"    # 2555 days (7 years - compliance)
    COMPLIANCE_LOGS = "compliance" # 2555 days (7 years - regulatory)


class CompressionLevel(Enum):
    """Compression levels for archived logs"""
    NONE = 0
    FAST = 1      # Fast compression, larger files
    BALANCED = 6  # Balanced compression/speed
    MAXIMUM = 9   # Maximum compression, slower


class StorageLocation(Enum):
    """Storage location types"""
    LOCAL_DISK = "local"
    S3_BUCKET = "s3"
    GCS_BUCKET = "gcs"
    AZURE_BLOB = "azure"
    CLOUD_STORAGE = "cloud"


@dataclass
class RetentionConfig:
    """Configuration for log retention"""
    policy: RetentionPolicy
    retention_days: int
    compression_level: CompressionLevel = CompressionLevel.BALANCED
    storage_location: StorageLocation = StorageLocation.LOCAL_DISK
    archive_after_days: int = 7
    delete_after_days: Optional[int] = None
    cost_optimization: bool = True
    
    def __post_init__(self):
        if self.delete_after_days is None:
            self.delete_after_days = self.retention_days


class LogRetentionManager:
    """Comprehensive log retention and archival system"""
    
    def __init__(self, base_path: str = "/tmp/logs"):
        self.base_path = Path(base_path)
        self.archive_path = self.base_path / "archives"
        
        # Create directories
        self.base_path.mkdir(exist_ok=True)
        self.archive_path.mkdir(exist_ok=True)
        
        self.logger = get_structured_logger()
        
        # Initialize retention policies
        self.retention_configs = self._initialize_retention_policies()
        
        # Statistics tracking
        self.stats = {
            'files_archived': 0,
            'files_deleted': 0,
            'bytes_compressed': 0,
            'compression_ratio': 0.0,
            'last_cleanup': None,
            'storage_saved_bytes': 0
        }
        
        # Background processing
        self.is_active = False
        self.cleanup_thread = None
        self.cleanup_interval = int(os.getenv('LOG_CLEANUP_INTERVAL_HOURS', '24')) * 3600  # 24 hours
        
        # Cost optimization settings
        self.max_storage_mb = int(os.getenv('MAX_LOG_STORAGE_MB', '1024'))  # 1GB default
        self.compression_enabled = os.getenv('LOG_COMPRESSION_ENABLED', 'true').lower() == 'true'
        self.aggressive_cleanup = os.getenv('LOG_AGGRESSIVE_CLEANUP', 'false').lower() == 'true'
        
        self.logger.info(
            "Log retention manager initialized",
            component=ComponentType.AUDIT_SYSTEM.value,
            base_path=str(self.base_path),
            max_storage_mb=self.max_storage_mb,
            compression_enabled=self.compression_enabled
        )
    
    def _initialize_retention_policies(self) -> Dict[RetentionPolicy, RetentionConfig]:
        """Initialize retention policies with maritime compliance requirements"""
        configs = {}
        
        # Short-term retention for debug/info logs
        configs[RetentionPolicy.DEBUG_LOGS] = RetentionConfig(
            policy=RetentionPolicy.DEBUG_LOGS,
            retention_days=7,
            compression_level=CompressionLevel.FAST,
            archive_after_days=1,
            cost_optimization=True
        )
        
        configs[RetentionPolicy.INFO_LOGS] = RetentionConfig(
            policy=RetentionPolicy.INFO_LOGS,
            retention_days=30,
            compression_level=CompressionLevel.BALANCED,
            archive_after_days=3,
            cost_optimization=True
        )
        
        # Medium-term retention for warnings
        configs[RetentionPolicy.WARNING_LOGS] = RetentionConfig(
            policy=RetentionPolicy.WARNING_LOGS,
            retention_days=90,
            compression_level=CompressionLevel.BALANCED,
            archive_after_days=7,
            cost_optimization=True
        )
        
        # Long-term retention for errors
        configs[RetentionPolicy.ERROR_LOGS] = RetentionConfig(
            policy=RetentionPolicy.ERROR_LOGS,
            retention_days=365,
            compression_level=CompressionLevel.MAXIMUM,
            archive_after_days=14,
            cost_optimization=False  # Keep error logs accessible
        )
        
        # Very long-term retention for compliance (7 years = 2555 days)
        maritime_retention_days = int(os.getenv('MARITIME_LOG_RETENTION_DAYS', '2555'))
        
        configs[RetentionPolicy.CRITICAL_LOGS] = RetentionConfig(
            policy=RetentionPolicy.CRITICAL_LOGS,
            retention_days=maritime_retention_days,
            compression_level=CompressionLevel.MAXIMUM,
            archive_after_days=30,
            cost_optimization=False
        )
        
        configs[RetentionPolicy.AUDIT_LOGS] = RetentionConfig(
            policy=RetentionPolicy.AUDIT_LOGS,
            retention_days=maritime_retention_days,
            compression_level=CompressionLevel.MAXIMUM,
            archive_after_days=7,  # Archive audit logs quickly
            cost_optimization=False
        )
        
        configs[RetentionPolicy.MARITIME_LOGS] = RetentionConfig(
            policy=RetentionPolicy.MARITIME_LOGS,
            retention_days=maritime_retention_days,
            compression_level=CompressionLevel.MAXIMUM,
            archive_after_days=30,
            cost_optimization=False
        )
        
        configs[RetentionPolicy.SECURITY_LOGS] = RetentionConfig(
            policy=RetentionPolicy.SECURITY_LOGS,
            retention_days=maritime_retention_days,
            compression_level=CompressionLevel.MAXIMUM,
            archive_after_days=1,  # Archive security logs immediately
            cost_optimization=False
        )
        
        configs[RetentionPolicy.COMPLIANCE_LOGS] = RetentionConfig(
            policy=RetentionPolicy.COMPLIANCE_LOGS,
            retention_days=maritime_retention_days,
            compression_level=CompressionLevel.MAXIMUM,
            archive_after_days=1,
            cost_optimization=False
        )
        
        return configs
    
    def start_background_cleanup(self):
        """Start background cleanup process"""
        if self.is_active:
            return
        
        self.is_active = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        self.logger.info(
            "Log retention cleanup started",
            component=ComponentType.AUDIT_SYSTEM.value,
            cleanup_interval_hours=self.cleanup_interval / 3600
        )
    
    def stop_background_cleanup(self):
        """Stop background cleanup process"""
        self.is_active = False
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=30)
    
    def _cleanup_loop(self):
        """Background cleanup loop"""
        while self.is_active:
            try:
                # Run cleanup
                self.cleanup_logs()
                
                # Check storage limits
                if self.aggressive_cleanup:
                    self._enforce_storage_limits()
                
                # Update stats
                self.stats['last_cleanup'] = datetime.now(timezone.utc)
                
                # Sleep until next cleanup
                time.sleep(self.cleanup_interval)
                
            except Exception as e:
                self.logger.error(
                    "Error in log retention cleanup loop",
                    component=ComponentType.AUDIT_SYSTEM.value,
                    exception=e
                )
                time.sleep(300)  # Wait 5 minutes before retry
    
    def cleanup_logs(self):
        """Perform log cleanup based on retention policies"""
        try:
            total_files_processed = 0
            total_bytes_saved = 0
            
            for log_file in self.base_path.glob("*.log*"):
                if not log_file.is_file():
                    continue
                
                # Determine retention policy for this file
                policy = self._determine_retention_policy(log_file)
                config = self.retention_configs.get(policy)
                
                if not config:
                    continue
                
                file_age_days = self._get_file_age_days(log_file)
                
                # Archive if old enough
                if file_age_days >= config.archive_after_days and not self._is_archived(log_file):
                    bytes_saved = self._archive_file(log_file, config)
                    if bytes_saved > 0:
                        total_bytes_saved += bytes_saved
                        total_files_processed += 1
                
                # Delete if beyond retention period
                elif file_age_days >= config.delete_after_days:
                    self._delete_file(log_file)
                    total_files_processed += 1
            
            # Clean up old archive files
            self._cleanup_old_archives()
            
            # Update statistics
            self.stats['files_archived'] += total_files_processed
            self.stats['storage_saved_bytes'] += total_bytes_saved
            
            if total_files_processed > 0:
                self.logger.info(
                    "Log cleanup completed",
                    component=ComponentType.AUDIT_SYSTEM.value,
                    files_processed=total_files_processed,
                    bytes_saved=total_bytes_saved,
                    storage_saved_mb=total_bytes_saved / (1024 * 1024)
                )
            
        except Exception as e:
            self.logger.error(
                "Error during log cleanup",
                component=ComponentType.AUDIT_SYSTEM.value,
                exception=e
            )
    
    def _determine_retention_policy(self, log_file: Path) -> RetentionPolicy:
        """Determine retention policy for a log file"""
        file_name = log_file.name.lower()
        
        # Maritime and compliance logs get special treatment
        if any(keyword in file_name for keyword in ['maritime', 'vessel', 'cargo', 'port']):
            return RetentionPolicy.MARITIME_LOGS
        
        if 'audit' in file_name:
            return RetentionPolicy.AUDIT_LOGS
        
        if 'security' in file_name:
            return RetentionPolicy.SECURITY_LOGS
        
        if 'compliance' in file_name:
            return RetentionPolicy.COMPLIANCE_LOGS
        
        # Check log level based on file content or naming
        if 'critical' in file_name or 'emergency' in file_name:
            return RetentionPolicy.CRITICAL_LOGS
        elif 'error' in file_name:
            return RetentionPolicy.ERROR_LOGS
        elif 'warning' in file_name or 'warn' in file_name:
            return RetentionPolicy.WARNING_LOGS
        elif 'debug' in file_name:
            return RetentionPolicy.DEBUG_LOGS
        else:
            return RetentionPolicy.INFO_LOGS
    
    def _get_file_age_days(self, log_file: Path) -> float:
        """Get age of file in days"""
        try:
            file_mtime = log_file.stat().st_mtime
            age_seconds = time.time() - file_mtime
            return age_seconds / (24 * 3600)  # Convert to days
        except OSError:
            return 0
    
    def _is_archived(self, log_file: Path) -> bool:
        """Check if file is already archived"""
        archive_file = self.archive_path / f"{log_file.stem}.tar.gz"
        return archive_file.exists()
    
    def _archive_file(self, log_file: Path, config: RetentionConfig) -> int:
        """Archive a log file with compression"""
        try:
            if not self.compression_enabled:
                return 0
            
            original_size = log_file.stat().st_size
            archive_name = f"{log_file.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tar.gz"
            archive_path = self.archive_path / archive_name
            
            # Create compressed archive
            with tarfile.open(archive_path, 'w:gz', compresslevel=config.compression_level.value) as tar:
                tar.add(log_file, arcname=log_file.name)
            
            # Verify archive integrity
            if self._verify_archive(archive_path, log_file):
                # Calculate compression ratio
                compressed_size = archive_path.stat().st_size
                compression_ratio = 1 - (compressed_size / original_size)
                bytes_saved = original_size - compressed_size
                
                # Update stats
                self.stats['bytes_compressed'] += original_size
                self.stats['compression_ratio'] = (
                    (self.stats['compression_ratio'] * self.stats['files_archived'] + compression_ratio) /
                    (self.stats['files_archived'] + 1)
                )
                
                # Remove original file
                log_file.unlink()
                
                self.logger.info(
                    "Log file archived",
                    component=ComponentType.AUDIT_SYSTEM.value,
                    original_file=str(log_file),
                    archive_file=str(archive_path),
                    original_size_mb=original_size / (1024 * 1024),
                    compressed_size_mb=compressed_size / (1024 * 1024),
                    compression_ratio=compression_ratio * 100,
                    bytes_saved=bytes_saved
                )
                
                return bytes_saved
            else:
                # Archive verification failed, remove bad archive
                archive_path.unlink()
                self.logger.error(
                    "Archive verification failed",
                    component=ComponentType.AUDIT_SYSTEM.value,
                    log_file=str(log_file),
                    archive_file=str(archive_path)
                )
                return 0
                
        except Exception as e:
            self.logger.error(
                "Failed to archive log file",
                component=ComponentType.AUDIT_SYSTEM.value,
                log_file=str(log_file),
                exception=e
            )
            return 0
    
    def _verify_archive(self, archive_path: Path, original_file: Path) -> bool:
        """Verify archive integrity"""
        try:
            with tarfile.open(archive_path, 'r:gz') as tar:
                # Check if archive can be opened and contains expected file
                members = tar.getnames()
                return original_file.name in members
        except Exception:
            return False
    
    def _delete_file(self, log_file: Path):
        """Delete a log file"""
        try:
            file_size = log_file.stat().st_size
            log_file.unlink()
            
            self.stats['files_deleted'] += 1
            
            self.logger.info(
                "Log file deleted (retention expired)",
                component=ComponentType.AUDIT_SYSTEM.value,
                log_file=str(log_file),
                file_size_mb=file_size / (1024 * 1024)
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to delete log file",
                component=ComponentType.AUDIT_SYSTEM.value,
                log_file=str(log_file),
                exception=e
            )
    
    def _cleanup_old_archives(self):
        """Clean up old archive files based on retention policies"""
        try:
            for archive_file in self.archive_path.glob("*.tar.gz"):
                # Extract date from filename
                file_age_days = self._get_file_age_days(archive_file)
                
                # Determine if archive should be deleted
                # Use maximum retention period for archives
                max_retention = max(config.retention_days for config in self.retention_configs.values())
                
                if file_age_days > max_retention:
                    archive_file.unlink()
                    self.logger.info(
                        "Archive file deleted (retention expired)",
                        component=ComponentType.AUDIT_SYSTEM.value,
                        archive_file=str(archive_file),
                        age_days=file_age_days
                    )
        
        except Exception as e:
            self.logger.error(
                "Error cleaning up old archives",
                component=ComponentType.AUDIT_SYSTEM.value,
                exception=e
            )
    
    def _enforce_storage_limits(self):
        """Enforce storage limits by removing oldest non-critical logs"""
        try:
            current_usage = self._calculate_storage_usage()
            current_usage_mb = current_usage / (1024 * 1024)
            
            if current_usage_mb <= self.max_storage_mb:
                return
            
            self.logger.warning(
                "Storage limit exceeded, enforcing cleanup",
                component=ComponentType.AUDIT_SYSTEM.value,
                current_usage_mb=current_usage_mb,
                limit_mb=self.max_storage_mb
            )
            
            # Get all log files sorted by age (oldest first)
            log_files = []
            for log_file in self.base_path.glob("*.log*"):
                if log_file.is_file():
                    policy = self._determine_retention_policy(log_file)
                    # Skip critical logs from aggressive cleanup
                    if policy not in [RetentionPolicy.AUDIT_LOGS, RetentionPolicy.SECURITY_LOGS,
                                     RetentionPolicy.COMPLIANCE_LOGS, RetentionPolicy.MARITIME_LOGS]:
                        age_days = self._get_file_age_days(log_file)
                        log_files.append((log_file, age_days, policy))
            
            # Sort by age (oldest first)
            log_files.sort(key=lambda x: x[1], reverse=True)
            
            # Remove files until under limit
            bytes_removed = 0
            files_removed = 0
            
            for log_file, age_days, policy in log_files:
                if current_usage_mb <= self.max_storage_mb:
                    break
                
                file_size = log_file.stat().st_size
                
                # Archive if possible, otherwise delete
                config = self.retention_configs.get(policy)
                if config and age_days >= 1:  # Archive files older than 1 day
                    saved_bytes = self._archive_file(log_file, config)
                    if saved_bytes > 0:
                        bytes_removed += saved_bytes
                        files_removed += 1
                        current_usage_mb -= file_size / (1024 * 1024)
                elif age_days >= 0.5:  # Delete files older than 12 hours
                    self._delete_file(log_file)
                    bytes_removed += file_size
                    files_removed += 1
                    current_usage_mb -= file_size / (1024 * 1024)
            
            if files_removed > 0:
                self.logger.info(
                    "Storage limit enforcement completed",
                    component=ComponentType.AUDIT_SYSTEM.value,
                    files_removed=files_removed,
                    bytes_removed=bytes_removed,
                    final_usage_mb=current_usage_mb
                )
        
        except Exception as e:
            self.logger.error(
                "Error enforcing storage limits",
                component=ComponentType.AUDIT_SYSTEM.value,
                exception=e
            )
    
    def _calculate_storage_usage(self) -> int:
        """Calculate total storage usage in bytes"""
        total_size = 0
        
        try:
            # Calculate log files
            for log_file in self.base_path.glob("*.log*"):
                if log_file.is_file():
                    total_size += log_file.stat().st_size
            
            # Calculate archive files
            for archive_file in self.archive_path.glob("*.tar.gz"):
                if archive_file.is_file():
                    total_size += archive_file.stat().st_size
        
        except Exception as e:
            self.logger.error(
                "Error calculating storage usage",
                component=ComponentType.AUDIT_SYSTEM.value,
                exception=e
            )
        
        return total_size
    
    def get_storage_statistics(self) -> Dict[str, Any]:
        """Get storage and retention statistics"""
        current_usage_bytes = self._calculate_storage_usage()
        current_usage_mb = current_usage_bytes / (1024 * 1024)
        
        # Count files by type
        file_counts = defaultdict(int)
        file_sizes = defaultdict(int)
        
        for log_file in self.base_path.glob("*.log*"):
            if log_file.is_file():
                policy = self._determine_retention_policy(log_file)
                file_counts[policy.value] += 1
                file_sizes[policy.value] += log_file.stat().st_size
        
        # Count archives
        archive_count = len(list(self.archive_path.glob("*.tar.gz")))
        archive_size = sum(f.stat().st_size for f in self.archive_path.glob("*.tar.gz") if f.is_file())
        
        return {
            'current_usage_mb': current_usage_mb,
            'max_storage_mb': self.max_storage_mb,
            'usage_percentage': (current_usage_mb / self.max_storage_mb) * 100,
            'total_log_files': sum(file_counts.values()),
            'total_archive_files': archive_count,
            'log_files_by_type': dict(file_counts),
            'log_sizes_by_type_mb': {k: v / (1024 * 1024) for k, v in file_sizes.items()},
            'archive_size_mb': archive_size / (1024 * 1024),
            'compression_enabled': self.compression_enabled,
            'avg_compression_ratio': self.stats['compression_ratio'] * 100,
            'total_files_archived': self.stats['files_archived'],
            'total_files_deleted': self.stats['files_deleted'],
            'total_bytes_compressed': self.stats['bytes_compressed'],
            'storage_saved_mb': self.stats['storage_saved_bytes'] / (1024 * 1024),
            'last_cleanup': self.stats['last_cleanup'].isoformat() if self.stats['last_cleanup'] else None,
            'retention_policies': {
                policy.value: {
                    'retention_days': config.retention_days,
                    'archive_after_days': config.archive_after_days,
                    'compression_level': config.compression_level.value,
                    'cost_optimization': config.cost_optimization
                }
                for policy, config in self.retention_configs.items()
            }
        }
    
    def manual_cleanup(self, force_cleanup: bool = False) -> Dict[str, Any]:
        """Perform manual cleanup and return results"""
        start_time = time.time()
        initial_usage = self._calculate_storage_usage()
        
        # Perform cleanup
        if force_cleanup:
            # Temporarily enable aggressive cleanup
            original_aggressive = self.aggressive_cleanup
            self.aggressive_cleanup = True
            
            self.cleanup_logs()
            self._enforce_storage_limits()
            
            self.aggressive_cleanup = original_aggressive
        else:
            self.cleanup_logs()
        
        final_usage = self._calculate_storage_usage()
        cleanup_time = time.time() - start_time
        
        return {
            'cleanup_duration_seconds': cleanup_time,
            'initial_usage_mb': initial_usage / (1024 * 1024),
            'final_usage_mb': final_usage / (1024 * 1024),
            'space_freed_mb': (initial_usage - final_usage) / (1024 * 1024),
            'force_cleanup_used': force_cleanup,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def restore_from_archive(self, archive_name: str, restore_path: Optional[Path] = None) -> bool:
        """Restore logs from archive"""
        try:
            archive_path = self.archive_path / archive_name
            
            if not archive_path.exists():
                self.logger.error(
                    "Archive file not found",
                    component=ComponentType.AUDIT_SYSTEM.value,
                    archive_name=archive_name
                )
                return False
            
            restore_location = restore_path or self.base_path
            
            with tarfile.open(archive_path, 'r:gz') as tar:
                tar.extractall(restore_location)
            
            self.logger.info(
                "Archive restored successfully",
                component=ComponentType.AUDIT_SYSTEM.value,
                archive_name=archive_name,
                restore_path=str(restore_location)
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to restore from archive",
                component=ComponentType.AUDIT_SYSTEM.value,
                archive_name=archive_name,
                exception=e
            )
            return False
    
    def list_archives(self) -> List[Dict[str, Any]]:
        """List all available archives"""
        archives = []
        
        try:
            for archive_file in self.archive_path.glob("*.tar.gz"):
                if archive_file.is_file():
                    stat = archive_file.stat()
                    archives.append({
                        'name': archive_file.name,
                        'size_mb': stat.st_size / (1024 * 1024),
                        'created_date': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        'age_days': (time.time() - stat.st_mtime) / (24 * 3600)
                    })
            
            # Sort by creation date (newest first)
            archives.sort(key=lambda x: x['created_date'], reverse=True)
            
        except Exception as e:
            self.logger.error(
                "Error listing archives",
                component=ComponentType.AUDIT_SYSTEM.value,
                exception=e
            )
        
        return archives


# Global retention manager instance
_log_retention_manager: Optional[LogRetentionManager] = None


def init_log_retention_manager(base_path: str = "/tmp/logs") -> LogRetentionManager:
    """Initialize the global log retention manager"""
    global _log_retention_manager
    
    if _log_retention_manager is None:
        _log_retention_manager = LogRetentionManager(base_path)
        
        # Start background cleanup if enabled
        if os.getenv('LOG_CLEANUP_ENABLED', 'true').lower() == 'true':
            _log_retention_manager.start_background_cleanup()
    
    return _log_retention_manager


def get_log_retention_manager() -> Optional[LogRetentionManager]:
    """Get the global log retention manager instance"""
    return _log_retention_manager


def configure_log_retention(app):
    """Configure Flask app with log retention"""
    # Initialize retention manager
    log_path = app.config.get('LOG_PATH', '/tmp/logs')
    retention_manager = init_log_retention_manager(log_path)
    
    # Add cleanup route for admin interface
    @app.route('/api/admin/logs/cleanup', methods=['POST'])
    def manual_log_cleanup():
        try:
            force = request.json.get('force', False) if request.json else False
            result = retention_manager.manual_cleanup(force_cleanup=force)
            return jsonify({'success': True, 'result': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/admin/logs/stats', methods=['GET'])
    def log_storage_stats():
        try:
            stats = retention_manager.get_storage_statistics()
            return jsonify({'success': True, 'stats': stats})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/admin/logs/archives', methods=['GET'])
    def list_log_archives():
        try:
            archives = retention_manager.list_archives()
            return jsonify({'success': True, 'archives': archives})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return retention_manager


# Export public interface
__all__ = [
    'RetentionPolicy', 'CompressionLevel', 'StorageLocation', 'RetentionConfig',
    'LogRetentionManager', 'init_log_retention_manager', 'get_log_retention_manager',
    'configure_log_retention'
]