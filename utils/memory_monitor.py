"""
Memory Monitoring and Optimization Module for Stevedores Dashboard 3.0
Prevents memory overflow and provides real-time monitoring
Optimized for 512MB container limits in production maritime operations
"""

import psutil
import gc
import logging
import threading
import time
import os
import signal
import resource
from typing import Dict, Any, List, Optional, Callable
from collections import deque
from datetime import datetime, timedelta
from functools import wraps

logger = logging.getLogger(__name__)

# Memory optimization constants for 512MB containers
DEFAULT_CONTAINER_LIMIT_MB = 512
MEMORY_SAFETY_BUFFER_MB = 64  # Reserve 64MB for system operations
AGGRESSIVE_GC_THRESHOLD = 80  # Trigger aggressive cleanup at 80%
CRITICAL_MEMORY_THRESHOLD = 90  # Critical threshold at 90%
WARNING_MEMORY_THRESHOLD = 75  # Warning threshold at 75%
EMERGENCY_SHUTDOWN_THRESHOLD = 95  # Emergency shutdown at 95%

class MemoryMonitor:
    """Production memory monitoring and management for 512MB containers"""
    
    def __init__(self, warning_threshold=WARNING_MEMORY_THRESHOLD, 
                 critical_threshold=CRITICAL_MEMORY_THRESHOLD, 
                 check_interval=15):  # More frequent checks for containers
        self.warning_threshold = warning_threshold  # Percentage
        self.critical_threshold = critical_threshold  # Percentage
        self.emergency_threshold = EMERGENCY_SHUTDOWN_THRESHOLD
        self.check_interval = check_interval  # Seconds
        
        self.memory_history = deque(maxlen=200)  # More history for better trending
        self.alert_history = deque(maxlen=50)  # Track alert frequency
        self.is_monitoring = False
        self.monitor_thread = None
        self._stop_event = threading.Event()
        
        # Container-aware memory limit detection
        self.memory_limit = self._get_container_memory_limit()
        self.available_memory = self.memory_limit - (MEMORY_SAFETY_BUFFER_MB * 1024 * 1024)
        
        # Performance optimization settings
        self.gc_frequency = 0  # Track GC frequency
        self.last_cleanup = time.time()
        self.cleanup_callbacks: List[Callable] = []
        
        # Alert cooldown to prevent spam
        self.last_alert_time = 0
        self.alert_cooldown = 60  # 60 seconds between similar alerts
        
        logger.info(f"Memory monitor initialized - Container limit: {self.memory_limit / (1024**2):.0f}MB, "
                   f"Available: {self.available_memory / (1024**2):.0f}MB, "
                   f"Warning: {self.warning_threshold}%, Critical: {self.critical_threshold}%")
    
    def _get_container_memory_limit(self) -> int:
        """Get container memory limit with improved detection"""
        try:
            # Try cgroup v2 first (modern containers)
            cgroup_paths = [
                '/sys/fs/cgroup/memory.max',
                '/sys/fs/cgroup/memory/memory.limit_in_bytes',
                '/sys/fs/cgroup/memory.limit_in_bytes'
            ]
            
            for path in cgroup_paths:
                try:
                    with open(path, 'r') as f:
                        content = f.read().strip()
                        if content != 'max' and content.isdigit():
                            limit = int(content)
                            if limit < (1 << 62):  # Valid limit (not max value)
                                logger.info(f"Container memory limit detected: {limit / (1024**2):.0f}MB from {path}")
                                return limit
                except (FileNotFoundError, ValueError, PermissionError):
                    continue
            
            # Check environment variables (common in container platforms)
            env_limit = os.environ.get('MEMORY_LIMIT_MB')
            if env_limit and env_limit.isdigit():
                limit = int(env_limit) * 1024 * 1024
                logger.info(f"Container memory limit from ENV: {limit / (1024**2):.0f}MB")
                return limit
            
        except Exception as e:
            logger.warning(f"Failed to detect container memory limit: {e}")
        
        # Fallback to system memory or default container size
        system_memory = psutil.virtual_memory().total
        default_container = DEFAULT_CONTAINER_LIMIT_MB * 1024 * 1024
        
        # If system memory is much larger than typical container, assume containerized
        if system_memory > (2 * 1024**3):  # > 2GB suggests container
            logger.info(f"Assuming containerized environment, using default: {DEFAULT_CONTAINER_LIMIT_MB}MB")
            return default_container
        else:
            logger.info(f"Using system memory: {system_memory / (1024**2):.0f}MB")
            return system_memory

    def register_cleanup_callback(self, callback: Callable) -> None:
        """Register callback for memory cleanup events"""
        self.cleanup_callbacks.append(callback)
        logger.debug(f"Registered cleanup callback: {callback.__name__}")

    def calculate_optimal_workers(self) -> int:
        """Calculate optimal worker count based on available memory"""
        # Reserve memory for system and base application
        base_memory_mb = 128  # Base Flask app memory
        memory_per_worker_mb = 48  # Estimated memory per worker
        
        available_mb = (self.available_memory / (1024**2))
        max_workers = max(1, int((available_mb - base_memory_mb) / memory_per_worker_mb))
        
        # Cap at reasonable limits for containers
        max_workers = min(max_workers, 6)  # Max 6 workers for 512MB container
        
        logger.info(f"Calculated optimal workers: {max_workers} (Available: {available_mb:.0f}MB)")
        return max_workers
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get comprehensive memory usage statistics for containers"""
        try:
            # Process memory information
            process = psutil.Process()
            process_memory = process.memory_info()
            
            # System memory
            system_memory = psutil.virtual_memory()
            
            # Container memory calculations
            container_used = process_memory.rss
            container_percent = (container_used / self.memory_limit) * 100
            available_percent = (self.available_memory / self.memory_limit) * 100
            
            # Memory pressure indicators
            pressure_score = self._calculate_memory_pressure()
            
            # Garbage collection statistics
            gc_stats = gc.get_stats()
            
            usage = {
                "timestamp": datetime.now().isoformat(),
                "container": {
                    "limit_mb": round(self.memory_limit / (1024**2), 2),
                    "available_mb": round(self.available_memory / (1024**2), 2),
                    "used_mb": round(container_used / (1024**2), 2),
                    "free_mb": round((self.memory_limit - container_used) / (1024**2), 2),
                    "percent": round(container_percent, 2),
                    "available_percent": round(available_percent, 2),
                    "pressure_score": pressure_score
                },
                "process": {
                    "rss_mb": round(process_memory.rss / (1024**2), 2),
                    "vms_mb": round(process_memory.vms / (1024**2), 2),
                    "shared_mb": round(getattr(process_memory, 'shared', 0) / (1024**2), 2),
                    "text_mb": round(getattr(process_memory, 'text', 0) / (1024**2), 2),
                    "data_mb": round(getattr(process_memory, 'data', 0) / (1024**2), 2),
                    "percent": round(process.memory_percent(), 2),
                    "threads": process.num_threads(),
                    "fds": getattr(process, 'num_fds', lambda: 0)()
                },
                "system": {
                    "total_gb": round(system_memory.total / (1024**3), 2),
                    "used_gb": round(system_memory.used / (1024**3), 2),
                    "available_gb": round(system_memory.available / (1024**3), 2),
                    "percent": system_memory.percent,
                    "swap_used_mb": round(psutil.swap_memory().used / (1024**2), 2),
                    "swap_percent": psutil.swap_memory().percent
                },
                "gc": {
                    "stats": gc_stats,
                    "objects": len(gc.get_objects()),
                    "frequency": self.gc_frequency,
                    "last_cleanup": round(time.time() - self.last_cleanup, 2),
                    "generations": {i: gc.get_count()[i] for i in range(3)}
                },
                "thresholds": {
                    "warning": self.warning_threshold,
                    "critical": self.critical_threshold,
                    "emergency": self.emergency_threshold
                },
                "status": self._get_memory_status(container_percent)
            }
            
            return usage
            
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return {
                "error": str(e), 
                "timestamp": datetime.now().isoformat(),
                "status": "error"
            }

    def _calculate_memory_pressure(self) -> float:
        """Calculate memory pressure score (0-100)"""
        try:
            process = psutil.Process()
            rss = process.memory_info().rss
            pressure = (rss / self.available_memory) * 100
            return min(100.0, max(0.0, pressure))
        except:
            return 0.0

    def _get_memory_status(self, container_percent: float) -> str:
        """Get memory status based on thresholds"""
        if container_percent >= self.emergency_threshold:
            return "emergency"
        elif container_percent >= self.critical_threshold:
            return "critical"
        elif container_percent >= self.warning_threshold:
            return "warning"
        else:
            return "healthy"
    
    def start_monitoring(self):
        """Start background memory monitoring"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self._stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Memory monitoring started")
    
    def stop_monitoring(self):
        """Stop background memory monitoring"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        self._stop_event.set()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        logger.info("Memory monitoring stopped")
    
    def _monitor_loop(self):
        """Enhanced background monitoring loop for production containers"""
        logger.info("Memory monitoring loop started")
        consecutive_highs = 0
        
        while not self._stop_event.wait(self.check_interval):
            try:
                usage = self.get_memory_usage()
                container_percent = usage.get("container", {}).get("percent", 0)
                memory_status = usage.get("status", "unknown")
                pressure_score = usage.get("container", {}).get("pressure_score", 0)
                
                # Store in history
                history_entry = {
                    "timestamp": usage["timestamp"],
                    "container_percent": container_percent,
                    "process_mb": usage.get("process", {}).get("rss_mb", 0),
                    "pressure_score": pressure_score,
                    "status": memory_status,
                    "gc_objects": usage.get("gc", {}).get("objects", 0),
                    "threads": usage.get("process", {}).get("threads", 0)
                }
                self.memory_history.append(history_entry)
                
                # Track consecutive high memory usage
                if container_percent >= self.warning_threshold:
                    consecutive_highs += 1
                else:
                    consecutive_highs = 0
                
                # Handle memory pressure based on severity
                if container_percent >= self.emergency_threshold:
                    self._handle_emergency_memory(usage)
                elif container_percent >= self.critical_threshold:
                    self._handle_critical_memory(usage, consecutive_highs)
                elif container_percent >= self.warning_threshold:
                    self._handle_warning_memory(usage, consecutive_highs)
                elif container_percent >= AGGRESSIVE_GC_THRESHOLD:
                    self._handle_aggressive_cleanup(usage)
                
                # Periodic maintenance cleanup
                if time.time() - self.last_cleanup > 300:  # Every 5 minutes
                    self._periodic_maintenance()
                
            except Exception as e:
                logger.error(f"Memory monitoring error: {e}")
                consecutive_highs = 0  # Reset on error
    
    def _handle_warning_memory(self, usage: Dict[str, Any], consecutive_highs: int = 0):
        """Handle memory warning threshold breach"""
        container_percent = usage.get("container", {}).get("percent", 0)
        pressure_score = usage.get("container", {}).get("pressure_score", 0)
        
        # Rate limit alerts to prevent spam
        current_time = time.time()
        if current_time - self.last_alert_time < self.alert_cooldown:
            return
        
        logger.warning(f"Memory usage high: {container_percent:.1f}% (Warning: {self.warning_threshold}%, "
                      f"Pressure: {pressure_score:.1f}, Consecutive: {consecutive_highs})")
        
        # Record alert
        self.alert_history.append({
            "timestamp": usage["timestamp"],
            "level": "warning",
            "percent": container_percent,
            "pressure": pressure_score,
            "consecutive": consecutive_highs
        })
        
        # Progressive cleanup based on consecutive highs
        if consecutive_highs > 3:
            self._aggressive_cleanup(usage)
        else:
            self._gentle_cleanup()
        
        self.last_alert_time = current_time
    
    def _handle_critical_memory(self, usage: Dict[str, Any], consecutive_highs: int = 0):
        """Handle critical memory threshold breach"""
        container_percent = usage.get("container", {}).get("percent", 0)
        pressure_score = usage.get("container", {}).get("pressure_score", 0)
        
        logger.critical(f"CRITICAL MEMORY: {container_percent:.1f}% (Critical: {self.critical_threshold}%, "
                       f"Pressure: {pressure_score:.1f}, Consecutive: {consecutive_highs})")
        
        # Record critical alert
        self.alert_history.append({
            "timestamp": usage["timestamp"],
            "level": "critical",
            "percent": container_percent,
            "pressure": pressure_score,
            "consecutive": consecutive_highs
        })
        
        # Force aggressive cleanup
        self.force_memory_cleanup()
        
        # Execute registered cleanup callbacks
        for callback in self.cleanup_callbacks:
            try:
                callback()
                logger.info(f"Executed cleanup callback: {callback.__name__}")
            except Exception as e:
                logger.error(f"Cleanup callback {callback.__name__} failed: {e}")
        
        # Log detailed memory breakdown for debugging
        logger.critical(f"Critical memory details: "
                       f"RSS: {usage.get('process', {}).get('rss_mb', 0):.1f}MB, "
                       f"Objects: {usage.get('gc', {}).get('objects', 0)}, "
                       f"Threads: {usage.get('process', {}).get('threads', 0)}")

    def _handle_emergency_memory(self, usage: Dict[str, Any]):
        """Handle emergency memory threshold - last resort before OOM"""
        container_percent = usage.get("container", {}).get("percent", 0)
        
        logger.critical(f"EMERGENCY MEMORY SITUATION: {container_percent:.1f}% "
                       f"(Emergency: {self.emergency_threshold}%) - TAKING DRASTIC ACTION")
        
        # Record emergency alert
        self.alert_history.append({
            "timestamp": usage["timestamp"],
            "level": "emergency",
            "percent": container_percent,
            "action": "emergency_cleanup"
        })
        
        # Emergency cleanup sequence
        try:
            # 1. Force immediate garbage collection (all generations)
            for i in range(3):
                collected = gc.collect()
                logger.critical(f"Emergency GC pass {i+1}: {collected} objects collected")
            
            # 2. Execute all cleanup callbacks immediately
            for callback in self.cleanup_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Emergency cleanup callback failed: {e}")
            
            # 3. Clear internal caches
            self._clear_internal_caches()
            
            # 4. If still critical after cleanup, consider worker restart
            post_cleanup_usage = self.get_memory_usage()
            post_cleanup_percent = post_cleanup_usage.get("container", {}).get("percent", 0)
            
            if post_cleanup_percent >= self.critical_threshold:
                logger.critical(f"Emergency cleanup insufficient: {post_cleanup_percent:.1f}% remaining")
                self._signal_worker_restart()
            else:
                logger.info(f"Emergency cleanup successful: {post_cleanup_percent:.1f}% remaining")
                
        except Exception as e:
            logger.critical(f"Emergency memory cleanup failed: {e}")
            self._signal_worker_restart()

    def _handle_aggressive_cleanup(self, usage: Dict[str, Any]):
        """Handle aggressive cleanup at 80% threshold"""
        container_percent = usage.get("container", {}).get("percent", 0)
        
        logger.info(f"Aggressive cleanup triggered: {container_percent:.1f}%")
        self._aggressive_cleanup(usage)
    
    def force_memory_cleanup(self):
        """Force aggressive memory cleanup"""
        start_time = time.time()
        try:
            logger.info("Starting force memory cleanup")
            
            # Get initial memory state
            initial_usage = self.get_memory_usage()
            initial_mb = initial_usage.get("process", {}).get("rss_mb", 0)
            
            # Multiple garbage collection passes with different strategies
            collected_total = 0
            
            # Pass 1: Standard collection
            collected = gc.collect()
            collected_total += collected
            logger.info(f"GC pass 1 (standard): {collected} objects collected")
            
            # Pass 2: Force collection of all generations
            for gen in range(3):
                collected = gc.collect(gen)
                collected_total += collected
                logger.info(f"GC pass 2.{gen} (generation {gen}): {collected} objects collected")
            
            # Pass 3: Final sweep
            collected = gc.collect()
            collected_total += collected
            logger.info(f"GC pass 3 (final): {collected} objects collected")
            
            # Update cleanup tracking
            self.gc_frequency += 1
            self.last_cleanup = time.time()
            
            # Measure effectiveness
            final_usage = self.get_memory_usage()
            final_mb = final_usage.get("process", {}).get("rss_mb", 0)
            freed_mb = initial_mb - final_mb
            
            cleanup_time = (time.time() - start_time) * 1000
            
            logger.info(f"Force cleanup completed: {collected_total} objects collected, "
                       f"{freed_mb:.1f}MB freed, {cleanup_time:.0f}ms duration")
            
        except Exception as e:
            logger.error(f"Error during force memory cleanup: {e}")

    def _gentle_cleanup(self):
        """Gentle cleanup for warning threshold"""
        try:
            collected = gc.collect()
            self.gc_frequency += 1
            logger.info(f"Gentle cleanup: {collected} objects collected")
        except Exception as e:
            logger.error(f"Gentle cleanup failed: {e}")

    def _aggressive_cleanup(self, usage: Dict[str, Any]):
        """Aggressive cleanup for high memory pressure"""
        try:
            logger.info("Starting aggressive cleanup")
            
            # Force multiple GC passes
            total_collected = 0
            for i in range(2):
                collected = gc.collect()
                total_collected += collected
            
            # Execute cleanup callbacks
            for callback in self.cleanup_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.warning(f"Aggressive cleanup callback failed: {e}")
            
            self.gc_frequency += 1
            self.last_cleanup = time.time()
            
            logger.info(f"Aggressive cleanup completed: {total_collected} objects collected")
            
        except Exception as e:
            logger.error(f"Aggressive cleanup failed: {e}")

    def _periodic_maintenance(self):
        """Periodic maintenance cleanup"""
        try:
            logger.debug("Running periodic maintenance cleanup")
            collected = gc.collect()
            self.last_cleanup = time.time()
            logger.debug(f"Periodic maintenance: {collected} objects collected")
        except Exception as e:
            logger.error(f"Periodic maintenance failed: {e}")

    def _clear_internal_caches(self):
        """Clear internal monitoring caches in emergency"""
        try:
            # Keep only recent history
            if len(self.memory_history) > 50:
                self.memory_history = deque(list(self.memory_history)[-50:], maxlen=200)
            
            # Keep only recent alerts
            if len(self.alert_history) > 20:
                self.alert_history = deque(list(self.alert_history)[-20:], maxlen=50)
            
            logger.info("Internal caches cleared")
        except Exception as e:
            logger.error(f"Failed to clear internal caches: {e}")

    def _signal_worker_restart(self):
        """Signal worker restart due to memory pressure"""
        try:
            logger.critical("Signaling worker restart due to memory pressure")
            
            # Try graceful restart first (if in Gunicorn)
            if hasattr(os, 'getppid') and os.getppid() != 1:
                # Send SIGUSR2 to parent process (Gunicorn master) for graceful worker restart
                os.kill(os.getppid(), signal.SIGUSR2)
                logger.critical("Sent SIGUSR2 to parent process for worker restart")
            else:
                # Fallback: exit current process
                logger.critical("Exiting worker process due to memory emergency")
                os._exit(1)
                
        except Exception as e:
            logger.critical(f"Failed to signal worker restart: {e}")
            # Last resort: force exit
            os._exit(1)
    
    def get_memory_trend(self, minutes: int = 10) -> Dict[str, Any]:
        """Get memory usage trend over specified minutes"""
        if not self.memory_history:
            return {"error": "No memory history available"}
        
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        recent_data = [
            entry for entry in self.memory_history
            if datetime.fromisoformat(entry["timestamp"]) > cutoff_time
        ]
        
        if not recent_data:
            return {"error": f"No data in last {minutes} minutes"}
        
        # Calculate trend
        percentages = [entry["container_percent"] for entry in recent_data]
        memory_mbs = [entry["process_mb"] for entry in recent_data]
        
        return {
            "period_minutes": minutes,
            "readings_count": len(recent_data),
            "memory_percent": {
                "min": min(percentages),
                "max": max(percentages),
                "avg": sum(percentages) / len(percentages),
                "current": percentages[-1]
            },
            "memory_mb": {
                "min": min(memory_mbs),
                "max": max(memory_mbs),
                "avg": sum(memory_mbs) / len(memory_mbs),
                "current": memory_mbs[-1]
            },
            "trend": "increasing" if percentages[-1] > percentages[0] else "decreasing"
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive memory health status for health check endpoint"""
        usage = self.get_memory_usage()
        container_percent = usage.get("container", {}).get("percent", 0)
        pressure_score = usage.get("container", {}).get("pressure_score", 0)
        
        # Determine status
        status = usage.get("status", "unknown")
        
        # Get recent alert frequency
        recent_alerts = len([alert for alert in self.alert_history 
                           if datetime.fromisoformat(alert["timestamp"]) > 
                           datetime.now() - timedelta(hours=1)])
        
        return {
            "status": status,
            "memory_usage_percent": round(container_percent, 2),
            "pressure_score": round(pressure_score, 2),
            "memory_limit_mb": round(self.memory_limit / (1024**2), 2),
            "available_memory_mb": round(self.available_memory / (1024**2), 2),
            "thresholds": {
                "warning": self.warning_threshold,
                "critical": self.critical_threshold,
                "emergency": self.emergency_threshold
            },
            "monitoring": {
                "active": self.is_monitoring,
                "check_interval": self.check_interval,
                "history_entries": len(self.memory_history)
            },
            "gc": {
                "objects": len(gc.get_objects()),
                "frequency": self.gc_frequency,
                "last_cleanup_ago": round(time.time() - self.last_cleanup, 1)
            },
            "alerts": {
                "recent_count": recent_alerts,
                "total_alerts": len(self.alert_history),
                "last_alert_ago": round(time.time() - self.last_alert_time, 1) if self.last_alert_time else None
            },
            "optimization": {
                "optimal_workers": self.calculate_optimal_workers(),
                "cleanup_callbacks": len(self.cleanup_callbacks)
            }
        }

    def get_memory_report(self) -> Dict[str, Any]:
        """Get comprehensive memory usage report"""
        usage = self.get_memory_usage()
        trend = self.get_memory_trend(30)  # 30-minute trend
        
        # Analyze alert patterns
        alert_analysis = self._analyze_alert_patterns()
        
        # Performance metrics
        avg_gc_frequency = self.gc_frequency / max(1, len(self.memory_history))
        
        return {
            "summary": {
                "current_status": usage.get("status", "unknown"),
                "container_usage": usage.get("container", {}),
                "process_info": usage.get("process", {}),
                "system_info": usage.get("system", {})
            },
            "trends": trend,
            "alerts": {
                "analysis": alert_analysis,
                "recent_history": list(self.alert_history)[-10:]  # Last 10 alerts
            },
            "performance": {
                "gc_frequency": self.gc_frequency,
                "avg_gc_per_reading": round(avg_gc_frequency, 3),
                "monitoring_uptime": round(time.time() - (self.memory_history[0]["timestamp"] if self.memory_history else time.time()), 1)
            },
            "recommendations": self._get_memory_recommendations(usage)
        }

    def _analyze_alert_patterns(self) -> Dict[str, Any]:
        """Analyze alert patterns for insights"""
        if not self.alert_history:
            return {"status": "no_alerts", "message": "No alerts recorded"}
        
        # Count by level
        alert_counts = {}
        recent_alerts = []
        
        for alert in self.alert_history:
            level = alert.get("level", "unknown")
            alert_counts[level] = alert_counts.get(level, 0) + 1
            
            # Recent alerts (last hour)
            if datetime.fromisoformat(alert["timestamp"]) > datetime.now() - timedelta(hours=1):
                recent_alerts.append(alert)
        
        return {
            "total_alerts": len(self.alert_history),
            "by_level": alert_counts,
            "recent_alerts": len(recent_alerts),
            "pattern_analysis": "escalating" if len(recent_alerts) > 3 else "stable"
        }

    def _get_memory_recommendations(self, usage: Dict[str, Any]) -> List[str]:
        """Get memory optimization recommendations"""
        recommendations = []
        container_percent = usage.get("container", {}).get("percent", 0)
        gc_objects = usage.get("gc", {}).get("objects", 0)
        
        if container_percent > 85:
            recommendations.append("Consider increasing container memory limit")
            recommendations.append("Review application for memory leaks")
        
        if container_percent > 75:
            recommendations.append("Implement more aggressive caching cleanup")
            recommendations.append("Consider reducing worker count")
        
        if gc_objects > 100000:
            recommendations.append("High object count detected - review object lifecycle")
        
        if len(self.alert_history) > 20:
            recommendations.append("Frequent memory alerts - investigate root cause")
        
        if not recommendations:
            recommendations.append("Memory usage is healthy")
        
        return recommendations

