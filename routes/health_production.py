"""
Production health check endpoints for Stevedores Dashboard 3.0.
Comprehensive health monitoring with Redis and memory status.
"""

from flask import Blueprint, jsonify, current_app
import time
from datetime import datetime
import os

# Health blueprint
health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Comprehensive health check."""
    start_time = time.time()
    health_data = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '3.0.6-PRODUCTION-FIX',
        'environment': os.getenv('FLASK_ENV', 'production'),
        'checks': {}
    }
    
    # Database check
    try:
        from app import db
        db.engine.execute('SELECT 1')
        health_data['checks']['database'] = {
            'status': 'healthy',
            'message': 'Database connection successful'
        }
    except Exception as e:
        health_data['status'] = 'unhealthy'
        health_data['checks']['database'] = {
            'status': 'unhealthy',
            'message': f'Database error: {str(e)}'
        }
    
    # Redis check
    try:
        from utils.redis_client_production import production_redis_client
        redis_status = production_redis_client.get_status()
        health_data['checks']['redis'] = redis_status
        if not redis_status.get('redis_connected', False):
            health_data['status'] = 'degraded'  # Not critical if fallback works
    except Exception as e:
        health_data['checks']['redis'] = {
            'status': 'unhealthy',
            'message': f'Redis error: {str(e)}'
        }
    
    # Memory check
    try:
        from utils.memory_monitor_production import memory_health_check
        memory_status = memory_health_check()
        health_data['checks']['memory'] = memory_status
        if memory_status['status'] == 'unhealthy':
            health_data['status'] = 'unhealthy'
    except Exception as e:
        health_data['checks']['memory'] = {
            'status': 'unknown',
            'message': f'Memory check error: {str(e)}'
        }
    
    # Response time
    response_time = (time.time() - start_time) * 1000
    health_data['response_time_ms'] = round(response_time, 2)
    
    # Set HTTP status based on health
    status_code = 200
    if health_data['status'] == 'unhealthy':
        status_code = 503
    elif health_data['status'] == 'degraded':
        status_code = 200  # Still operational
    
    return jsonify(health_data), status_code

@health_bp.route('/health/quick', methods=['GET'])
def quick_health_check():
    """Quick health check for load balancers."""
    try:
        # Minimal check - just verify app is responding
        from app import db
        db.engine.execute('SELECT 1')
        
        return jsonify({
            'status': 'ok',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception:
        return jsonify({
            'status': 'error',
            'timestamp': datetime.utcnow().isoformat()
        }), 503

@health_bp.route('/health/detailed', methods=['GET'])
def detailed_health_check():
    """Detailed health check with all system information."""
    start_time = time.time()
    health_data = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '3.0.6-PRODUCTION-FIX',
        'environment': os.getenv('FLASK_ENV', 'production'),
        'system': {},
        'checks': {}
    }
    
    # System information
    try:
        import psutil
        health_data['system'] = {
            'cpu_percent': psutil.cpu_percent(),
            'memory_total_mb': psutil.virtual_memory().total // (1024 * 1024),
            'disk_usage_percent': psutil.disk_usage('/').percent,
            'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None
        }
    except Exception as e:
        health_data['system']['error'] = str(e)
    
    # Database check with connection info
    try:
        from app import db
        result = db.engine.execute('SELECT 1')
        health_data['checks']['database'] = {
            'status': 'healthy',
            'connection_pool_size': db.engine.pool.size(),
            'checked_in_connections': db.engine.pool.checkedin()
        }
    except Exception as e:
        health_data['status'] = 'unhealthy'
        health_data['checks']['database'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
    
    # Redis detailed check
    try:
        from utils.redis_client_production import production_redis_client
        redis_status = production_redis_client.get_status()
        ping_start = time.time()
        ping_success = production_redis_client.ping()
        ping_time = (time.time() - ping_start) * 1000
        
        health_data['checks']['redis'] = {
            **redis_status,
            'ping_success': ping_success,
            'ping_time_ms': round(ping_time, 2)
        }
    except Exception as e:
        health_data['checks']['redis'] = {
            'status': 'error',
            'error': str(e)
        }
    
    # Memory detailed check
    try:
        from utils.memory_monitor_production import production_memory_monitor
        memory_report = production_memory_monitor.get_memory_report()
        health_data['checks']['memory'] = memory_report
        
        if memory_report['status'] in ['critical', 'emergency']:
            health_data['status'] = 'unhealthy'
    except Exception as e:
        health_data['checks']['memory'] = {
            'status': 'error',
            'error': str(e)
        }
    
    # Application-specific checks
    try:
        from models.vessel import create_vessel_model
        from app import db
        Vessel = create_vessel_model(db)
        vessel_count = Vessel.query.count()
        
        health_data['checks']['application'] = {
            'status': 'healthy',
            'vessel_count': vessel_count,
            'models_loaded': True
        }
    except Exception as e:
        health_data['checks']['application'] = {
            'status': 'error',
            'error': str(e)
        }
    
    # Response time
    response_time = (time.time() - start_time) * 1000
    health_data['response_time_ms'] = round(response_time, 2)
    
    return jsonify(health_data), 200 if health_data['status'] != 'unhealthy' else 503