"""
Production Monitoring and Alerting System for Stevedores Dashboard 3.0
Enhanced with memory monitoring integration for 512MB container environments
Real-time monitoring of critical production metrics with maritime-specific alerting
"""

import logging
import time
import json
import threading
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from collections import deque, defaultdict
import psutil

logger = logging.getLogger(__name__)

class MetricCollector:
    """Collects and aggregates production metrics"""
    
    def __init__(self, max_history=1000):
        self.max_history = max_history
        self.metrics_history = defaultdict(lambda: deque(maxlen=max_history))
        self.alerts = deque(maxlen=100)  # Last 100 alerts
        self.lock = threading.Lock()
        
        # Enhanced thresholds for container environments
        self.thresholds = {
            'memory_percent': {'warning': 75, 'critical': 85, 'emergency': 95},
            'memory_pressure': {'warning': 70, 'critical': 85, 'emergency': 95},
            'cpu_percent': {'warning': 80, 'critical': 90},
            'disk_percent': {'warning': 85, 'critical': 95},
            'response_time_ms': {'warning': 1000, 'critical': 3000},
            'error_rate_percent': {'warning': 5, 'critical': 10},
            'gc_frequency': {'warning': 10, 'critical': 20},
            'worker_memory_mb': {'warning': 200, 'critical': 300},
            'request_memory_leak_mb': {'warning': 10, 'critical': 25}
        }
        
        # Memory monitoring integration
        self.memory_monitor = None
        self.memory_callbacks: List[Callable] = []
        
        # Alert cooldowns to prevent spam
        self.alert_cooldowns = defaultdict(float)
        self.cooldown_duration = 300  # 5 minutes
    
    def collect_metric(self, name: str, value: float, timestamp: Optional[float] = None):
        """Collect a single metric"""
        if timestamp is None:
            timestamp = time.time()
        
        with self.lock:
            self.metrics_history[name].append({
                'timestamp': timestamp,
                'value': value,
                'datetime': datetime.fromtimestamp(timestamp).isoformat()
            })
        
        # Check thresholds and generate alerts
        self._check_thresholds(name, value, timestamp)
    
    def _check_thresholds(self, metric_name: str, value: float, timestamp: float):
        """Check if metric exceeds thresholds and generate alerts with cooldown"""
        if metric_name not in self.thresholds:
            return
        
        thresholds = self.thresholds[metric_name]
        
        # Check cooldown to prevent alert spam
        cooldown_key = f"{metric_name}_{value >= thresholds.get('critical', float('inf'))}"
        current_time = time.time()
        
        if current_time - self.alert_cooldowns[cooldown_key] < self.cooldown_duration:
            return  # Still in cooldown
        
        # Check emergency threshold first (if exists)
        if 'emergency' in thresholds and value >= thresholds['emergency']:
            self._generate_alert(metric_name, value, 'emergency', timestamp)
            self.alert_cooldowns[cooldown_key] = current_time
        elif value >= thresholds['critical']:
            self._generate_alert(metric_name, value, 'critical', timestamp)
            self.alert_cooldowns[cooldown_key] = current_time
        elif value >= thresholds['warning']:
            self._generate_alert(metric_name, value, 'warning', timestamp)
            # Shorter cooldown for warnings
            if current_time - self.alert_cooldowns[cooldown_key] > 60:  # 1 minute for warnings
                self.alert_cooldowns[cooldown_key] = current_time
    
    def _generate_alert(self, metric_name: str, value: float, level: str, timestamp: float):
        """Generate an alert with enhanced maritime context"""
        alert = {
            'timestamp': timestamp,
            'datetime': datetime.fromtimestamp(timestamp).isoformat(),
            'metric': metric_name,
            'value': value,
            'level': level,
            'threshold': self.thresholds[metric_name][level],
            'message': f"{metric_name} {level}: {value:.2f} (threshold: {self.thresholds[metric_name][level]})",
            'context': self._get_alert_context(metric_name, value, level)
        }
        
        with self.lock:
            self.alerts.append(alert)
        
        # Enhanced logging with maritime operations context
        log_func = getattr(logger, level.lower(), logger.warning)
        maritime_emoji = "⚓" if metric_name.startswith('memory') else "🚨"
        log_func(f"{maritime_emoji} MARITIME ALERT: {alert['message']} - {alert['context']}")
        
        # Execute memory-specific callbacks
        if metric_name.startswith('memory') and self.memory_callbacks:
            for callback in self.memory_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.error(f"Memory alert callback failed: {e}")

    def _get_alert_context(self, metric_name: str, value: float, level: str) -> str:
        """Get maritime operations context for alerts"""
        if metric_name.startswith('memory'):
            if level == 'emergency':
                return "CRITICAL MARITIME OPERATION IMPACT - Consider immediate action"
            elif level == 'critical':
                return "High impact on vessel operations - Memory optimization required"
            else:
                return "Monitor maritime operations performance"
        elif metric_name == 'cpu_percent':
            return "Vessel processing performance affected"
        elif metric_name == 'disk_percent':
            return "Maritime document storage capacity concerns"
        else:
            return "Maritime operations monitoring alert"

    def register_memory_monitor(self, memory_monitor):
        """Register memory monitor for integration"""
        self.memory_monitor = memory_monitor
        
        # Register as cleanup callback
        if hasattr(memory_monitor, 'register_cleanup_callback'):
            memory_monitor.register_cleanup_callback(self._memory_cleanup_callback)
        
        logger.info("Memory monitor integrated with production monitoring")

    def _memory_cleanup_callback(self):
        """Callback for memory cleanup events"""
        try:
            # Collect current memory stats after cleanup
            if self.memory_monitor:
                usage = self.memory_monitor.get_memory_usage()
                
                # Collect memory metrics
                container_percent = usage.get("container", {}).get("percent", 0)
                pressure_score = usage.get("container", {}).get("pressure_score", 0)
                gc_objects = usage.get("gc", {}).get("objects", 0)
                
                self.collect_metric("memory_percent", container_percent)
                self.collect_metric("memory_pressure", pressure_score)
                self.collect_metric("gc_objects", gc_objects)
                
                logger.info(f"Post-cleanup metrics collected: {container_percent:.1f}% memory, "
                           f"{pressure_score:.1f} pressure, {gc_objects} objects")
        except Exception as e:
            logger.error(f"Memory cleanup callback error: {e}")

    def collect_memory_metrics(self):
        """Collect comprehensive memory metrics from monitor"""
        try:
            if not self.memory_monitor:
                return
            
            usage = self.memory_monitor.get_memory_usage()
            timestamp = time.time()
            
            # Core memory metrics
            container_percent = usage.get("container", {}).get("percent", 0)
            pressure_score = usage.get("container", {}).get("pressure_score", 0)
            process_rss = usage.get("process", {}).get("rss_mb", 0)
            
            # GC and optimization metrics
            gc_objects = usage.get("gc", {}).get("objects", 0)
            gc_frequency = usage.get("gc", {}).get("frequency", 0)
            
            # System context
            system_percent = usage.get("system", {}).get("percent", 0)
            swap_percent = usage.get("system", {}).get("swap_percent", 0)
            
            # Collect all metrics
            self.collect_metric("memory_percent", container_percent, timestamp)
            self.collect_metric("memory_pressure", pressure_score, timestamp)
            self.collect_metric("worker_memory_mb", process_rss, timestamp)
            self.collect_metric("gc_objects", gc_objects, timestamp)
            self.collect_metric("gc_frequency", gc_frequency, timestamp)
            self.collect_metric("system_memory_percent", system_percent, timestamp)
            self.collect_metric("swap_percent", swap_percent, timestamp)
            
            # Collect memory trend data
            trend = self.memory_monitor.get_memory_trend(5)  # 5-minute trend
            if 'error' not in trend:
                memory_trend = trend.get("memory_percent", {}).get("avg", 0)
                self.collect_metric("memory_trend_5min", memory_trend, timestamp)
            
        except Exception as e:
            logger.error(f"Failed to collect memory metrics: {e}")

    def register_memory_callback(self, callback: Callable):
        """Register callback for memory-related alerts"""
        self.memory_callbacks.append(callback)
        logger.debug(f"Memory callback registered: {callback.__name__}")

    def get_memory_alert_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get summary of memory-related alerts"""
        cutoff_time = time.time() - (hours * 3600)
        memory_alerts = []
        
        with self.lock:
            for alert in self.alerts:
                if (alert['timestamp'] > cutoff_time and 
                    alert['metric'].startswith('memory')):
                    memory_alerts.append(alert)
        
        # Analyze alert patterns
        alert_counts = defaultdict(int)
        for alert in memory_alerts:
            alert_counts[alert['level']] += 1
        
        return {
            "total_memory_alerts": len(memory_alerts),
            "by_level": dict(alert_counts),
            "recent_alerts": memory_alerts[-5:],  # Last 5
            "alert_frequency": len(memory_alerts) / max(1, hours),
            "time_range_hours": hours
        }
    
    def get_metrics_summary(self, minutes: int = 10) -> Dict[str, Any]:
        """Get metrics summary for the last N minutes"""
        cutoff_time = time.time() - (minutes * 60)
        summary = {}
        
        with self.lock:
            for metric_name, history in self.metrics_history.items():
                recent_values = [
                    entry['value'] for entry in history
                    if entry['timestamp'] > cutoff_time
                ]
                
                if recent_values:
                    summary[metric_name] = {
                        'count': len(recent_values),
                        'min': min(recent_values),
                        'max': max(recent_values),
                        'avg': sum(recent_values) / len(recent_values),
                        'latest': recent_values[-1]
                    }
        
        return summary
    
    def get_recent_alerts(self, minutes: int = 60) -> List[Dict[str, Any]]:
        """Get alerts from the last N minutes"""
        cutoff_time = time.time() - (minutes * 60)
        
        with self.lock:
            return [
                alert for alert in self.alerts
                if alert['timestamp'] > cutoff_time
            ]

class ProductionMonitor:
    """Main production monitoring system"""
    
    def __init__(self):
        self.metric_collector = MetricCollector()
        self.is_monitoring = False
        self.monitor_thread = None
        self.collection_interval = 30  # Collect metrics every 30 seconds
        self._stop_event = threading.Event()
        
        # Counters
        self.request_count = 0
        self.error_count = 0
        self.response_times = deque(maxlen=100)
    
    def start_monitoring(self):
        """Start the monitoring system"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self._stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("🔍 Production monitoring started")
    
    def stop_monitoring(self):
        """Stop the monitoring system"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        self._stop_event.set()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        logger.info("🛑 Production monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while not self._stop_event.wait(self.collection_interval):
            try:
                self._collect_system_metrics()
                self._collect_application_metrics()
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
    
    def _collect_system_metrics(self):
        """Collect system-level metrics"""
        now = time.time()
        
        try:
            # Memory usage
            memory = psutil.virtual_memory()
            self.metric_collector.collect_metric('memory_percent', memory.percent, now)
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            self.metric_collector.collect_metric('cpu_percent', cpu_percent, now)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self.metric_collector.collect_metric('disk_percent', disk_percent, now)
            
            # Load average (if available)
            try:
                load_avg = psutil.getloadavg()
                self.metric_collector.collect_metric('load_avg_1min', load_avg[0], now)
                self.metric_collector.collect_metric('load_avg_5min', load_avg[1], now)
            except:
                pass
            
        except Exception as e:
            logger.error(f"System metrics collection error: {e}")
    
    def _collect_application_metrics(self):
        """Collect application-level metrics"""
        now = time.time()
        
        try:
            # Calculate error rate
            if self.request_count > 0:
                error_rate = (self.error_count / self.request_count) * 100
                self.metric_collector.collect_metric('error_rate_percent', error_rate, now)
            
            # Average response time
            if self.response_times:
                avg_response_time = sum(self.response_times) / len(self.response_times)
                self.metric_collector.collect_metric('response_time_ms', avg_response_time, now)
            
            # Request rate (requests per minute)
            requests_per_minute = self.request_count / max(1, self.collection_interval / 60)
            self.metric_collector.collect_metric('requests_per_minute', requests_per_minute, now)
            
            # Reset counters for next interval
            self.request_count = 0
            self.error_count = 0
            
        except Exception as e:
            logger.error(f"Application metrics collection error: {e}")
    
    def record_request(self, response_time_ms: float, status_code: int):
        """Record a request for metrics"""
        self.request_count += 1
        self.response_times.append(response_time_ms)
        
        if status_code >= 400:
            self.error_count += 1
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get monitoring data for dashboard"""
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'metrics_summary': self.metric_collector.get_metrics_summary(10),
            'recent_alerts': self.metric_collector.get_recent_alerts(60),
            'alert_counts': {
                'critical': len([a for a in self.metric_collector.get_recent_alerts(60) if a['level'] == 'critical']),
                'warning': len([a for a in self.metric_collector.get_recent_alerts(60) if a['level'] == 'warning'])
            },
            'monitoring_status': {
                'active': self.is_monitoring,
                'collection_interval': self.collection_interval,
                'uptime_seconds': time.time() - getattr(self, 'start_time', time.time())
            }
        }
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get health report for monitoring systems"""
        recent_alerts = self.metric_collector.get_recent_alerts(60)
        critical_alerts = [a for a in recent_alerts if a['level'] == 'critical']
        
        status = 'healthy'
        if critical_alerts:
            status = 'critical'
        elif recent_alerts:
            status = 'warning'
        
        return {
            'status': status,
            'active_monitoring': self.is_monitoring,
            'recent_alerts_count': len(recent_alerts),
            'critical_alerts_count': len(critical_alerts),
            'metrics_collected': len(self.metric_collector.metrics_history),
            'last_collection': datetime.utcnow().isoformat()
        }

# Global monitoring instance
_production_monitor: Optional[ProductionMonitor] = None

def init_production_monitor() -> ProductionMonitor:
    """Initialize the global production monitor"""
    global _production_monitor
    
    if _production_monitor is None:
        _production_monitor = ProductionMonitor()
        _production_monitor.start_time = time.time()
        _production_monitor.start_monitoring()
    
    return _production_monitor

def get_production_monitor() -> Optional[ProductionMonitor]:
    """Get the global production monitor instance"""
    return _production_monitor

def monitoring_middleware(app):
    """Flask middleware to record request metrics"""
    @app.before_request
    def before_request():
        if hasattr(g, 'request_start_time'):
            return
        g.request_start_time = time.time()
    
    @app.after_request
    def after_request(response):
        if not hasattr(g, 'request_start_time'):
            return response
        
        response_time_ms = (time.time() - g.request_start_time) * 1000
        
        monitor = get_production_monitor()
        if monitor:
            monitor.record_request(response_time_ms, response.status_code)
        
        return response
    
    return app