# Decorator for memory-aware request handling
def memory_limit(threshold_percent: float = 90):
    """Decorator to reject requests when memory usage is high"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            monitor = get_memory_monitor()
            if monitor:
                usage = monitor.get_memory_usage()
                current_percent = usage.get("container", {}).get("percent", 0)
                
                if current_percent > threshold_percent:
                    from flask import jsonify
                    logger.warning(f"Request rejected due to high memory usage: {current_percent:.1f}%")
                    return jsonify({
                        "error": "Service temporarily unavailable due to high memory usage",
                        "memory_percent": current_percent,
                        "retry_after": 30
                    }), 503
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Global memory monitor instance
_memory_monitor: Optional[MemoryMonitor] = None

def init_memory_monitor(warning_threshold=WARNING_MEMORY_THRESHOLD, 
                       critical_threshold=CRITICAL_MEMORY_THRESHOLD) -> MemoryMonitor:
    """Initialize enhanced global memory monitor for production containers"""
    global _memory_monitor
    
    if _memory_monitor is None:
        _memory_monitor = MemoryMonitor(
            warning_threshold=warning_threshold, 
            critical_threshold=critical_threshold,
            check_interval=15  # More frequent monitoring for containers
        )
        _memory_monitor.start_monitoring()
        
        # Register default cleanup callbacks
        _register_default_cleanup_callbacks(_memory_monitor)
        
        logger.info(f"Enhanced memory monitor initialized for {_memory_monitor.memory_limit / (1024**2):.0f}MB container")
    
    return _memory_monitor

def _register_default_cleanup_callbacks(monitor: MemoryMonitor):
    """Register default cleanup callbacks for common Flask components"""
    try:
        # Flask-SQLAlchemy connection pool cleanup
        def cleanup_db_connections():
            try:
                from flask import current_app
                if hasattr(current_app, 'extensions') and 'sqlalchemy' in current_app.extensions:
                    db = current_app.extensions['sqlalchemy'].db
                    db.engine.pool.dispose()
                    logger.info("Database connection pool disposed")
            except Exception as e:
                logger.warning(f"DB cleanup failed: {e}")
        
        # Redis connection cleanup
        def cleanup_redis_connections():
            try:
                from utils.redis_client import cleanup_redis_connections
                cleanup_redis_connections()
                logger.info("Redis connections cleaned up")
            except Exception as e:
                logger.warning(f"Redis cleanup failed: {e}")
        
        monitor.register_cleanup_callback(cleanup_db_connections)
        monitor.register_cleanup_callback(cleanup_redis_connections)
        
        logger.info("Default cleanup callbacks registered")
        
    except Exception as e:
        logger.warning(f"Failed to register default cleanup callbacks: {e}")

def get_memory_monitor() -> Optional[MemoryMonitor]:
    """Get global memory monitor instance"""
    return _memory_monitor

def memory_health_check() -> Dict[str, Any]:
    """Health check for memory monitoring"""
    monitor = get_memory_monitor()
    if monitor:
        return monitor.get_health_status()
    else:
        return {"status": "not_initialized", "monitoring_active": False}