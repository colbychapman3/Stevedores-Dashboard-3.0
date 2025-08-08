"""
Production Logging Dashboard Routes for Stevedores Dashboard 3.0
Real-time log monitoring and maritime operations visibility
"""

import os
import json
import time
from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, jsonify, request, current_app, g
from flask_login import login_required
import logging

# Import logging components
from ..utils.structured_logger import get_structured_logger, ComponentType
from ..utils.log_aggregator import get_log_aggregator
from ..utils.monitoring_integrations import get_monitoring_manager
from ..utils.maritime_alerts import get_maritime_alert_system
from ..utils.log_retention import get_log_retention_manager

# Create blueprint
logging_dashboard = Blueprint('logging_dashboard', __name__)
logger = get_structured_logger()


@logging_dashboard.route('/admin/logging')
@login_required
def logging_dashboard_view():
    """Main logging dashboard page"""
    try:
        return render_template('admin/logging_dashboard.html')
    except Exception as e:
        logger.error(
            "Error rendering logging dashboard",
            component=ComponentType.WEB_SERVER.value,
            exception=e
        )
        return jsonify({'error': 'Failed to load logging dashboard'}), 500


@logging_dashboard.route('/api/admin/logging/overview')
@login_required
def logging_overview():
    """Get logging system overview"""
    try:
        overview_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'system_health': 'healthy',
            'components': {}
        }
        
        # Log aggregator status
        aggregator = get_log_aggregator()
        if aggregator:
            overview_data['components']['aggregator'] = {
                'status': 'active' if aggregator.is_processing else 'inactive',
                'patterns_detected': aggregator.processing_stats['patterns_detected'],
                'logs_processed': aggregator.processing_stats['logs_processed'],
                'processing_errors': aggregator.processing_stats['processing_errors'],
                'buffer_size': len(aggregator.log_buffer),
                'active_patterns': len(aggregator.active_patterns)
            }
        else:
            overview_data['components']['aggregator'] = {'status': 'not_initialized'}
        
        # Monitoring integrations status
        monitoring = get_monitoring_manager()
        if monitoring:
            health = monitoring.get_monitoring_health()
            overview_data['components']['monitoring'] = {
                'status': health['health_status'],
                'providers': health['providers'],
                'maritime_metrics': health['maritime_metrics'],
                'performance_counters': health['performance_counters']
            }
        else:
            overview_data['components']['monitoring'] = {'status': 'not_initialized'}
        
        # Alert system status
        alert_system = get_maritime_alert_system()
        if alert_system:
            alert_stats = alert_system.get_alert_statistics(24)
            overview_data['components']['alerts'] = {
                'status': 'active',
                'active_alerts': len(alert_system.active_alerts),
                'total_alerts_24h': alert_stats['total_alerts'],
                'critical_alerts_24h': alert_stats['alerts_by_priority'].get('critical', 0),
                'rules_configured': len(alert_system.rules)
            }
        else:
            overview_data['components']['alerts'] = {'status': 'not_initialized'}
        
        # Log retention status
        retention_manager = get_log_retention_manager()
        if retention_manager:
            storage_stats = retention_manager.get_storage_statistics()
            overview_data['components']['retention'] = {
                'status': 'active' if retention_manager.is_active else 'inactive',
                'current_usage_mb': storage_stats['current_usage_mb'],
                'usage_percentage': storage_stats['usage_percentage'],
                'total_files_archived': storage_stats['total_files_archived'],
                'compression_ratio': storage_stats['avg_compression_ratio']
            }
        else:
            overview_data['components']['retention'] = {'status': 'not_initialized'}
        
        # Determine overall health
        component_statuses = [comp.get('status', 'unknown') for comp in overview_data['components'].values()]
        if 'not_initialized' in component_statuses:
            overview_data['system_health'] = 'degraded'
        elif any(status in ['inactive', 'error'] for status in component_statuses):
            overview_data['system_health'] = 'warning'
        
        return jsonify(overview_data)
        
    except Exception as e:
        logger.error(
            "Error getting logging overview",
            component=ComponentType.WEB_SERVER.value,
            exception=e
        )
        return jsonify({'error': 'Failed to get logging overview'}), 500


