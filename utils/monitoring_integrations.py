"""
Real-time Monitoring Integrations for Stevedores Dashboard 3.0
External service integrations for DataDog, New Relic, LogTail, and other monitoring platforms
Cost-effective monitoring with maritime operations focus
"""

import os
import json
import time
import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import requests
from queue import Queue, Empty
import hashlib
import hmac
import base64

# Import structured logging components
from .structured_logger import get_structured_logger, LogLevel, ComponentType
from .log_aggregator import get_log_aggregator, PatternSeverity, MaritimePatternType


class MonitoringProvider(Enum):
    """Supported monitoring service providers"""
    DATADOG = "datadog"
    NEW_RELIC = "new_relic"
    LOGTAIL = "logtail"
    LOGFLARE = "logflare"
    PAPERTRAIL = "papertrail"
    CLOUDWATCH = "cloudwatch"
    GRAFANA = "grafana"
    PROMETHEUS = "prometheus"
    WEBHOOK = "webhook"


class MetricType(Enum):
    """Types of metrics to send"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MonitoringConfig:
    """Configuration for monitoring service"""
    provider: MonitoringProvider
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    app_name: str = "stevedores-dashboard"
    environment: str = "production"
    enabled: bool = True
    batch_size: int = 100
    flush_interval: int = 30
    retry_attempts: int = 3
    timeout: int = 10
    tags: Dict[str, str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


@dataclass
class MonitoringMetric:
    """Monitoring metric data structure"""
    name: str
    value: Union[int, float]
    metric_type: MetricType
    timestamp: Optional[datetime] = None
    tags: Optional[Dict[str, str]] = None
    unit: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
        if self.tags is None:
            self.tags = {}


@dataclass
class MonitoringEvent:
    """Monitoring event/alert data structure"""
    title: str
    message: str
    level: str
    timestamp: Optional[datetime] = None
    source: str = "stevedores-dashboard"
    tags: Optional[Dict[str, str]] = None
    aggregation_key: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
        if self.tags is None:
            self.tags = {}


class BaseMonitoringProvider:
    """Base class for monitoring providers"""
    
    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.logger = get_structured_logger()
        self.metrics_queue = Queue(maxsize=5000)
        self.events_queue = Queue(maxsize=1000)
        self.is_active = False
        self.processing_thread = None
        
        # Statistics
        self.stats = {
            'metrics_sent': 0,
            'events_sent': 0,
            'errors': 0,
            'last_flush': None
        }
    
    def start(self):
        """Start monitoring provider"""
        if self.is_active or not self.config.enabled:
            return
        
        self.is_active = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        
        self.logger.info(
            f"Monitoring provider started: {self.config.provider.value}",
            component=ComponentType.HEALTH_MONITOR.value,
            provider=self.config.provider.value
        )
    
    def stop(self):
        """Stop monitoring provider"""
        self.is_active = False
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=5)
        
        # Flush remaining data
        self._flush_metrics()
        self._flush_events()
    
    def send_metric(self, metric: MonitoringMetric):
        """Queue metric for sending"""
        if not self.config.enabled:
            return
        
        try:
            self.metrics_queue.put_nowait(metric)
        except:
            # Queue full, drop metric
            self.stats['errors'] += 1
    
    def send_event(self, event: MonitoringEvent):
        """Queue event for sending"""
        if not self.config.enabled:
            return
        
        try:
            self.events_queue.put_nowait(event)
        except:
            # Queue full, drop event
            self.stats['errors'] += 1
    
    def _processing_loop(self):
        """Main processing loop"""
        while self.is_active:
            try:
                # Flush data at intervals
                time.sleep(self.config.flush_interval)
                self._flush_metrics()
                self._flush_events()
                self.stats['last_flush'] = datetime.now(timezone.utc)
                
            except Exception as e:
                self.logger.error(
                    f"Error in {self.config.provider.value} processing loop",
                    component=ComponentType.HEALTH_MONITOR.value,
                    provider=self.config.provider.value,
                    exception=e
                )
                self.stats['errors'] += 1
                time.sleep(5)
    
    def _flush_metrics(self):
        """Flush queued metrics"""
        metrics = []
        try:
            while len(metrics) < self.config.batch_size:
                metric = self.metrics_queue.get_nowait()
                metrics.append(metric)
        except Empty:
            pass
        
        if metrics:
            self._send_metrics_batch(metrics)
    
    def _flush_events(self):
        """Flush queued events"""
        events = []
        try:
            while len(events) < self.config.batch_size:
                event = self.events_queue.get_nowait()
                events.append(event)
        except Empty:
            pass
        
        if events:
            self._send_events_batch(events)
    
    def _send_metrics_batch(self, metrics: List[MonitoringMetric]):
        """Send batch of metrics - to be implemented by subclasses"""
        raise NotImplementedError
    
    def _send_events_batch(self, events: List[MonitoringEvent]):
        """Send batch of events - to be implemented by subclasses"""
        raise NotImplementedError


class DataDogProvider(BaseMonitoringProvider):
    """DataDog monitoring provider"""
    
    def __init__(self, config: MonitoringConfig):
        super().__init__(config)
        self.api_key = config.api_key or os.getenv('DATADOG_API_KEY')
        self.site = config.tags.get('site', os.getenv('DATADOG_SITE', 'datadoghq.com'))
        self.base_url = f"https://api.{self.site}"
    
    def _send_metrics_batch(self, metrics: List[MonitoringMetric]):
        """Send metrics to DataDog"""
        try:
            series = []
            for metric in metrics:
                # Add common tags
                tags = {**self.config.tags, **metric.tags}
                tag_list = [f"{k}:{v}" for k, v in tags.items()]
                
                series.append({
                    "metric": f"stevedores.{metric.name}",
                    "points": [[int(metric.timestamp.timestamp()), metric.value]],
                    "type": self._convert_metric_type(metric.metric_type),
                    "tags": tag_list,
                    "unit": metric.unit
                })
            
            payload = {"series": series}
            
            headers = {
                "Content-Type": "application/json",
                "DD-API-KEY": self.api_key
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/series",
                json=payload,
                headers=headers,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            self.stats['metrics_sent'] += len(metrics)
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(
                "Failed to send metrics to DataDog",
                component=ComponentType.HEALTH_MONITOR.value,
                provider="datadog",
                metrics_count=len(metrics),
                exception=e
            )
    
    def _send_events_batch(self, events: List[MonitoringEvent]):
        """Send events to DataDog"""
        try:
            for event in events:
                # Add common tags
                tags = {**self.config.tags, **event.tags}
                tag_list = [f"{k}:{v}" for k, v in tags.items()]
                
                payload = {
                    "title": event.title,
                    "text": event.message,
                    "alert_type": self._convert_alert_level(event.level),
                    "source_type_name": "stevedores-dashboard",
                    "tags": tag_list,
                    "aggregation_key": event.aggregation_key
                }
                
                headers = {
                    "Content-Type": "application/json",
                    "DD-API-KEY": self.api_key
                }
                
                response = requests.post(
                    f"{self.base_url}/api/v1/events",
                    json=payload,
                    headers=headers,
                    timeout=self.config.timeout
                )
                response.raise_for_status()
                
                self.stats['events_sent'] += 1
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(
                "Failed to send events to DataDog",
                component=ComponentType.HEALTH_MONITOR.value,
                provider="datadog",
                events_count=len(events),
                exception=e
            )
    
    def _convert_metric_type(self, metric_type: MetricType) -> str:
        """Convert metric type to DataDog format"""
        mapping = {
            MetricType.COUNTER: "count",
            MetricType.GAUGE: "gauge",
            MetricType.HISTOGRAM: "histogram",
            MetricType.TIMER: "gauge"
        }
        return mapping.get(metric_type, "gauge")
    
    def _convert_alert_level(self, level: str) -> str:
        """Convert alert level to DataDog format"""
        mapping = {
            "DEBUG": "info",
            "INFO": "info",
            "WARNING": "warning",
            "ERROR": "error",
            "CRITICAL": "error",
            "MARITIME_ALERT": "warning",
            "SECURITY": "error"
        }
        return mapping.get(level.upper(), "info")


class NewRelicProvider(BaseMonitoringProvider):
    """New Relic monitoring provider"""
    
    def __init__(self, config: MonitoringConfig):
        super().__init__(config)
        self.license_key = config.api_key or os.getenv('NEW_RELIC_LICENSE_KEY')
        self.base_url = "https://metric-api.newrelic.com"
    
    def _send_metrics_batch(self, metrics: List[MonitoringMetric]):
        """Send metrics to New Relic"""
        try:
            common_attributes = {
                "service.name": self.config.app_name,
                "environment": self.config.environment,
                **self.config.tags
            }
            
            payload = [{
                "common": {
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "attributes": common_attributes
                },
                "metrics": []
            }]
            
            for metric in metrics:
                metric_data = {
                    "name": f"stevedores.{metric.name}",
                    "type": self._convert_metric_type(metric.metric_type),
                    "value": metric.value,
                    "timestamp": int(metric.timestamp.timestamp() * 1000),
                    "attributes": {**common_attributes, **metric.tags}
                }
                payload[0]["metrics"].append(metric_data)
            
            headers = {
                "Content-Type": "application/json",
                "Api-Key": self.license_key
            }
            
            response = requests.post(
                f"{self.base_url}/metric/v1",
                json=payload,
                headers=headers,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            self.stats['metrics_sent'] += len(metrics)
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(
                "Failed to send metrics to New Relic",
                component=ComponentType.HEALTH_MONITOR.value,
                provider="new_relic",
                metrics_count=len(metrics),
                exception=e
            )
    
    def _send_events_batch(self, events: List[MonitoringEvent]):
        """Send events to New Relic"""
        try:
            for event in events:
                payload = {
                    "eventType": "StevedoresAlert",
                    "title": event.title,
                    "description": event.message,
                    "level": event.level,
                    "source": event.source,
                    "timestamp": int(event.timestamp.timestamp() * 1000),
                    **self.config.tags,
                    **event.tags
                }
                
                headers = {
                    "Content-Type": "application/json",
                    "Api-Key": self.license_key
                }
                
                response = requests.post(
                    "https://insights-collector.newrelic.com/v1/accounts/<ACCOUNT_ID>/events",
                    json=[payload],
                    headers=headers,
                    timeout=self.config.timeout
                )
                response.raise_for_status()
                
                self.stats['events_sent'] += 1
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(
                "Failed to send events to New Relic",
                component=ComponentType.HEALTH_MONITOR.value,
                provider="new_relic",
                events_count=len(events),
                exception=e
            )
    
    def _convert_metric_type(self, metric_type: MetricType) -> str:
        """Convert metric type to New Relic format"""
        mapping = {
            MetricType.COUNTER: "count",
            MetricType.GAUGE: "gauge",
            MetricType.HISTOGRAM: "summary",
            MetricType.TIMER: "gauge"
        }
        return mapping.get(metric_type, "gauge")


class LogTailProvider(BaseMonitoringProvider):
    """LogTail monitoring provider"""
    
    def __init__(self, config: MonitoringConfig):
        super().__init__(config)
        self.source_token = config.api_key or os.getenv('LOGTAIL_SOURCE_TOKEN')
        self.base_url = "https://in.logtail.com"
    
    def _send_metrics_batch(self, metrics: List[MonitoringMetric]):
        """Send metrics as structured logs to LogTail"""
        try:
            for metric in metrics:
                payload = {
                    "dt": metric.timestamp.isoformat(),
                    "level": "INFO",
                    "message": f"Metric: {metric.name}",
                    "metric_name": metric.name,
                    "metric_value": metric.value,
                    "metric_type": metric.metric_type.value,
                    "metric_unit": metric.unit,
                    "service": self.config.app_name,
                    "environment": self.config.environment,
                    **self.config.tags,
                    **metric.tags
                }
                
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.source_token}"
                }
                
                response = requests.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=self.config.timeout
                )
                response.raise_for_status()
                
                self.stats['metrics_sent'] += 1
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(
                "Failed to send metrics to LogTail",
                component=ComponentType.HEALTH_MONITOR.value,
                provider="logtail",
                metrics_count=len(metrics),
                exception=e
            )
    
    def _send_events_batch(self, events: List[MonitoringEvent]):
        """Send events to LogTail"""
        try:
            for event in events:
                payload = {
                    "dt": event.timestamp.isoformat(),
                    "level": event.level,
                    "message": f"[{event.title}] {event.message}",
                    "event_title": event.title,
                    "event_source": event.source,
                    "service": self.config.app_name,
                    "environment": self.config.environment,
                    **self.config.tags,
                    **event.tags
                }
                
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.source_token}"
                }
                
                response = requests.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=self.config.timeout
                )
                response.raise_for_status()
                
                self.stats['events_sent'] += 1
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(
                "Failed to send events to LogTail",
                component=ComponentType.HEALTH_MONITOR.value,
                provider="logtail",
                events_count=len(events),
                exception=e
            )


class WebhookProvider(BaseMonitoringProvider):
    """Generic webhook provider for custom integrations"""
    
    def __init__(self, config: MonitoringConfig):
        super().__init__(config)
        self.webhook_url = config.api_url or os.getenv('MONITORING_WEBHOOK_URL')
        self.webhook_secret = config.api_key or os.getenv('MONITORING_WEBHOOK_SECRET')
    
    def _send_metrics_batch(self, metrics: List[MonitoringMetric]):
        """Send metrics via webhook"""
        try:
            payload = {
                "type": "metrics",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": self.config.app_name,
                "environment": self.config.environment,
                "metrics": [
                    {
                        "name": metric.name,
                        "value": metric.value,
                        "type": metric.metric_type.value,
                        "timestamp": metric.timestamp.isoformat(),
                        "unit": metric.unit,
                        "tags": {**self.config.tags, **metric.tags}
                    }
                    for metric in metrics
                ]
            }
            
            headers = {"Content-Type": "application/json"}
            
            # Add signature if secret is provided
            if self.webhook_secret:
                signature = self._generate_signature(json.dumps(payload))
                headers["X-Webhook-Signature"] = signature
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=headers,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            self.stats['metrics_sent'] += len(metrics)
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(
                "Failed to send metrics via webhook",
                component=ComponentType.HEALTH_MONITOR.value,
                provider="webhook",
                metrics_count=len(metrics),
                exception=e
            )
    
    def _send_events_batch(self, events: List[MonitoringEvent]):
        """Send events via webhook"""
        try:
            payload = {
                "type": "events",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": self.config.app_name,
                "environment": self.config.environment,
                "events": [
                    {
                        "title": event.title,
                        "message": event.message,
                        "level": event.level,
                        "timestamp": event.timestamp.isoformat(),
                        "source": event.source,
                        "tags": {**self.config.tags, **event.tags}
                    }
                    for event in events
                ]
            }
            
            headers = {"Content-Type": "application/json"}
            
            # Add signature if secret is provided
            if self.webhook_secret:
                signature = self._generate_signature(json.dumps(payload))
                headers["X-Webhook-Signature"] = signature
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=headers,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            self.stats['events_sent'] += len(events)
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(
                "Failed to send events via webhook",
                component=ComponentType.HEALTH_MONITOR.value,
                provider="webhook",
                events_count=len(events),
                exception=e
            )
    
    def _generate_signature(self, payload: str) -> str:
        """Generate HMAC signature for webhook"""
        if not self.webhook_secret:
            return ""
        
        signature = hmac.new(
            self.webhook_secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"sha256={signature}"


class MonitoringManager:
    """Central manager for all monitoring integrations"""
    
    def __init__(self):
        self.providers: Dict[str, BaseMonitoringProvider] = {}
        self.logger = get_structured_logger()
        self.is_initialized = False
        
        # Maritime-specific metric tracking
        self.maritime_metrics = {
            'vessel_operations': 0,
            'cargo_operations': 0,
            'security_incidents': 0,
            'system_performance': 0,
            'sync_operations': 0
        }
        
        # Performance counters
        self.performance_counters = {
            'request_count': 0,
            'error_count': 0,
            'memory_usage': 0,
            'response_time': 0,
            'database_queries': 0
        }
    
    def initialize(self):
        """Initialize monitoring providers based on configuration"""
        if self.is_initialized:
            return
        
        environment = os.getenv('FLASK_ENV', 'production')
        app_name = os.getenv('SERVICE_NAME', 'stevedores-dashboard')
        
        common_tags = {
            'environment': environment,
            'version': os.getenv('DEPLOYMENT_VERSION', '3.0.6'),
            'service': 'maritime-operations'
        }
        
        # DataDog
        if os.getenv('DATADOG_API_KEY'):
            config = MonitoringConfig(
                provider=MonitoringProvider.DATADOG,
                api_key=os.getenv('DATADOG_API_KEY'),
                app_name=app_name,
                environment=environment,
                tags=common_tags
            )
            self.providers['datadog'] = DataDogProvider(config)
        
        # New Relic
        if os.getenv('NEW_RELIC_LICENSE_KEY'):
            config = MonitoringConfig(
                provider=MonitoringProvider.NEW_RELIC,
                api_key=os.getenv('NEW_RELIC_LICENSE_KEY'),
                app_name=app_name,
                environment=environment,
                tags=common_tags
            )
            self.providers['new_relic'] = NewRelicProvider(config)
        
        # LogTail
        if os.getenv('LOGTAIL_SOURCE_TOKEN'):
            config = MonitoringConfig(
                provider=MonitoringProvider.LOGTAIL,
                api_key=os.getenv('LOGTAIL_SOURCE_TOKEN'),
                app_name=app_name,
                environment=environment,
                tags=common_tags
            )
            self.providers['logtail'] = LogTailProvider(config)
        
        # Webhook
        if os.getenv('MONITORING_WEBHOOK_URL'):
            config = MonitoringConfig(
                provider=MonitoringProvider.WEBHOOK,
                api_url=os.getenv('MONITORING_WEBHOOK_URL'),
                api_key=os.getenv('MONITORING_WEBHOOK_SECRET'),
                app_name=app_name,
                environment=environment,
                tags=common_tags
            )
            self.providers['webhook'] = WebhookProvider(config)
        
        # Start all providers
        for provider in self.providers.values():
            provider.start()
        
        self.is_initialized = True
        
        self.logger.info(
            "Monitoring integrations initialized",
            component=ComponentType.HEALTH_MONITOR.value,
            providers=list(self.providers.keys()),
            provider_count=len(self.providers)
        )
    
    def send_metric(self, name: str, value: Union[int, float], metric_type: MetricType = MetricType.GAUGE, tags: Dict[str, str] = None, unit: str = None):
        """Send metric to all configured providers"""
        if not self.is_initialized:
            self.initialize()
        
        metric = MonitoringMetric(
            name=name,
            value=value,
            metric_type=metric_type,
            tags=tags or {},
            unit=unit
        )
        
        for provider in self.providers.values():
            provider.send_metric(metric)
    
    def send_event(self, title: str, message: str, level: str = "INFO", tags: Dict[str, str] = None):
        """Send event to all configured providers"""
        if not self.is_initialized:
            self.initialize()
        
        event = MonitoringEvent(
            title=title,
            message=message,
            level=level,
            tags=tags or {}
        )
        
        for provider in self.providers.values():
            provider.send_event(event)
    
    def track_maritime_operation(self, operation_type: str, duration_ms: float, success: bool = True):
        """Track maritime operation metrics"""
        self.maritime_metrics[operation_type] = self.maritime_metrics.get(operation_type, 0) + 1
        
        # Send metrics
        self.send_metric(f"maritime.{operation_type}.count", 1, MetricType.COUNTER)
        self.send_metric(f"maritime.{operation_type}.duration", duration_ms, MetricType.TIMER, unit="milliseconds")
        
        if not success:
            self.send_metric(f"maritime.{operation_type}.errors", 1, MetricType.COUNTER)
    
    def track_performance_metric(self, metric_name: str, value: Union[int, float], threshold: Optional[float] = None):
        """Track system performance metrics"""
        self.performance_counters[metric_name] = value
        
        # Send metric
        self.send_metric(f"system.{metric_name}", value, MetricType.GAUGE)
        
        # Alert if threshold exceeded
        if threshold and value > threshold:
            self.send_event(
                title=f"Performance Alert: {metric_name}",
                message=f"{metric_name} value {value} exceeds threshold {threshold}",
                level="WARNING",
                tags={"metric": metric_name, "threshold_exceeded": "true"}
            )
    
    def track_pattern_alert(self, pattern_type: MaritimePatternType, severity: PatternSeverity, context: Dict[str, Any]):
        """Track pattern detection alerts"""
        # Send metrics
        self.send_metric("maritime.patterns.detected", 1, MetricType.COUNTER, tags={
            "pattern_type": pattern_type.value,
            "severity": severity.value
        })
        
        # Send alert event
        self.send_event(
            title=f"Maritime Pattern Alert: {pattern_type.value}",
            message=f"Pattern detected with {severity.value} severity",
            level="WARNING" if severity == PatternSeverity.WARNING else "ERROR",
            tags={
                "pattern_type": pattern_type.value,
                "severity": severity.value,
                **context
            }
        )
    
    def get_monitoring_health(self) -> Dict[str, Any]:
        """Get monitoring system health status"""
        provider_stats = {}
        for name, provider in self.providers.items():
            provider_stats[name] = {
                'active': provider.is_active,
                'metrics_sent': provider.stats['metrics_sent'],
                'events_sent': provider.stats['events_sent'],
                'errors': provider.stats['errors'],
                'last_flush': provider.stats['last_flush'].isoformat() if provider.stats['last_flush'] else None
            }
        
        return {
            'initialized': self.is_initialized,
            'providers': provider_stats,
            'maritime_metrics': self.maritime_metrics.copy(),
            'performance_counters': self.performance_counters.copy(),
            'health_status': 'healthy' if all(p.is_active for p in self.providers.values()) else 'degraded'
        }
    
    def shutdown(self):
        """Shutdown all monitoring providers"""
        for provider in self.providers.values():
            provider.stop()
        
        self.logger.info(
            "Monitoring integrations shutdown",
            component=ComponentType.HEALTH_MONITOR.value
        )


# Global monitoring manager instance
_monitoring_manager: Optional[MonitoringManager] = None


def init_monitoring_manager() -> MonitoringManager:
    """Initialize the global monitoring manager"""
    global _monitoring_manager
    
    if _monitoring_manager is None:
        _monitoring_manager = MonitoringManager()
        _monitoring_manager.initialize()
    
    return _monitoring_manager


def get_monitoring_manager() -> Optional[MonitoringManager]:
    """Get the global monitoring manager instance"""
    return _monitoring_manager


def configure_monitoring_middleware(app):
    """Configure Flask middleware for monitoring integration"""
    # Initialize monitoring
    monitoring = init_monitoring_manager()
    
    @app.before_request
    def before_request_monitoring():
        """Track request start"""
        import flask
        flask.g.request_start_time = time.time()
        monitoring.track_performance_metric('concurrent_requests', 1)
    
    @app.after_request
    def after_request_monitoring(response):
        """Track request completion"""
        if hasattr(flask.g, 'request_start_time'):
            duration_ms = (time.time() - flask.g.request_start_time) * 1000
            
            # Track response time
            monitoring.track_performance_metric('response_time', duration_ms, threshold=2000)
            
            # Track status codes
            monitoring.send_metric('http.requests', 1, MetricType.COUNTER, tags={
                'status_code': str(response.status_code),
                'method': flask.request.method,
                'endpoint': flask.request.endpoint or 'unknown'
            })
            
            # Track errors
            if response.status_code >= 400:
                monitoring.send_metric('http.errors', 1, MetricType.COUNTER, tags={
                    'status_code': str(response.status_code)
                })
        
        return response
    
    # Integrate with log aggregator
    aggregator = get_log_aggregator()
    if aggregator:
        def pattern_alert_callback(pattern_match):
            monitoring.track_pattern_alert(
                pattern_match.pattern_type,
                pattern_match.severity,
                pattern_match.maritime_context
            )
        
        # This would need to be implemented in the aggregator
        # aggregator.add_pattern_callback(pattern_alert_callback)
    
    return monitoring


# Export public interface
__all__ = [
    'MonitoringProvider', 'MetricType', 'MonitoringConfig', 'MonitoringMetric',
    'MonitoringEvent', 'MonitoringManager', 'init_monitoring_manager',
    'get_monitoring_manager', 'configure_monitoring_middleware'
]