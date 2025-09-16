"""
Memory Monitoring Routes for Stevedores Dashboard 3.0
Provides endpoints for memory monitoring, alerts, and optimization
"""

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import logging

from utils.memory_monitor import get_memory_monitor, memory_limit
from utils.security_middleware import security_headers

logger = logging.getLogger(__name__)

# Create memory monitoring blueprint
memory_bp = Blueprint('memory', __name__, url_prefix='/api/memory')

@memory_bp.route('/health', methods=['GET'])
@security_headers
def memory_health():
    """Get current memory health status"""
    try:
        monitor = get_memory_monitor()
        if not monitor:
            return jsonify({
                "status": "not_initialized",
                "error": "Memory monitor not initialized",
                "timestamp": datetime.now().isoformat()
            }), 503
        
        health_status = monitor.get_health_status()
        
        # Determine HTTP status code based on memory status
        status_code = 200
        if health_status["status"] == "critical":
            status_code = 503
        elif health_status["status"] == "warning":
            status_code = 200  # Still serving but with warning
        elif health_status["status"] == "emergency":
            status_code = 503
        
        return jsonify(health_status), status_code
        
    except Exception as e:
        logger.error(f"Memory health check failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@memory_bp.route('/usage', methods=['GET'])
@security_headers
def memory_usage():
    """Get detailed memory usage statistics"""
    try:
        monitor = get_memory_monitor()
        if not monitor:
            return jsonify({
                "error": "Memory monitor not initialized"
            }), 503
        
        usage = monitor.get_memory_usage()
        return jsonify(usage), 200
        
    except Exception as e:
        logger.error(f"Failed to get memory usage: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@memory_bp.route('/trend', methods=['GET'])
@security_headers
def memory_trend():
    """Get memory usage trend over time"""
    try:
        monitor = get_memory_monitor()
        if not monitor:
            return jsonify({
                "error": "Memory monitor not initialized"
            }), 503
        
        # Get minutes parameter (default 30)
        minutes = request.args.get('minutes', 30, type=int)
        if minutes > 1440:  # Limit to 24 hours
            minutes = 1440
        
        trend = monitor.get_memory_trend(minutes)
        return jsonify(trend), 200
        
    except Exception as e:
        logger.error(f"Failed to get memory trend: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@memory_bp.route('/report', methods=['GET'])
@security_headers
@login_required
def memory_report():
    """Get comprehensive memory usage report (authenticated users only)"""
    try:
        monitor = get_memory_monitor()
        if not monitor:
            return jsonify({
                "error": "Memory monitor not initialized"
            }), 503
        
        report = monitor.get_memory_report()
        
        # Add request context
        report["request_info"] = {
            "user_id": current_user.id if hasattr(current_user, 'id') else None,
            "user_authenticated": not current_user.is_anonymous,
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(report), 200
        
    except Exception as e:
        logger.error(f"Failed to get memory report: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@memory_bp.route('/cleanup', methods=['POST'])
@security_headers
@login_required
@memory_limit(threshold_percent=95)  # Don't allow cleanup if memory is too high
def force_cleanup():
    """Force memory cleanup (authenticated users only)"""
    try:
        monitor = get_memory_monitor()
        if not monitor:
            return jsonify({
                "error": "Memory monitor not initialized"
            }), 503
        
        # Get pre-cleanup stats
        pre_cleanup = monitor.get_memory_usage()
        pre_memory = pre_cleanup.get("container", {}).get("percent", 0)
        
        # Force cleanup
        monitor.force_memory_cleanup()
        
        # Get post-cleanup stats
        post_cleanup = monitor.get_memory_usage()
        post_memory = post_cleanup.get("container", {}).get("percent", 0)
        
        freed_percent = pre_memory - post_memory
        
        logger.info(f"Manual memory cleanup by user {current_user.id if hasattr(current_user, 'id') else 'unknown'}: "
                   f"{pre_memory:.1f}% -> {post_memory:.1f}% ({freed_percent:.1f}% freed)")
        
        return jsonify({
            "status": "success",
            "cleanup_performed": True,
            "memory_before": round(pre_memory, 2),
            "memory_after": round(post_memory, 2),
            "memory_freed": round(freed_percent, 2),
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to force memory cleanup: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@memory_bp.route('/alerts', methods=['GET'])
@security_headers
@login_required
def memory_alerts():
    """Get memory alert history (authenticated users only)"""
    try:
        monitor = get_memory_monitor()
        if not monitor:
            return jsonify({
                "error": "Memory monitor not initialized"
            }), 503
        
        # Get limit parameter (default 50)
        limit = request.args.get('limit', 50, type=int)
        if limit > 500:  # Reasonable limit
            limit = 500
        
        # Get severity filter
        severity = request.args.get('severity', 'all')
        
        alerts = list(monitor.alert_history)
        
        # Filter by severity if specified
        if severity != 'all':
            alerts = [alert for alert in alerts if alert.get('level') == severity]
        
        # Limit results
        alerts = alerts[-limit:] if len(alerts) > limit else alerts
        
        return jsonify({
            "alerts": alerts,
            "total_count": len(monitor.alert_history),
            "filtered_count": len(alerts),
            "filter": {
                "limit": limit,
                "severity": severity
            },
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get memory alerts: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@memory_bp.route('/config', methods=['GET'])
@security_headers
@login_required
def memory_config():
    """Get memory monitor configuration (authenticated users only)"""
    try:
        monitor = get_memory_monitor()
        if not monitor:
            return jsonify({
                "error": "Memory monitor not initialized"
            }), 503
        
        config = {
            "container": {
                "memory_limit_mb": round(monitor.memory_limit / (1024**2), 2),
                "available_memory_mb": round(monitor.available_memory / (1024**2), 2),
                "safety_buffer_mb": 64  # From constants
            },
            "thresholds": {
                "warning": monitor.warning_threshold,
                "critical": monitor.critical_threshold,
                "emergency": monitor.emergency_threshold
            },
            "monitoring": {
                "check_interval": monitor.check_interval,
                "is_active": monitor.is_monitoring,
                "history_size": len(monitor.memory_history),
                "max_history": monitor.memory_history.maxlen
            },
            "optimization": {
                "optimal_workers": monitor.calculate_optimal_workers(),
                "cleanup_callbacks": len(monitor.cleanup_callbacks),
                "gc_frequency": monitor.gc_frequency
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(config), 200
        
    except Exception as e:
        logger.error(f"Failed to get memory config: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@memory_bp.route('/workers/optimal', methods=['GET'])
@security_headers
def optimal_workers():
    """Get optimal worker count based on current memory state"""
    try:
        monitor = get_memory_monitor()
        if not monitor:
            return jsonify({
                "error": "Memory monitor not initialized"
            }), 503
        
        optimal = monitor.calculate_optimal_workers()
        current_usage = monitor.get_memory_usage()
        
        return jsonify({
            "optimal_workers": optimal,
            "current_memory_percent": current_usage.get("container", {}).get("percent", 0),
            "memory_limit_mb": round(monitor.memory_limit / (1024**2), 2),
            "recommendation": "healthy" if optimal >= 3 else "consider_memory_increase",
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get optimal workers: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

# Error handlers for the blueprint
@memory_bp.errorhandler(503)
def service_unavailable(error):
    """Handle service unavailable errors"""
    return jsonify({
        "error": "Memory monitoring service unavailable",
        "message": "The server is experiencing high memory usage",
        "retry_after": 30,
        "timestamp": datetime.now().isoformat()
    }), 503

@memory_bp.errorhandler(429)
def too_many_requests(error):
    """Handle rate limit errors"""
    return jsonify({
        "error": "Too many requests",
        "message": "Memory monitoring API rate limit exceeded",
        "retry_after": 60,
        "timestamp": datetime.now().isoformat()
    }), 429

# Register the blueprint in the app (to be done in app.py)
def register_memory_routes(app):
    """Register memory monitoring routes with the app"""
    app.register_blueprint(memory_bp)
    logger.info("Memory monitoring routes registered")