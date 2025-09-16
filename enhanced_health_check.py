#!/usr/bin/env python3
"""
Enhanced Health Check System for Stevedores Dashboard 3.0
Comprehensive system status monitoring for production deployment validation
"""

import os
import sys
import time
import psutil
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from flask import jsonify, current_app

# Configure health check logging
health_logger = logging.getLogger('health_check')

def get_system_metrics() -> Dict[str, Any]:
    """Get comprehensive system metrics"""
    try:
        # Memory metrics
        memory = psutil.virtual_memory()
        memory_metrics = {
            'total': round(memory.total / (1024**3), 2),  # GB
            'available': round(memory.available / (1024**3), 2),  # GB
            'used': round(memory.used / (1024**3), 2),  # GB
            'percent': memory.percent,
            'status': 'healthy' if memory.percent < 85 else 'warning' if memory.percent < 95 else 'critical'
        }
        
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_metrics = {
            'cores': psutil.cpu_count(),
            'usage_percent': cpu_percent,
            'status': 'healthy' if cpu_percent < 80 else 'warning' if cpu_percent < 95 else 'critical'
        }
        
        # Load average (if available)
        if hasattr(os, 'getloadavg'):
            load_avg = os.getloadavg()
            cpu_metrics['load_average'] = {
                '1min': load_avg[0],
                '5min': load_avg[1],
                '15min': load_avg[2]
            }
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        disk_metrics = {
            'total': round(disk.total / (1024**3), 2),  # GB
            'free': round(disk.free / (1024**3), 2),  # GB
            'used': round(disk.used / (1024**3), 2),  # GB
            'percent': round((disk.used / disk.total) * 100, 1),
            'status': 'healthy' if disk.free > 2 else 'warning' if disk.free > 0.5 else 'critical'
        }
        
        return {
            'memory': memory_metrics,
            'cpu': cpu_metrics,
            'disk': disk_metrics,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        health_logger.error(f"Error getting system metrics: {e}")
        return {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

def check_database_health() -> Dict[str, Any]:
    """Check database connectivity and health"""
    try:
        from flask_sqlalchemy import SQLAlchemy
        from sqlalchemy import text
        
        # Get database instance
        from app import db
        
        start_time = time.time()
        
        # Test basic connection
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            test_result = result.fetchone()
        
        connection_time = round((time.time() - start_time) * 1000, 2)  # milliseconds
        
        # Get database info
        db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if 'postgresql://' in db_uri or 'postgres://' in db_uri:
            db_type = 'postgresql'
        elif 'sqlite://' in db_uri:
            db_type = 'sqlite'
        else:
            db_type = 'unknown'
        
        return {
            'status': 'healthy',
            'connection_time_ms': connection_time,
            'database_type': db_type,
            'engine_options': current_app.config.get('SQLALCHEMY_ENGINE_OPTIONS', {}),
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except ImportError as e:
        return {
            'status': 'error',
            'error': f"Database modules not available: {str(e)}",
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

def check_model_health() -> Dict[str, Any]:
    """Check if models are properly loaded and accessible"""
    try:
        from app import User, Vessel, CargoTally
        
        model_checks = {}
        
        # Test User model
        try:
            user_count = User.query.count()
            model_checks['User'] = {
                'status': 'healthy',
                'record_count': user_count
            }
        except Exception as e:
            model_checks['User'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Test Vessel model
        try:
            vessel_count = Vessel.query.count()
            model_checks['Vessel'] = {
                'status': 'healthy',
                'record_count': vessel_count
            }
        except Exception as e:
            model_checks['Vessel'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Test CargoTally model
        try:
            tally_count = CargoTally.query.count()
            model_checks['CargoTally'] = {
                'status': 'healthy',
                'record_count': tally_count
            }
        except Exception as e:
            model_checks['CargoTally'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Overall model health
        healthy_models = len([m for m in model_checks.values() if m['status'] == 'healthy'])
        total_models = len(model_checks)
        
        return {
            'status': 'healthy' if healthy_models == total_models else 'degraded',
            'models': model_checks,
            'healthy_count': healthy_models,
            'total_count': total_models,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except ImportError as e:
        return {
            'status': 'error',
            'error': f"Models not available: {str(e)}",
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

def check_security_middleware() -> Dict[str, Any]:
    """Check security middleware status"""
    try:
        security_checks = {}
        
        # Check CSRF protection
        try:
            from flask_wtf.csrf import CSRFProtect
            security_checks['csrf'] = {
                'status': 'healthy',
                'enabled': current_app.config.get('WTF_CSRF_ENABLED', False)
            }
        except Exception as e:
            security_checks['csrf'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Check Login Manager
        try:
            from flask_login import LoginManager
            security_checks['login_manager'] = {
                'status': 'healthy',
                'login_view': current_app.config.get('login_manager.login_view', 'not_set')
            }
        except Exception as e:
            security_checks['login_manager'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Check security manager
        try:
            from app import security_manager
            if security_manager:
                security_checks['security_manager'] = {'status': 'healthy'}
            else:
                security_checks['security_manager'] = {'status': 'not_initialized'}
        except Exception as e:
            security_checks['security_manager'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Check JWT manager
        try:
            from app import jwt_manager
            if jwt_manager:
                security_checks['jwt_manager'] = {'status': 'healthy'}
            else:
                security_checks['jwt_manager'] = {'status': 'not_initialized'}
        except Exception as e:
            security_checks['jwt_manager'] = {
                'status': 'error',
                'error': str(e)
            }
        
        healthy_security = len([s for s in security_checks.values() if s['status'] == 'healthy'])
        total_security = len(security_checks)
        
        return {
            'status': 'healthy' if healthy_security >= total_security * 0.75 else 'degraded',
            'components': security_checks,
            'healthy_count': healthy_security,
            'total_count': total_security,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

def check_configuration_health() -> Dict[str, Any]:
    """Check configuration status"""
    try:
        config_checks = {
            'secret_key': {
                'status': 'healthy' if current_app.config.get('SECRET_KEY') else 'critical',
                'length': len(current_app.config.get('SECRET_KEY', ''))
            },
            'database_uri': {
                'status': 'healthy' if current_app.config.get('SQLALCHEMY_DATABASE_URI') else 'critical',
                'type': 'postgresql' if 'postgres' in current_app.config.get('SQLALCHEMY_DATABASE_URI', '') else 'sqlite' if 'sqlite' in current_app.config.get('SQLALCHEMY_DATABASE_URI', '') else 'unknown'
            },
            'debug_mode': {
                'status': 'healthy',
                'enabled': current_app.config.get('DEBUG', False)
            },
            'csrf_enabled': {
                'status': 'healthy' if current_app.config.get('WTF_CSRF_ENABLED') else 'warning',
                'enabled': current_app.config.get('WTF_CSRF_ENABLED', False)
            }
        }
        
        critical_issues = len([c for c in config_checks.values() if c['status'] == 'critical'])
        
        return {
            'status': 'critical' if critical_issues > 0 else 'healthy',
            'checks': config_checks,
            'critical_issues': critical_issues,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

def comprehensive_health_check() -> Dict[str, Any]:
    """Run comprehensive health check and return detailed status"""
    
    start_time = time.time()
    
    # Run all health checks
    system_health = get_system_metrics()
    database_health = check_database_health()
    model_health = check_model_health()
    security_health = check_security_middleware()
    config_health = check_configuration_health()
    
    check_duration = time.time() - start_time
    
    # Determine overall status
    critical_systems = ['database', 'config']
    important_systems = ['models', 'security']
    
    overall_status = 'healthy'
    
    # Check critical systems
    if (database_health.get('status') in ['unhealthy', 'error'] or 
        config_health.get('status') in ['critical', 'error']):
        overall_status = 'critical'
    # Check important systems
    elif (model_health.get('status') in ['error'] or 
          security_health.get('status') in ['error']):
        overall_status = 'degraded'
    # Check for warnings
    elif (model_health.get('status') == 'degraded' or 
          security_health.get('status') == 'degraded' or
          any(metric.get('status') in ['warning', 'critical'] for metric in system_health.values() if isinstance(metric, dict))):
        overall_status = 'warning'
    
    # Compile final health report
    health_report = {
        'overall_status': overall_status,
        'timestamp': datetime.utcnow().isoformat(),
        'check_duration': round(check_duration, 3),
        'version': '3.0.6-SCHEMA-FIX-20250805',
        'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        'environment': os.environ.get('FLASK_ENV', 'production'),
        'system': system_health,
        'database': database_health,
        'models': model_health,
        'security': security_health,
        'configuration': config_health,
        'features': {
            'offline_support': True,
            'pwa_enabled': True,
            'csrf_protection': current_app.config.get('WTF_CSRF_ENABLED', False),
            'database_retry': True,
            'audit_logging': security_health.get('components', {}).get('security_manager', {}).get('status') == 'healthy'
        }
    }
    
    return health_report

def create_health_endpoint(app):
    """Create enhanced health check endpoint"""
    
    @app.route('/health')
    def health_check():
        """Basic health check endpoint"""
        try:
            health_report = comprehensive_health_check()
            
            # Return appropriate HTTP status code
            status_code = 200
            if health_report['overall_status'] == 'critical':
                status_code = 503  # Service Unavailable
            elif health_report['overall_status'] == 'degraded':
                status_code = 503  # Service Unavailable
            elif health_report['overall_status'] == 'warning':
                status_code = 200  # OK but with warnings
            
            return jsonify(health_report), status_code
            
        except Exception as e:
            health_logger.error(f"Health check failed: {e}")
            return jsonify({
                'overall_status': 'error',
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
                'version': '3.0.6-SCHEMA-FIX-20250805'
            }), 503
    
    @app.route('/health/detailed')
    def detailed_health_check():
        """Detailed health check with full system information"""
        try:
            health_report = comprehensive_health_check()
            return jsonify(health_report), 200
            
        except Exception as e:
            health_logger.error(f"Detailed health check failed: {e}")
            return jsonify({
                'overall_status': 'error',
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
                'version': '3.0.6-SCHEMA-FIX-20250805'
            }), 503
    
    @app.route('/health/quick')
    def quick_health_check():
        """Quick health check for basic status"""
        try:
            # Just check database connectivity
            database_health = check_database_health()
            
            return jsonify({
                'status': 'healthy' if database_health.get('status') == 'healthy' else 'unhealthy',
                'timestamp': datetime.utcnow().isoformat(),
                'database': database_health.get('status'),
                'version': '3.0.6-SCHEMA-FIX-20250805'
            }), 200 if database_health.get('status') == 'healthy' else 503
            
        except Exception as e:
            return jsonify({
                'status': 'error',
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }), 503
    
    health_logger.info("✅ Enhanced health check endpoints registered")
    return app