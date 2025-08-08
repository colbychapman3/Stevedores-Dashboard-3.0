"""
Performance Monitoring System for Stevedores Dashboard 3.0
Real-time monitoring of memory, response times, and system health
"""

import time
import psutil
import threading
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from flask import g, request, current_app
import json
import os

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Real-time performance monitoring with alerts and metrics collection"""
    
    def __init__(self, app=None):
        # Metrics storage (in-memory with size limits)
        self.metrics = {
            'response_times': deque(maxlen=1000),      # Last 1000 requests
            'memory_usage': deque(maxlen=288),          # 24 hours at 5min intervals
            'cpu_usage': deque(maxlen=288),             # 24 hours at 5min intervals
            'database_connections': deque(maxlen=100),   # Last 100 measurements
            'redis_connections': deque(maxlen=100),      # Last 100 measurements
            'active_requests': deque(maxlen=500),        # Active request tracking
            'error_rates': deque(maxlen=100),            # Error tracking
            'slow_queries': deque(maxlen=50)             # Slow query tracking
        }
        
        # Performance thresholds
        self.thresholds = {
            'memory_warning': 350,    # MB
            'memory_critical': 400,   # MB
            'response_warning': 200,  # ms
            'response_critical': 500, # ms
            'cpu_warning': 70,        # %
            'cpu_critical': 85,       # %
            'error_rate_warning': 1,  # %
            'error_rate_critical': 5  # %
        }
        
        # Monitoring state
        self.start_time = time.time()
        self.monitoring_active = False
        self.alert_cooldown = {}  # Prevent alert spam
        self.last_alert_times = {}
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize performance monitoring with Flask app"""
        # Register Flask request hooks
        app.before_request(self._before_request)
        app.after_request(self._after_request)
        app.teardown_appcontext(self._teardown_request)
        
        # Start background monitoring
        self._start_background_monitoring()
        
        # Register shutdown handler
        import atexit
        atexit.register(self._shutdown_monitoring)
        
        app.logger.info("✅ Performance monitoring initialized")
    
    def _before_request(self):
        """Track request start time and active requests"""
        g.request_start_time = time.time()
        g.request_id = f"{time.time()}_{id(request)}"
        
        # Track active request
        self.metrics['active_requests'].append({
            'id': g.request_id,
            'start_time': g.request_start_time,
            'endpoint': request.endpoint or 'unknown',
            'method': request.method,
            'remote_addr': request.remote_addr
        })
    
    def _after_request(self, response):
        """Track request completion and response times"""
        if hasattr(g, 'request_start_time'):
            response_time = (time.time() - g.request_start_time) * 1000  # Convert to ms
            
            # Store response time
            self.metrics['response_times'].append({
                'time': response_time,
                'status_code': response.status_code,
                'endpoint': request.endpoint or 'unknown',
                'timestamp': time.time()
            })
            
            # Check for slow responses
            if response_time > self.thresholds['response_warning']:
                self._log_slow_request(response_time, request.endpoint, response.status_code)
            
            # Track errors
            if response.status_code >= 400:
                self._track_error(response.status_code, request.endpoint)
        
        return response
    
    def _teardown_request(self, exception):
        """Clean up request tracking"""
        if hasattr(g, 'request_id'):
            # Remove from active requests
            self.metrics['active_requests'] = deque(
                [req for req in self.metrics['active_requests'] 
                 if req['id'] != g.request_id],
                maxlen=500
            )
    
    def _start_background_monitoring(self):
        """Start background system monitoring thread"""
        if not self.monitoring_active:
            self.monitoring_active = True
            monitor_thread = threading.Thread(
                target=self._system_monitor_loop, 
                daemon=True, 
                name="performance-monitor"
            )
            monitor_thread.start()
            logger.info("Background performance monitoring started")
    
    def _system_monitor_loop(self):
        """Main system monitoring loop"""
        while self.monitoring_active:
            try:
                self._collect_system_metrics()
                self._check_thresholds_and_alert()
                time.sleep(300)  # Monitor every 5 minutes
                
            except Exception as e:
                logger.error(f"System monitoring error: {e}")
                time.sleep(60)  # Fallback interval on error
    
    def _collect_system_metrics(self):
        """Collect system-level metrics"""
        try:
            # Memory usage
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            self.metrics['memory_usage'].append({
                'value': memory_mb,
                'timestamp': time.time()
            })
            
            # CPU usage
            cpu_percent = process.cpu_percent(interval=1)
            self.metrics['cpu_usage'].append({
                'value': cpu_percent,
                'timestamp': time.time()
            })
            
            # Database connections (if available)
            try:
                from app import db
                active_connections = db.session.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
                ).scalar()
                
                self.metrics['database_connections'].append({
                    'value': active_connections,
                    'timestamp': time.time()
                })
            except:
                pass  # Database not available or query failed
            
            # Redis connections (if available)
            try:
                from utils.redis_manager import get_redis_manager
                redis_manager = get_redis_manager()
                if redis_manager:
                    stats = redis_manager.get_connection_stats()
                    if 'connected_clients' in stats:
                        self.metrics['redis_connections'].append({
                            'value': stats['connected_clients'],
                            'timestamp': time.time()
                        })
            except:
                pass  # Redis not available
                
        except Exception as e:
            logger.warning(f"Failed to collect system metrics: {e}")
    
    def _check_thresholds_and_alert(self):
        """Check performance thresholds and generate alerts"""
        current_time = time.time()
        
        # Check memory usage
        if self.metrics['memory_usage']:
            current_memory = self.metrics['memory_usage'][-1]['value']
            
            if current_memory > self.thresholds['memory_critical']:
                self._send_alert('memory_critical', 
                               f"Critical memory usage: {current_memory:.1f}MB")
            elif current_memory > self.thresholds['memory_warning']:
                self._send_alert('memory_warning', 
                               f"High memory usage: {current_memory:.1f}MB")
        
        # Check response times
        if self.metrics['response_times']:
            recent_responses = [
                r for r in self.metrics['response_times'] 
                if current_time - r['timestamp'] < 300  # Last 5 minutes
            ]
            
            if recent_responses:
                avg_response_time = sum(r['time'] for r in recent_responses) / len(recent_responses)
                
                if avg_response_time > self.thresholds['response_critical']:
                    self._send_alert('response_critical', 
                                   f"Critical response time: {avg_response_time:.1f}ms")
                elif avg_response_time > self.thresholds['response_warning']:
                    self._send_alert('response_warning', 
                                   f"Slow response time: {avg_response_time:.1f}ms")
        
        # Check CPU usage
        if self.metrics['cpu_usage']:
            current_cpu = self.metrics['cpu_usage'][-1]['value']
            
            if current_cpu > self.thresholds['cpu_critical']:
                self._send_alert('cpu_critical', f"Critical CPU usage: {current_cpu:.1f}%")
            elif current_cpu > self.thresholds['cpu_warning']:
                self._send_alert('cpu_warning', f"High CPU usage: {current_cpu:.1f}%")
    
    def _send_alert(self, alert_type: str, message: str):
        """Send performance alert with cooldown to prevent spam"""
        current_time = time.time()
        cooldown_period = 300  # 5 minutes
        
        # Check cooldown
        if alert_type in self.last_alert_times:
            if current_time - self.last_alert_times[alert_type] < cooldown_period:
                return  # Still in cooldown
        
        # Send alert
        logger.warning(f"🚨 PERFORMANCE ALERT [{alert_type.upper()}]: {message}")
        
        # Update cooldown
        self.last_alert_times[alert_type] = current_time
        
        # Store alert in metrics for dashboard
        if 'alerts' not in self.metrics:
            self.metrics['alerts'] = deque(maxlen=100)
        
        self.metrics['alerts'].append({
            'type': alert_type,
            'message': message,
            'timestamp': current_time
        })
    
    def _log_slow_request(self, response_time: float, endpoint: str, status_code: int):
        """Log slow request for analysis"""
        self.metrics['slow_queries'].append({
            'response_time': response_time,
            'endpoint': endpoint,
            'status_code': status_code,
            'timestamp': time.time()
        })
        
        if response_time > self.thresholds['response_critical']:
            logger.warning(
                f"🐌 SLOW REQUEST: {endpoint} took {response_time:.1f}ms "
                f"(status: {status_code})"
            )
    
    def _track_error(self, status_code: int, endpoint: str):
        """Track error for rate calculation"""
        self.metrics['error_rates'].append({
            'status_code': status_code,
            'endpoint': endpoint,
            'timestamp': time.time()
        })
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics for dashboard/API"""
        current_time = time.time()
        
        # Calculate response time statistics
        response_stats = {}
        if self.metrics['response_times']:
            times = [r['time'] for r in self.metrics['response_times']]
            response_stats = {
                'avg': sum(times) / len(times),
                'min': min(times),
                'max': max(times),
                'count': len(times)
            }
        
        # Calculate memory statistics
        memory_stats = {}
        if self.metrics['memory_usage']:
            current_memory = self.metrics['memory_usage'][-1]['value']
            memory_values = [m['value'] for m in self.metrics['memory_usage']]
            memory_stats = {
                'current': current_memory,
                'avg': sum(memory_values) / len(memory_values),
                'max': max(memory_values)
            }
        
        # Calculate error rate
        error_rate = 0
        if self.metrics['error_rates'] and self.metrics['response_times']:
            recent_errors = len([
                e for e in self.metrics['error_rates']
                if current_time - e['timestamp'] < 3600  # Last hour
            ])
            recent_requests = len([
                r for r in self.metrics['response_times']
                if current_time - r['timestamp'] < 3600  # Last hour
            ])
            
            if recent_requests > 0:
                error_rate = (recent_errors / recent_requests) * 100
        
        return {
            'uptime': current_time - self.start_time,
            'response_time': response_stats,
            'memory': memory_stats,
            'error_rate': error_rate,
            'active_requests': len(self.metrics['active_requests']),
            'total_requests': len(self.metrics['response_times']),
            'slow_requests': len([
                r for r in self.metrics['response_times']
                if r['time'] > self.thresholds['response_warning']
            ]),
            'alerts_count': len(self.metrics.get('alerts', [])),
            'timestamp': current_time
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status"""
        metrics = self.get_current_metrics()
        
        # Determine health status
        critical_issues = []
        warnings = []
        
        # Check memory
        if 'memory' in metrics and metrics['memory']:
            current_memory = metrics['memory']['current']
            if current_memory > self.thresholds['memory_critical']:
                critical_issues.append(f"Memory usage critical: {current_memory:.1f}MB")
            elif current_memory > self.thresholds['memory_warning']:
                warnings.append(f"Memory usage high: {current_memory:.1f}MB")
        
        # Check response times
        if 'response_time' in metrics and metrics['response_time']:
            avg_response = metrics['response_time']['avg']
            if avg_response > self.thresholds['response_critical']:
                critical_issues.append(f"Response time critical: {avg_response:.1f}ms")
            elif avg_response > self.thresholds['response_warning']:
                warnings.append(f"Response time slow: {avg_response:.1f}ms")
        
        # Check error rate
        if metrics['error_rate'] > self.thresholds['error_rate_critical']:
            critical_issues.append(f"Error rate critical: {metrics['error_rate']:.1f}%")
        elif metrics['error_rate'] > self.thresholds['error_rate_warning']:
            warnings.append(f"Error rate high: {metrics['error_rate']:.1f}%")
        
        # Determine overall status
        if critical_issues:
            status = 'critical'
        elif warnings:
            status = 'warning'
        else:
            status = 'healthy'
        
        return {
            'status': status,
            'critical_issues': critical_issues,
            'warnings': warnings,
            'metrics': metrics,
            'thresholds': self.thresholds
        }
    
    def _shutdown_monitoring(self):
        """Shutdown background monitoring"""
        self.monitoring_active = False
        logger.info("Performance monitoring shutdown")

# Global performance monitor instance
performance_monitor = None

def get_performance_monitor() -> Optional[PerformanceMonitor]:
    """Get global performance monitor instance"""
    return performance_monitor

def init_performance_monitor(app) -> PerformanceMonitor:
    """Initialize global performance monitor"""
    global performance_monitor
    performance_monitor = PerformanceMonitor(app)
    return performance_monitor