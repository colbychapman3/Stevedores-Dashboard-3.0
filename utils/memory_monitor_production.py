"""
Production memory monitoring and optimization system.
Prevents out-of-memory crashes for Stevedores Dashboard 3.0.
"""

import os
import gc
import psutil
import threading
import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class MemoryStats:
    total_mb: float
    used_mb: float
    used_percent: float
    available_mb: float
    threshold_status: str
    timestamp: datetime

class ProductionMemoryMonitor:
    """Production memory monitoring system."""
    
    def __init__(self, memory_limit_mb: Optional[int] = None):
        self.memory_limit_mb = memory_limit_mb or self._detect_container_memory()
        self.warning_threshold = 0.75
        self.critical_threshold = 0.85
        self.emergency_threshold = 0.95
        
        self.process = psutil.Process()
        self.monitoring = False
        self.monitor_thread = None
        
        logger.info(f"Production memory monitor initialized: {self.memory_limit_mb}MB limit")
    
    def _detect_container_memory(self) -> int:
        """Detect container memory limit."""
        # Check environment
        env_limit = os.getenv('MEMORY_LIMIT_MB')
        if env_limit:
            try:
                return int(env_limit)
            except ValueError:
                pass
        
        # Try cgroup detection
        try:
            with open('/sys/fs/cgroup/memory/memory.limit_in_bytes', 'r') as f:
                limit_bytes = int(f.read().strip())
                limit_mb = limit_bytes // (1024 * 1024)
                # Cap at system memory
                system_mb = psutil.virtual_memory().total // (1024 * 1024)
                return min(limit_mb, system_mb)
        except (FileNotFoundError, ValueError, PermissionError):
            pass
        
        # Default for production containers
        return 512
    
    def get_current_stats(self) -> MemoryStats:
        """Get current memory statistics."""
        process_info = self.process.memory_info()
        used_mb = process_info.rss / (1024 * 1024)
        used_percent = (used_mb / self.memory_limit_mb) * 100
        
        if used_percent >= self.emergency_threshold * 100:
            status = 'emergency'
        elif used_percent >= self.critical_threshold * 100:
            status = 'critical'
        elif used_percent >= self.warning_threshold * 100:
            status = 'warning'
        else:
            status = 'normal'
        
        return MemoryStats(
            total_mb=self.memory_limit_mb,
            used_mb=used_mb,
            used_percent=used_percent,
            available_mb=self.memory_limit_mb - used_mb,
            threshold_status=status,
            timestamp=datetime.now()
        )
    
    def start_monitoring(self, interval: int = 30):
        """Start memory monitoring."""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop, 
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
        logger.info(f"Memory monitoring started (interval: {interval}s)")
    
    def _monitor_loop(self, interval: int):
        """Main monitoring loop."""
        while self.monitoring:
            try:
                stats = self.get_current_stats()
                
                if stats.threshold_status in ['critical', 'emergency']:
                    self._trigger_cleanup(stats)
                    logger.warning(f"Memory {stats.threshold_status}: {stats.used_percent:.1f}%")
                
            except Exception as e:
                logger.error(f"Memory monitoring error: {e}")
            
            time.sleep(interval)
    
    def _trigger_cleanup(self, stats: MemoryStats):
        """Trigger memory cleanup."""
        logger.info(f"Triggering memory cleanup: {stats.used_percent:.1f}%")
        
        # Force garbage collection
        collected = gc.collect()
        logger.info(f"Garbage collection freed {collected} objects")
        
        # Clear caches if available
        try:
            from flask import current_app
            if hasattr(current_app, 'cache'):
                current_app.cache.clear()
        except:
            pass
    
    def get_memory_report(self) -> Dict[str, Any]:
        """Get memory report."""
        stats = self.get_current_stats()
        return {
            'memory_usage_mb': round(stats.used_mb, 1),
            'memory_usage_percent': round(stats.used_percent, 1),
            'memory_limit_mb': stats.total_mb,
            'available_mb': round(stats.available_mb, 1),
            'status': stats.threshold_status,
            'thresholds': {
                'warning': f"{self.warning_threshold * 100}%",
                'critical': f"{self.critical_threshold * 100}%",
                'emergency': f"{self.emergency_threshold * 100}%"
            }
        }

def calculate_optimal_workers(memory_limit_mb: int = 512) -> int:
    """Calculate optimal Gunicorn workers."""
    # Reserve memory for OS
    reserved_mb = 128
    available_mb = memory_limit_mb - reserved_mb
    
    # Estimate 64MB per worker
    worker_memory_mb = 64
    max_workers = available_mb // worker_memory_mb
    
    # CPU-based limit
    cpu_count = os.cpu_count() or 1
    cpu_limit = (cpu_count * 2) + 1
    
    # Apply safety limits
    optimal_workers = min(max_workers, cpu_limit, 8)
    optimal_workers = max(1, optimal_workers)
    
    logger.info(f"Calculated optimal workers: {optimal_workers} "
                f"(Memory: {memory_limit_mb}MB, CPU: {cpu_count})")
    
    return optimal_workers

# Global instance
production_memory_monitor = ProductionMemoryMonitor()

def memory_health_check() -> Dict[str, Any]:
    """Memory health check."""
    try:
        stats = production_memory_monitor.get_current_stats()
        
        return {
            'status': 'healthy' if stats.threshold_status in ['normal', 'warning'] else 'unhealthy',
            'memory_usage_mb': round(stats.used_mb, 1),
            'memory_usage_percent': round(stats.used_percent, 1),
            'memory_limit_mb': stats.total_mb,
            'threshold_status': stats.threshold_status
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'memory_usage_mb': 0,
            'memory_usage_percent': 0
        }

def start_production_monitoring():
    """Start production memory monitoring."""
    if not production_memory_monitor.monitoring:
        production_memory_monitor.start_monitoring()
        logger.info("Production memory monitoring started")