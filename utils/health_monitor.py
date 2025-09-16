"""
Comprehensive Health Check Monitor
Validates all production dependencies and system health
"""

import time
import logging
from datetime import datetime
from typing import Dict, Any, List
from flask import current_app
import psutil

logger = logging.getLogger(__name__)

class HealthMonitor:
    """Production health monitoring with dependency validation"""
    
    def __init__(self):
        self.checks = {}
        self.last_check_time = 0
        self.cache_ttl = 30  # Cache results for 30 seconds
        self.cached_result = None
    
    def register_check(self, name: str, check_func, critical: bool = True):
        """Register a health check function"""
        self.checks[name] = {
            'func': check_func,
            'critical': critical,
            'last_result': None,
            'last_check': 0
        }
    
    def run_all_checks(self, use_cache: bool = True) -> Dict[str, Any]:
        """Run all registered health checks"""
        now = time.time()
        
        # Use cache if recent and requested
        if (use_cache and self.cached_result and 
            (now - self.last_check_time) < self.cache_ttl):
            return self.cached_result
        
        results = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '3.0.0',
            'checks': {},
            'summary': {
                'total_checks': len(self.checks),
                'passed': 0,
                'failed': 0,
                'warnings': 0
            }
        }
        
        overall_healthy = True
        has_warnings = False
        
        for check_name, check_info in self.checks.items():
            try:
                start_time = time.time()
                result = check_info['func']()
                check_duration = (time.time() - start_time) * 1000  # ms
                
                # Normalize result format
                if isinstance(result, dict):
                    check_result = result.copy()
                    check_result['response_time_ms'] = round(check_duration, 2)
                    check_result['check_name'] = check_name
                else:
                    check_result = {
                        'status': 'healthy' if result else 'unhealthy',
                        'response_time_ms': round(check_duration, 2),
                        'check_name': check_name
                    }
                
                # Determine check status
                check_status = check_result.get('status', 'unknown')
                
                if check_status in ['unhealthy', 'error', 'critical']:
                    results['summary']['failed'] += 1
                    if check_info['critical']:
                        overall_healthy = False
                    else:
                        has_warnings = True
                        
                elif check_status == 'warning':
                    results['summary']['warnings'] += 1
                    has_warnings = True
                    results['summary']['passed'] += 1
                else:
                    results['summary']['passed'] += 1
                
                results['checks'][check_name] = check_result
                check_info['last_result'] = check_result
                check_info['last_check'] = now
                
            except Exception as e:
                logger.error(f"Health check '{check_name}' failed: {e}")
                error_result = {
                    'status': 'error',
                    'error': str(e),
                    'check_name': check_name,
                    'response_time_ms': 0
                }
                results['checks'][check_name] = error_result
                results['summary']['failed'] += 1
                
                if check_info['critical']:
                    overall_healthy = False
        
        # Determine overall status
        if not overall_healthy:
            results['status'] = 'unhealthy'
        elif has_warnings:
            results['status'] = 'degraded'
        
        # Cache result
        self.cached_result = results
        self.last_check_time = now
        
        return results
    
    def get_quick_status(self) -> Dict[str, Any]:
        """Get quick health status without running all checks"""
        if self.cached_result:
            return {
                'status': self.cached_result['status'],
                'timestamp': self.cached_result['timestamp'],
                'cached': True
            }
        
        # Run a minimal check
        return {
            'status': 'unknown',
            'timestamp': datetime.utcnow().isoformat(),
            'message': 'No recent health check data'
        }

def database_health_check() -> Dict[str, Any]:
    """Check database connectivity and health"""
    try:
        from flask import current_app
        from models.user import create_user_model
        
        # Test database connection
        start_time = time.time()
        db = current_app.extensions['sqlalchemy'].db
        
        # Simple query to test connection
        result = db.engine.execute('SELECT 1 as test').fetchone()
        response_time = (time.time() - start_time) * 1000
        
        # Get connection info
        engine = db.engine
        pool = engine.pool
        
        return {
            'status': 'healthy',
            'connection_test': result[0] == 1 if result else False,
            'response_time_ms': round(response_time, 2),
            'pool_size': getattr(pool, 'size', 'unknown'),
            'checked_out': getattr(pool, 'checkedout', 'unknown'),
            'pool_checked_in': getattr(pool, 'checkedin', 'unknown')
        }
        
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'connection_test': False
        }