@logging_dashboard.route('/api/admin/logging/patterns')
@login_required
def get_pattern_summary():
    """Get pattern detection summary"""
    try:
        hours = request.args.get('hours', 24, type=int)
        
        aggregator = get_log_aggregator()
        if not aggregator:
            return jsonify({'error': 'Log aggregator not initialized'}), 503
        
        pattern_summary = aggregator.get_pattern_summary(hours)
        maritime_data = aggregator.get_maritime_dashboard_data()
        
        response_data = {
            'summary': pattern_summary,
            'maritime_dashboard': maritime_data,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(
            "Error getting pattern summary",
            component=ComponentType.WEB_SERVER.value,
            exception=e
        )
        return jsonify({'error': 'Failed to get pattern summary'}), 500


@logging_dashboard.route('/api/admin/logging/alerts')
@login_required
def get_active_alerts():
    """Get active alerts"""
    try:
        priority_filter = request.args.get('priority')
        
        alert_system = get_maritime_alert_system()
        if not alert_system:
            return jsonify({'error': 'Alert system not initialized'}), 503
        
        from ..utils.maritime_alerts import AlertPriority
        
        priority_obj = None
        if priority_filter:
            try:
                priority_obj = AlertPriority(priority_filter.lower())
            except ValueError:
                pass
        
        active_alerts = alert_system.get_active_alerts(priority_obj)
        alert_stats = alert_system.get_alert_statistics(24)
        
        # Convert alerts to JSON-serializable format
        alerts_data = [alert.to_dict() for alert in active_alerts]
        
        response_data = {
            'active_alerts': alerts_data,
            'statistics': alert_stats,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(
            "Error getting active alerts",
            component=ComponentType.WEB_SERVER.value,
            exception=e
        )
        return jsonify({'error': 'Failed to get active alerts'}), 500


@logging_dashboard.route('/api/admin/logging/alerts/<alert_id>/acknowledge', methods=['POST'])
@login_required
def acknowledge_alert(alert_id):
    """Acknowledge an alert"""
    try:
        alert_system = get_maritime_alert_system()
        if not alert_system:
            return jsonify({'error': 'Alert system not initialized'}), 503
        
        # Get current user identifier
        acknowledged_by = getattr(g, 'jwt_claims', {}).get('user_id', 'admin')
        
        success = alert_system.acknowledge_alert(alert_id, str(acknowledged_by))
        
        if success:
            logger.info(
                f"Alert acknowledged via dashboard",
                component=ComponentType.WEB_SERVER.value,
                alert_id=alert_id,
                acknowledged_by=acknowledged_by
            )
            return jsonify({'success': True, 'alert_id': alert_id})
        else:
            return jsonify({'error': 'Alert not found or already acknowledged'}), 404
            
    except Exception as e:
        logger.error(
            "Error acknowledging alert",
            component=ComponentType.WEB_SERVER.value,
            alert_id=alert_id,
            exception=e
        )
        return jsonify({'error': 'Failed to acknowledge alert'}), 500


@logging_dashboard.route('/api/admin/logging/alerts/<alert_id>/resolve', methods=['POST'])
@login_required
def resolve_alert(alert_id):
    """Resolve an alert"""
    try:
        alert_system = get_maritime_alert_system()
        if not alert_system:
            return jsonify({'error': 'Alert system not initialized'}), 503
        
        # Get current user identifier
        resolved_by = getattr(g, 'jwt_claims', {}).get('user_id', 'admin')
        
        success = alert_system.resolve_alert(alert_id, str(resolved_by))
        
        if success:
            logger.info(
                f"Alert resolved via dashboard",
                component=ComponentType.WEB_SERVER.value,
                alert_id=alert_id,
                resolved_by=resolved_by
            )
            return jsonify({'success': True, 'alert_id': alert_id})
        else:
            return jsonify({'error': 'Alert not found or already resolved'}), 404
            
    except Exception as e:
        logger.error(
            "Error resolving alert",
            component=ComponentType.WEB_SERVER.value,
            alert_id=alert_id,
            exception=e
        )
        return jsonify({'error': 'Failed to resolve alert'}), 500


@logging_dashboard.route('/api/admin/logging/storage')
@login_required
def get_storage_statistics():
    """Get log storage statistics"""
    try:
        retention_manager = get_log_retention_manager()
        if not retention_manager:
            return jsonify({'error': 'Log retention manager not initialized'}), 503
        
        storage_stats = retention_manager.get_storage_statistics()
        archives = retention_manager.list_archives()
        
        response_data = {
            'storage_statistics': storage_stats,
            'archives': archives[:20],  # Limit to recent 20 archives
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(
            "Error getting storage statistics",
            component=ComponentType.WEB_SERVER.value,
            exception=e
        )
        return jsonify({'error': 'Failed to get storage statistics'}), 500


@logging_dashboard.route('/api/admin/logging/cleanup', methods=['POST'])
@login_required
def manual_log_cleanup():
    """Perform manual log cleanup"""
    try:
        retention_manager = get_log_retention_manager()
        if not retention_manager:
            return jsonify({'error': 'Log retention manager not initialized'}), 503
        
        # Get parameters
        force_cleanup = request.json.get('force', False) if request.json else False
        
        # Perform cleanup
        cleanup_result = retention_manager.manual_cleanup(force_cleanup=force_cleanup)
        
        logger.info(
            "Manual log cleanup performed via dashboard",
            component=ComponentType.WEB_SERVER.value,
            force_cleanup=force_cleanup,
            cleanup_result=cleanup_result
        )
        
        return jsonify({
            'success': True,
            'cleanup_result': cleanup_result,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(
            "Error performing manual cleanup",
            component=ComponentType.WEB_SERVER.value,
            exception=e
        )
        return jsonify({'error': 'Failed to perform cleanup'}), 500


@logging_dashboard.route('/api/admin/logging/monitoring/health')
@login_required
def get_monitoring_health():
    """Get monitoring integrations health"""
    try:
        monitoring = get_monitoring_manager()
        if not monitoring:
            return jsonify({'error': 'Monitoring manager not initialized'}), 503
        
        health_data = monitoring.get_monitoring_health()
        
        return jsonify({
            'health_data': health_data,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(
            "Error getting monitoring health",
            component=ComponentType.WEB_SERVER.value,
            exception=e
        )
        return jsonify({'error': 'Failed to get monitoring health'}), 500


@logging_dashboard.route('/api/admin/logging/metrics/send', methods=['POST'])
@login_required
def send_test_metric():
    """Send a test metric to monitoring systems"""
    try:
        monitoring = get_monitoring_manager()
        if not monitoring:
            return jsonify({'error': 'Monitoring manager not initialized'}), 503
        
        # Send test metric
        monitoring.send_metric('test.dashboard_metric', 1, tags={
            'source': 'logging_dashboard',
            'user': str(getattr(g, 'jwt_claims', {}).get('user_id', 'admin'))
        })
        
        # Send test event
        monitoring.send_event(
            'Test Event from Logging Dashboard',
            'This is a test event sent from the logging dashboard',
            level='INFO',
            tags={'source': 'logging_dashboard'}
        )
        
        logger.info(
            "Test metrics sent via dashboard",
            component=ComponentType.WEB_SERVER.value
        )
        
        return jsonify({'success': True, 'message': 'Test metrics sent successfully'})
        
    except Exception as e:
        logger.error(
            "Error sending test metrics",
            component=ComponentType.WEB_SERVER.value,
            exception=e
        )
        return jsonify({'error': 'Failed to send test metrics'}), 500


@logging_dashboard.route('/api/admin/logging/export/patterns')
@login_required
def export_pattern_data():
    """Export pattern detection data"""
    try:
        hours = request.args.get('hours', 24, type=int)
        format_type = request.args.get('format', 'json')
        
        aggregator = get_log_aggregator()
        if not aggregator:
            return jsonify({'error': 'Log aggregator not initialized'}), 503
        
        recent_patterns = aggregator.get_recent_patterns(hours)
        
        if format_type == 'json':
            # Convert patterns to JSON-serializable format
            patterns_data = []
            for pattern in recent_patterns:
                patterns_data.append({
                    'alert_id': pattern.alert_id,
                    'pattern_type': pattern.pattern_type.value,
                    'severity': pattern.severity.value,
                    'timestamp': pattern.timestamp.isoformat(),
                    'occurrence_count': pattern.occurrence_count,
                    'time_span_minutes': pattern.time_span_minutes,
                    'maritime_context': pattern.maritime_context,
                    'impact_assessment': pattern.impact_assessment,
                    'recommendations': pattern.recommendations
                })
            
            response_data = {
                'export_timestamp': datetime.now(timezone.utc).isoformat(),
                'time_period_hours': hours,
                'pattern_count': len(patterns_data),
                'patterns': patterns_data
            }
            
            return jsonify(response_data)
        
        else:
            return jsonify({'error': 'Unsupported export format'}), 400
        
    except Exception as e:
        logger.error(
            "Error exporting pattern data",
            component=ComponentType.WEB_SERVER.value,
            exception=e
        )
        return jsonify({'error': 'Failed to export pattern data'}), 500


@logging_dashboard.route('/api/admin/logging/realtime/stream')
@login_required
def realtime_log_stream():
    """Get real-time log stream data (for SSE or WebSocket)"""
    try:
        # This would typically be implemented with Server-Sent Events (SSE)
        # or WebSockets for real-time streaming
        
        # For now, return recent log entries
        aggregator = get_log_aggregator()
        if not aggregator:
            return jsonify({'error': 'Log aggregator not initialized'}), 503
        
        # Get recent log entries (last 50)
        recent_logs = list(aggregator.log_buffer)[-50:] if aggregator.log_buffer else []
        
        return jsonify({
            'logs': recent_logs,
            'count': len(recent_logs),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(
            "Error getting realtime log stream",
            component=ComponentType.WEB_SERVER.value,
            exception=e
        )
        return jsonify({'error': 'Failed to get log stream'}), 500


@logging_dashboard.route('/api/admin/logging/config/alerts')
@login_required
def get_alert_configuration():
    """Get alert system configuration"""
    try:
        alert_system = get_maritime_alert_system()
        if not alert_system:
            return jsonify({'error': 'Alert system not initialized'}), 503
        
        # Get alert rules configuration
        rules_config = {}
        for rule_id, rule in alert_system.rules.items():
            rules_config[rule_id] = {
                'name': rule.name,
                'alert_type': rule.alert_type.value,
                'priority': rule.priority.value,
                'enabled': rule.enabled,
                'throttle_minutes': rule.throttle_minutes,
                'channels': [ch.value for ch in rule.channels],
                'conditions': rule.conditions,
                'escalation_rules': rule.escalation_rules,
                'maritime_context_required': rule.maritime_context_required,
                'business_hours_only': rule.business_hours_only,
                'tags': rule.tags
            }
        
        return jsonify({
            'alert_rules': rules_config,
            'system_stats': alert_system.stats,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(
            "Error getting alert configuration",
            component=ComponentType.WEB_SERVER.value,
            exception=e
        )
        return jsonify({'error': 'Failed to get alert configuration'}), 500


@logging_dashboard.route('/api/admin/logging/performance')
@login_required
def get_performance_metrics():
    """Get logging system performance metrics"""
    try:
        performance_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'components': {}
        }
        
        # Aggregator performance
        aggregator = get_log_aggregator()
        if aggregator:
            performance_data['components']['aggregator'] = {
                'logs_processed_total': aggregator.processing_stats['logs_processed'],
                'patterns_detected_total': aggregator.processing_stats['patterns_detected'],
                'alerts_generated_total': aggregator.processing_stats['alerts_generated'],
                'processing_errors_total': aggregator.processing_stats['processing_errors'],
                'last_processing_time': (
                    aggregator.processing_stats['last_processing_time'].isoformat()
                    if aggregator.processing_stats['last_processing_time'] else None
                ),
                'buffer_utilization': len(aggregator.log_buffer) / aggregator.log_buffer.maxlen * 100,
                'active_pattern_tracking': len(aggregator.active_patterns)
            }
        
        # Monitoring system performance
        monitoring = get_monitoring_manager()
        if monitoring:
            performance_data['components']['monitoring'] = {
                'maritime_metrics': monitoring.maritime_metrics,
                'performance_counters': monitoring.performance_counters,
                'providers_active': len([p for p in monitoring.providers.values() if p.is_active])
            }
        
        # Alert system performance
        alert_system = get_maritime_alert_system()
        if alert_system:
            performance_data['components']['alerts'] = alert_system.stats.copy()
        
        # Retention system performance
        retention_manager = get_log_retention_manager()
        if retention_manager:
            performance_data['components']['retention'] = {
                'files_archived': retention_manager.stats['files_archived'],
                'files_deleted': retention_manager.stats['files_deleted'],
                'bytes_compressed': retention_manager.stats['bytes_compressed'],
                'compression_ratio': retention_manager.stats['compression_ratio'],
                'storage_saved_bytes': retention_manager.stats['storage_saved_bytes'],
                'last_cleanup': (
                    retention_manager.stats['last_cleanup'].isoformat()
                    if retention_manager.stats['last_cleanup'] else None
                )
            }
        
        return jsonify(performance_data)
        
    except Exception as e:
        logger.error(
            "Error getting performance metrics",
            component=ComponentType.WEB_SERVER.value,
            exception=e
        )
        return jsonify({'error': 'Failed to get performance metrics'}), 500