def redis_health_check() -> Dict[str, Any]:
    """Check Redis connectivity and health"""
    try:
        from utils.redis_client import redis_health_check
        return redis_health_check()
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'redis_available': False
        }

def security_health_check() -> Dict[str, Any]:
    """Check security middleware health"""
    try:
        from utils.security_middleware import security_health_check
        return security_health_check()
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'security_middleware_enabled': False
        }

def rate_limiter_health_check() -> Dict[str, Any]:
    """Check rate limiter health"""
    try:
        from utils.rate_limiter import rate_limiter_health_check
        return rate_limiter_health_check()
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'limiter_initialized': False
        }

def memory_health_check() -> Dict[str, Any]:
    """Check memory usage and health"""
    try:
        from utils.memory_monitor import memory_health_check
        return memory_health_check()
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'monitoring_active': False
        }

def system_health_check() -> Dict[str, Any]:
    """Check system resources health"""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        
        # Load average (if available)
        try:
            load_avg = psutil.getloadavg()
        except:
            load_avg = None
        
        # Determine status
        status = 'healthy'
        if cpu_percent > 90 or disk_percent > 90:
            status = 'critical'
        elif cpu_percent > 80 or disk_percent > 85:
            status = 'warning'
        
        result = {
            'status': status,
            'cpu_percent': round(cpu_percent, 2),
            'disk_percent': round(disk_percent, 2),
            'disk_free_gb': round((disk.total - disk.used) / (1024**3), 2)
        }
        
        if load_avg:
            result['load_average'] = [round(x, 2) for x in load_avg]
        
        return result
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }

def application_health_check() -> Dict[str, Any]:
    """Check application-specific health"""
    try:
        from flask import current_app
        
        # Check if app is in debug mode (should be False in production)
        debug_mode = current_app.config.get('DEBUG', False)
        
        # Check critical configuration
        has_secret_key = bool(current_app.config.get('SECRET_KEY'))
        has_db_uri = bool(current_app.config.get('SQLALCHEMY_DATABASE_URI'))
        
        # Basic functionality test
        try:
            # Test template rendering
            from flask import render_template_string
            render_template_string('{{ "test" }}')
            template_rendering = True
        except:
            template_rendering = False
        
        # Determine status
        issues = []
        if debug_mode:
            issues.append("Debug mode enabled in production")
        if not has_secret_key:
            issues.append("SECRET_KEY not configured")
        if not has_db_uri:
            issues.append("Database URI not configured")
        if not template_rendering:
            issues.append("Template rendering failed")
        
        status = 'unhealthy' if issues else 'healthy'
        
        return {
            'status': status,
            'debug_mode': debug_mode,
            'secret_key_configured': has_secret_key,
            'database_configured': has_db_uri,
            'template_rendering': template_rendering,
            'issues': issues
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }

# Global health monitor instance
_health_monitor = None

def init_health_monitor() -> HealthMonitor:
    """Initialize the global health monitor"""
    global _health_monitor
    
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
        
        # Register all health checks
        _health_monitor.register_check('database', database_health_check, critical=True)
        _health_monitor.register_check('redis', redis_health_check, critical=False)
        _health_monitor.register_check('security', security_health_check, critical=True)
        _health_monitor.register_check('rate_limiter', rate_limiter_health_check, critical=False)
        _health_monitor.register_check('memory', memory_health_check, critical=True)
        _health_monitor.register_check('system', system_health_check, critical=True)
        _health_monitor.register_check('application', application_health_check, critical=True)
        
        logger.info("Health monitor initialized with all checks")
    
    return _health_monitor

def get_health_monitor() -> HealthMonitor:
    """Get the global health monitor instance"""
    global _health_monitor
    if _health_monitor is None:
        return init_health_monitor()
    return _health_monitor