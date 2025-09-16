"""
Maritime-Specific Alert System for Stevedores Dashboard 3.0
Intelligent alerting with maritime operations context and escalation rules
"""

import os
import time
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Set, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import threading
from collections import defaultdict, deque
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Import components
from .structured_logger import get_structured_logger, LogLevel, ComponentType, MaritimeOperationType
from .log_aggregator import MaritimePatternType, PatternSeverity
from .monitoring_integrations import get_monitoring_manager


class AlertPriority(Enum):
    """Alert priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertChannel(Enum):
    """Alert delivery channels"""
    LOG = "log"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    PUSH_NOTIFICATION = "push"
    SLACK = "slack"
    TEAMS = "teams"
    PAGERDUTY = "pagerduty"


class MaritimeAlertType(Enum):
    """Maritime-specific alert types"""
    VESSEL_EMERGENCY = "vessel_emergency"
    CARGO_SECURITY = "cargo_security"
    ENVIRONMENTAL_VIOLATION = "environmental_violation"
    PORT_SAFETY = "port_safety"
    CUSTOMS_COMPLIANCE = "customs_compliance"
    EQUIPMENT_CRITICAL = "equipment_critical"
    WEATHER_HAZARD = "weather_hazard"
    SECURITY_BREACH = "security_breach"
    SYSTEM_FAILURE = "system_failure"
    DATA_INTEGRITY = "data_integrity"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    REGULATORY_COMPLIANCE = "regulatory_compliance"


@dataclass
class AlertRule:
    """Alert rule configuration"""
    rule_id: str
    name: str
    alert_type: MaritimeAlertType
    priority: AlertPriority
    conditions: Dict[str, Any]
    channels: List[AlertChannel]
    enabled: bool = True
    throttle_minutes: int = 15
    escalation_rules: List[Dict[str, Any]] = field(default_factory=list)
    maritime_context_required: bool = True
    business_hours_only: bool = False
    tags: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        # Compile conditions for faster evaluation
        self.compiled_conditions = self._compile_conditions()
    
    def _compile_conditions(self) -> Dict[str, Any]:
        """Compile conditions for efficient evaluation"""
        compiled = {}
        
        for key, condition in self.conditions.items():
            if isinstance(condition, dict):
                if 'threshold' in condition:
                    compiled[key] = {
                        'type': 'threshold',
                        'operator': condition.get('operator', '>='),
                        'value': condition['threshold']
                    }
                elif 'pattern' in condition:
                    import re
                    compiled[key] = {
                        'type': 'pattern',
                        'regex': re.compile(condition['pattern'], re.IGNORECASE)
                    }
                elif 'values' in condition:
                    compiled[key] = {
                        'type': 'in_list',
                        'values': set(condition['values'])
                    }
            else:
                compiled[key] = {'type': 'equals', 'value': condition}
        
        return compiled


@dataclass
class AlertEvent:
    """Alert event data structure"""
    alert_id: str
    rule_id: str
    alert_type: MaritimeAlertType
    priority: AlertPriority
    title: str
    message: str
    timestamp: datetime
    maritime_context: Dict[str, Any]
    technical_context: Dict[str, Any]
    affected_systems: List[str]
    estimated_impact: str
    recommended_actions: List[str]
    escalation_level: int = 0
    acknowledgment_required: bool = False
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'alert_id': self.alert_id,
            'rule_id': self.rule_id,
            'alert_type': self.alert_type.value,
            'priority': self.priority.value,
            'title': self.title,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'maritime_context': self.maritime_context,
            'technical_context': self.technical_context,
            'affected_systems': self.affected_systems,
            'estimated_impact': self.estimated_impact,
            'recommended_actions': self.recommended_actions,
            'escalation_level': self.escalation_level,
            'acknowledgment_required': self.acknowledgment_required,
            'acknowledged': self.acknowledged,
            'acknowledged_by': self.acknowledged_by,
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'resolved': self.resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'tags': self.tags
        }


class MaritimeAlertSystem:
    """Comprehensive maritime alert system"""
    
    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, AlertEvent] = {}
        self.alert_history = deque(maxlen=10000)  # Store recent alerts
        self.throttle_cache: Dict[str, datetime] = {}
        
        # Channel handlers
        self.channel_handlers: Dict[AlertChannel, Callable] = {
            AlertChannel.LOG: self._send_log_alert,
            AlertChannel.EMAIL: self._send_email_alert,
            AlertChannel.WEBHOOK: self._send_webhook_alert,
        }
        
        # Performance tracking
        self.stats = {
            'alerts_generated': 0,
            'alerts_sent': 0,
            'alerts_acknowledged': 0,
            'alerts_resolved': 0,
            'channel_failures': defaultdict(int),
            'rule_triggers': defaultdict(int)
        }
        
        self.logger = get_structured_logger()
        self.lock = threading.Lock()
        
        # Initialize default rules
        self._initialize_default_rules()
        
        # Start background tasks
        self._start_background_tasks()
    
    def _initialize_default_rules(self):
        """Initialize default maritime alert rules"""
        
        # Vessel Emergency Alerts
        self.add_rule(AlertRule(
            rule_id="vessel_emergency_001",
            name="Vessel Emergency Situation",
            alert_type=MaritimeAlertType.VESSEL_EMERGENCY,
            priority=AlertPriority.EMERGENCY,
            conditions={
                'maritime_operation': {'values': [
                    MaritimeOperationType.EMERGENCY_RESPONSE.value
                ]},
                'severity': {'values': ['CRITICAL', 'EMERGENCY']}
            },
            channels=[AlertChannel.LOG, AlertChannel.EMAIL, AlertChannel.WEBHOOK],
            throttle_minutes=0,  # No throttling for emergencies
            escalation_rules=[
                {'after_minutes': 5, 'channels': [AlertChannel.SMS]},
                {'after_minutes': 15, 'channels': [AlertChannel.PAGERDUTY]}
            ],
            acknowledgment_required=True
        ))
        
        # Security Breach Alerts
        self.add_rule(AlertRule(
            rule_id="security_breach_001",
            name="Maritime Security Breach",
            alert_type=MaritimeAlertType.SECURITY_BREACH,
            priority=AlertPriority.CRITICAL,
            conditions={
                'pattern_type': {'values': [
                    MaritimePatternType.SECURITY_BREACH.value,
                    MaritimePatternType.AUTHENTICATION_ANOMALY.value
                ]},
                'level': {'values': ['SECURITY', 'CRITICAL']}
            },
            channels=[AlertChannel.LOG, AlertChannel.EMAIL, AlertChannel.WEBHOOK],
            throttle_minutes=5,
            escalation_rules=[
                {'after_minutes': 10, 'priority': AlertPriority.EMERGENCY}
            ],
            acknowledgment_required=True
        ))
        
        # Environmental Violation Alerts
        self.add_rule(AlertRule(
            rule_id="environmental_001",
            name="Environmental Compliance Violation",
            alert_type=MaritimeAlertType.ENVIRONMENTAL_VIOLATION,
            priority=AlertPriority.HIGH,
            conditions={
                'pattern_type': {'values': [MaritimePatternType.ENVIRONMENTAL_VIOLATION.value]},
                'compliance_flags': {'pattern': r'.*environmental.*|.*marpol.*'}
            },
            channels=[AlertChannel.LOG, AlertChannel.EMAIL],
            throttle_minutes=10,
            escalation_rules=[
                {'after_minutes': 30, 'priority': AlertPriority.CRITICAL}
            ]
        ))
        
        # Cargo Security Alerts
        self.add_rule(AlertRule(
            rule_id="cargo_security_001",
            name="Cargo Security Incident",
            alert_type=MaritimeAlertType.CARGO_SECURITY,
            priority=AlertPriority.HIGH,
            conditions={
                'pattern_type': {'values': [MaritimePatternType.CARGO_DISCREPANCY.value]},
                'severity': {'values': ['CRITICAL', 'HIGH']}
            },
            channels=[AlertChannel.LOG, AlertChannel.EMAIL],
            throttle_minutes=15,
            maritime_context_required=True
        ))
        
        # System Performance Alerts
        self.add_rule(AlertRule(
            rule_id="system_performance_001",
            name="Critical System Performance",
            alert_type=MaritimeAlertType.PERFORMANCE_DEGRADATION,
            priority=AlertPriority.HIGH,
            conditions={
                'memory_usage_mb': {'threshold': 400, 'operator': '>='},
                'duration_ms': {'threshold': 5000, 'operator': '>='}
            },
            channels=[AlertChannel.LOG, AlertChannel.EMAIL],
            throttle_minutes=10
        ))
        
        # Equipment Failure Alerts
        self.add_rule(AlertRule(
            rule_id="equipment_critical_001",
            name="Critical Equipment Failure",
            alert_type=MaritimeAlertType.EQUIPMENT_CRITICAL,
            priority=AlertPriority.CRITICAL,
            conditions={
                'pattern_type': {'values': [MaritimePatternType.EQUIPMENT_FAILURE.value]},
                'maritime_context': {'pattern': r'.*crane.*|.*berth.*|.*critical.*'}
            },
            channels=[AlertChannel.LOG, AlertChannel.EMAIL, AlertChannel.WEBHOOK],
            throttle_minutes=5
        ))
        
        # Data Integrity Alerts
        self.add_rule(AlertRule(
            rule_id="data_integrity_001",
            name="Data Integrity Issue",
            alert_type=MaritimeAlertType.DATA_INTEGRITY,
            priority=AlertPriority.MEDIUM,
            conditions={
                'pattern_type': {'values': [MaritimePatternType.SYNC_FAILURE.value]},
                'occurrence_count': {'threshold': 3, 'operator': '>='}
            },
            channels=[AlertChannel.LOG, AlertChannel.EMAIL],
            throttle_minutes=20
        ))
        
        self.logger.info(
            "Maritime alert rules initialized",
            component=ComponentType.HEALTH_MONITOR.value,
            rules_count=len(self.rules)
        )
    
    def add_rule(self, rule: AlertRule):
        """Add or update an alert rule"""
        with self.lock:
            self.rules[rule.rule_id] = rule
        
        self.logger.info(
            f"Alert rule added: {rule.name}",
            component=ComponentType.HEALTH_MONITOR.value,
            rule_id=rule.rule_id,
            alert_type=rule.alert_type.value,
            priority=rule.priority.value
        )
    
    def remove_rule(self, rule_id: str):
        """Remove an alert rule"""
        with self.lock:
            if rule_id in self.rules:
                del self.rules[rule_id]
                self.logger.info(
                    f"Alert rule removed: {rule_id}",
                    component=ComponentType.HEALTH_MONITOR.value,
                    rule_id=rule_id
                )
    
    def evaluate_event(self, event_data: Dict[str, Any]):
        """Evaluate event against all alert rules"""
        triggered_rules = []
        
        for rule_id, rule in self.rules.items():
            if not rule.enabled:
                continue
            
            if self._evaluate_rule_conditions(rule, event_data):
                # Check throttling
                if self._is_throttled(rule_id, rule.throttle_minutes):
                    continue
                
                # Check business hours if required
                if rule.business_hours_only and not self._is_business_hours():
                    continue
                
                triggered_rules.append(rule)
                self.stats['rule_triggers'][rule_id] += 1
        
        # Generate alerts for triggered rules
        for rule in triggered_rules:
            self._generate_alert(rule, event_data)
    
    def _evaluate_rule_conditions(self, rule: AlertRule, event_data: Dict[str, Any]) -> bool:
        """Evaluate if event data matches rule conditions"""
        try:
            for field_name, compiled_condition in rule.compiled_conditions.items():
                field_value = self._get_field_value(event_data, field_name)
                
                if not self._evaluate_condition(field_value, compiled_condition):
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(
                f"Error evaluating rule conditions: {rule.rule_id}",
                component=ComponentType.HEALTH_MONITOR.value,
                rule_id=rule.rule_id,
                exception=e
            )
            return False
    
    def _get_field_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """Get field value from nested dictionary using dot notation"""
        keys = field_path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value
    
    def _evaluate_condition(self, field_value: Any, condition: Dict[str, Any]) -> bool:
        """Evaluate individual condition"""
        if field_value is None:
            return False
        
        condition_type = condition['type']
        
        if condition_type == 'equals':
            return field_value == condition['value']
        
        elif condition_type == 'threshold':
            operator = condition['operator']
            threshold = condition['value']
            
            if operator == '>=':
                return float(field_value) >= threshold
            elif operator == '<=':
                return float(field_value) <= threshold
            elif operator == '>':
                return float(field_value) > threshold
            elif operator == '<':
                return float(field_value) < threshold
            elif operator == '==':
                return float(field_value) == threshold
        
        elif condition_type == 'pattern':
            return bool(condition['regex'].search(str(field_value)))
        
        elif condition_type == 'in_list':
            return field_value in condition['values']
        
        return False
    
    def _is_throttled(self, rule_id: str, throttle_minutes: int) -> bool:
        """Check if rule is throttled"""
        if throttle_minutes == 0:
            return False
        
        now = datetime.now(timezone.utc)
        last_trigger = self.throttle_cache.get(rule_id)
        
        if last_trigger is None:
            self.throttle_cache[rule_id] = now
            return False
        
        time_diff = (now - last_trigger).total_seconds() / 60
        
        if time_diff >= throttle_minutes:
            self.throttle_cache[rule_id] = now
            return False
        
        return True
    
    def _is_business_hours(self) -> bool:
        """Check if current time is within business hours"""
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()  # 0 = Monday, 6 = Sunday
        
        # Business hours: Monday-Friday, 8 AM - 6 PM
        return weekday < 5 and 8 <= hour < 18
    
    def _generate_alert(self, rule: AlertRule, event_data: Dict[str, Any]):
        """Generate alert event"""
        alert_id = f"alert_{int(time.time())}_{rule.rule_id}"
        
        # Extract maritime context
        maritime_context = event_data.get('maritime_context', {})
        if 'vessel_id' in event_data:
            maritime_context['vessel_id'] = event_data['vessel_id']
        if 'port_code' in event_data:
            maritime_context['port_code'] = event_data['port_code']
        
        # Generate contextual message
        title, message = self._generate_alert_message(rule, event_data, maritime_context)
        
        # Create alert event
        alert_event = AlertEvent(
            alert_id=alert_id,
            rule_id=rule.rule_id,
            alert_type=rule.alert_type,
            priority=rule.priority,
            title=title,
            message=message,
            timestamp=datetime.now(timezone.utc),
            maritime_context=maritime_context,
            technical_context={
                'triggering_event': event_data,
                'rule_name': rule.name,
                'conditions_met': rule.conditions
            },
            affected_systems=self._identify_affected_systems(event_data),
            estimated_impact=self._estimate_impact(rule.alert_type, event_data),
            recommended_actions=self._generate_recommendations(rule.alert_type, event_data),
            acknowledgment_required=rule.priority in [AlertPriority.CRITICAL, AlertPriority.EMERGENCY],
            tags={**rule.tags, **event_data.get('tags', {})}
        )
        
        # Store alert
        with self.lock:
            self.active_alerts[alert_id] = alert_event
            self.alert_history.append(alert_event)
        
        # Send alert through configured channels
        self._send_alert(alert_event, rule.channels)
        
        # Schedule escalations if configured
        if rule.escalation_rules:
            self._schedule_escalations(alert_event, rule.escalation_rules)
        
        self.stats['alerts_generated'] += 1
        
        self.logger.critical(
            f"Maritime alert generated: {title}",
            component=ComponentType.HEALTH_MONITOR.value,
            alert_id=alert_id,
            rule_id=rule.rule_id,
            alert_type=rule.alert_type.value,
            priority=rule.priority.value,
            maritime_context=maritime_context,
            **event_data.get('extra_fields', {})
        )
    
    def _generate_alert_message(self, rule: AlertRule, event_data: Dict[str, Any], maritime_context: Dict[str, Any]) -> tuple:
        """Generate contextual alert title and message"""
        alert_type = rule.alert_type
        
        # Base title and message
        title = f"{alert_type.value.replace('_', ' ').title()}"
        message = rule.name
        
        # Add maritime context
        if 'vessel_imo' in maritime_context:
            title += f" - Vessel {maritime_context['vessel_imo']}"
        elif 'vessel_id' in maritime_context:
            title += f" - Vessel ID {maritime_context['vessel_id']}"
        
        if 'berth_id' in maritime_context:
            title += f" at Berth {maritime_context['berth_id']}"
        
        # Add technical details
        if 'message' in event_data:
            message += f"\n\nDetails: {event_data['message']}"
        
        if 'duration_ms' in event_data:
            message += f"\nDuration: {event_data['duration_ms']}ms"
        
        if 'memory_usage_mb' in event_data:
            message += f"\nMemory Usage: {event_data['memory_usage_mb']}MB"
        
        return title, message
    
    def _identify_affected_systems(self, event_data: Dict[str, Any]) -> List[str]:
        """Identify affected systems from event data"""
        systems = []
        
        component = event_data.get('component', '')
        if component:
            systems.append(component)
        
        # Check for specific system indicators
        if 'database' in event_data.get('message', '').lower():
            systems.append('database')
        if 'redis' in event_data.get('message', '').lower():
            systems.append('cache')
        if 'memory' in event_data.get('message', '').lower():
            systems.append('memory_system')
        if 'sync' in event_data.get('message', '').lower():
            systems.append('sync_engine')
        
        return list(set(systems))
    
    def _estimate_impact(self, alert_type: MaritimeAlertType, event_data: Dict[str, Any]) -> str:
        """Estimate business impact of the alert"""
        impact_map = {
            MaritimeAlertType.VESSEL_EMERGENCY: "Critical operational disruption, safety concerns",
            MaritimeAlertType.CARGO_SECURITY: "Financial loss, compliance violations, customer disputes",
            MaritimeAlertType.ENVIRONMENTAL_VIOLATION: "Regulatory fines, environmental damage, reputation risk",
            MaritimeAlertType.PORT_SAFETY: "Safety hazards, operational delays, liability concerns",
            MaritimeAlertType.EQUIPMENT_CRITICAL: "Operational delays, safety concerns, maintenance costs",
            MaritimeAlertType.SECURITY_BREACH: "Data security risk, compliance violations, reputation damage",
            MaritimeAlertType.SYSTEM_FAILURE: "Service disruption, productivity loss, data integrity risk",
            MaritimeAlertType.PERFORMANCE_DEGRADATION: "User experience degradation, operational inefficiency",
        }
        
        return impact_map.get(alert_type, "Operational impact assessment required")
    
    def _generate_recommendations(self, alert_type: MaritimeAlertType, event_data: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if alert_type == MaritimeAlertType.VESSEL_EMERGENCY:
            recommendations.extend([
                "Immediately contact vessel master and port authority",
                "Activate emergency response procedures",
                "Ensure all safety protocols are followed",
                "Document incident for regulatory reporting"
            ])
        
        elif alert_type == MaritimeAlertType.SECURITY_BREACH:
            recommendations.extend([
                "Immediately review and secure affected accounts",
                "Conduct security audit and incident response",
                "Monitor for additional suspicious activity",
                "Update security measures and access controls"
            ])
        
        elif alert_type == MaritimeAlertType.PERFORMANCE_DEGRADATION:
            recommendations.extend([
                "Monitor system resources and performance metrics",
                "Review recent changes and deployments",
                "Consider scaling resources if necessary",
                "Investigate root cause and implement fixes"
            ])
        
        elif alert_type == MaritimeAlertType.ENVIRONMENTAL_VIOLATION:
            recommendations.extend([
                "Immediately investigate and contain violation source",
                "Contact environmental compliance officer",
                "Document incident for regulatory authorities",
                "Implement corrective and preventive measures"
            ])
        
        return recommendations
    
    def _send_alert(self, alert_event: AlertEvent, channels: List[AlertChannel]):
        """Send alert through specified channels"""
        for channel in channels:
            try:
                handler = self.channel_handlers.get(channel)
                if handler:
                    handler(alert_event)
                    self.stats['alerts_sent'] += 1
                else:
                    self.logger.warning(
                        f"No handler configured for channel: {channel.value}",
                        component=ComponentType.HEALTH_MONITOR.value,
                        alert_id=alert_event.alert_id
                    )
            except Exception as e:
                self.stats['channel_failures'][channel.value] += 1
                self.logger.error(
                    f"Failed to send alert via {channel.value}",
                    component=ComponentType.HEALTH_MONITOR.value,
                    alert_id=alert_event.alert_id,
                    channel=channel.value,
                    exception=e
                )
    
    def _send_log_alert(self, alert_event: AlertEvent):
        """Send alert via logging"""
        self.logger.critical(
            f"MARITIME ALERT: {alert_event.title}",
            component=ComponentType.HEALTH_MONITOR.value,
            alert_id=alert_event.alert_id,
            alert_type=alert_event.alert_type.value,
            priority=alert_event.priority.value,
            message=alert_event.message,
            maritime_context=alert_event.maritime_context,
            recommended_actions=alert_event.recommended_actions,
            estimated_impact=alert_event.estimated_impact
        )
    
    def _send_email_alert(self, alert_event: AlertEvent):
        """Send alert via email"""
        try:
            smtp_server = os.getenv('SMTP_SERVER', 'localhost')
            smtp_port = int(os.getenv('SMTP_PORT', '587'))
            smtp_username = os.getenv('SMTP_USERNAME')
            smtp_password = os.getenv('SMTP_PASSWORD')
            from_email = os.getenv('ALERT_FROM_EMAIL', 'alerts@stevedores-dashboard.com')
            to_emails = os.getenv('ALERT_TO_EMAILS', '').split(',')
            
            if not to_emails or not to_emails[0]:
                return
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = f"[{alert_event.priority.value.upper()}] {alert_event.title}"
            
            # Email body
            body = f"""
Maritime Alert Notification

Alert ID: {alert_event.alert_id}
Type: {alert_event.alert_type.value}
Priority: {alert_event.priority.value}
Timestamp: {alert_event.timestamp.isoformat()}

Message:
{alert_event.message}

Maritime Context:
{json.dumps(alert_event.maritime_context, indent=2)}

Estimated Impact:
{alert_event.estimated_impact}

Recommended Actions:
{chr(10).join(f"- {action}" for action in alert_event.recommended_actions)}

Affected Systems:
{', '.join(alert_event.affected_systems)}

---
This is an automated alert from Stevedores Dashboard 3.0
"""
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if smtp_username and smtp_password:
                    server.starttls()
                    server.login(smtp_username, smtp_password)
                server.send_message(msg)
                
        except Exception as e:
            self.logger.error(
                "Failed to send email alert",
                component=ComponentType.HEALTH_MONITOR.value,
                alert_id=alert_event.alert_id,
                exception=e
            )
    
    def _send_webhook_alert(self, alert_event: AlertEvent):
        """Send alert via webhook"""
        try:
            webhook_url = os.getenv('ALERT_WEBHOOK_URL')
            if not webhook_url:
                return
            
            import requests
            
            payload = {
                'alert_id': alert_event.alert_id,
                'type': 'maritime_alert',
                'priority': alert_event.priority.value,
                'title': alert_event.title,
                'message': alert_event.message,
                'timestamp': alert_event.timestamp.isoformat(),
                'maritime_context': alert_event.maritime_context,
                'estimated_impact': alert_event.estimated_impact,
                'recommended_actions': alert_event.recommended_actions,
                'affected_systems': alert_event.affected_systems
            }
            
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
        except Exception as e:
            self.logger.error(
                "Failed to send webhook alert",
                component=ComponentType.HEALTH_MONITOR.value,
                alert_id=alert_event.alert_id,
                exception=e
            )
    
    def _schedule_escalations(self, alert_event: AlertEvent, escalation_rules: List[Dict[str, Any]]):
        """Schedule alert escalations"""
        def escalate_alert():
            for escalation in escalation_rules:
                time.sleep(escalation['after_minutes'] * 60)
                
                # Check if alert is still active and not resolved
                if (alert_event.alert_id in self.active_alerts and 
                    not self.active_alerts[alert_event.alert_id].resolved):
                    
                    # Apply escalation
                    if 'priority' in escalation:
                        alert_event.priority = AlertPriority(escalation['priority'])
                        alert_event.escalation_level += 1
                    
                    if 'channels' in escalation:
                        self._send_alert(alert_event, [AlertChannel(ch) for ch in escalation['channels']])
                    
                    self.logger.critical(
                        f"Alert escalated: {alert_event.title}",
                        component=ComponentType.HEALTH_MONITOR.value,
                        alert_id=alert_event.alert_id,
                        escalation_level=alert_event.escalation_level,
                        new_priority=alert_event.priority.value
                    )
        
        # Start escalation thread
        escalation_thread = threading.Thread(target=escalate_alert, daemon=True)
        escalation_thread.start()
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert"""
        with self.lock:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.acknowledged = True
                alert.acknowledged_by = acknowledged_by
                alert.acknowledged_at = datetime.now(timezone.utc)
                
                self.stats['alerts_acknowledged'] += 1
                
                self.logger.info(
                    f"Alert acknowledged: {alert.title}",
                    component=ComponentType.HEALTH_MONITOR.value,
                    alert_id=alert_id,
                    acknowledged_by=acknowledged_by
                )
                
                return True
        
        return False
    
    def resolve_alert(self, alert_id: str, resolved_by: str = None) -> bool:
        """Resolve an alert"""
        with self.lock:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.resolved = True
                alert.resolved_at = datetime.now(timezone.utc)
                
                # Remove from active alerts
                del self.active_alerts[alert_id]
                
                self.stats['alerts_resolved'] += 1
                
                self.logger.info(
                    f"Alert resolved: {alert.title}",
                    component=ComponentType.HEALTH_MONITOR.value,
                    alert_id=alert_id,
                    resolved_by=resolved_by
                )
                
                return True
        
        return False
    
    def get_active_alerts(self, priority_filter: Optional[AlertPriority] = None) -> List[AlertEvent]:
        """Get active alerts"""
        with self.lock:
            alerts = list(self.active_alerts.values())
            
            if priority_filter:
                alerts = [a for a in alerts if a.priority == priority_filter]
            
            # Sort by priority and timestamp
            priority_order = {
                AlertPriority.EMERGENCY: 0,
                AlertPriority.CRITICAL: 1,
                AlertPriority.HIGH: 2,
                AlertPriority.MEDIUM: 3,
                AlertPriority.LOW: 4
            }
            
            alerts.sort(key=lambda a: (priority_order[a.priority], a.timestamp), reverse=True)
            return alerts
    
    def get_alert_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get alert system statistics"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        recent_alerts = [
            alert for alert in self.alert_history
            if alert.timestamp > cutoff_time
        ]
        
        # Count by type and priority
        type_counts = defaultdict(int)
        priority_counts = defaultdict(int)
        
        for alert in recent_alerts:
            type_counts[alert.alert_type.value] += 1
            priority_counts[alert.priority.value] += 1
        
        return {
            'time_period_hours': hours,
            'total_alerts': len(recent_alerts),
            'active_alerts': len(self.active_alerts),
            'alerts_by_type': dict(type_counts),
            'alerts_by_priority': dict(priority_counts),
            'acknowledgment_rate': (
                self.stats['alerts_acknowledged'] / max(1, self.stats['alerts_generated']) * 100
            ),
            'resolution_rate': (
                self.stats['alerts_resolved'] / max(1, self.stats['alerts_generated']) * 100
            ),
            'channel_failures': dict(self.stats['channel_failures']),
            'top_triggered_rules': dict(
                sorted(self.stats['rule_triggers'].items(), key=lambda x: x[1], reverse=True)[:5]
            )
        }
    
    def _start_background_tasks(self):
        """Start background maintenance tasks"""
        def cleanup_task():
            while True:
                try:
                    # Clean up old throttle cache entries
                    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
                    
                    with self.lock:
                        self.throttle_cache = {
                            k: v for k, v in self.throttle_cache.items()
                            if v > cutoff_time
                        }
                    
                    time.sleep(3600)  # Run every hour
                    
                except Exception as e:
                    self.logger.error(
                        "Error in alert system cleanup task",
                        component=ComponentType.HEALTH_MONITOR.value,
                        exception=e
                    )
                    time.sleep(60)
        
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()


# Global alert system instance
_maritime_alert_system: Optional[MaritimeAlertSystem] = None


def init_maritime_alert_system() -> MaritimeAlertSystem:
    """Initialize the global maritime alert system"""
    global _maritime_alert_system
    
    if _maritime_alert_system is None:
        _maritime_alert_system = MaritimeAlertSystem()
    
    return _maritime_alert_system


def get_maritime_alert_system() -> Optional[MaritimeAlertSystem]:
    """Get the global maritime alert system instance"""
    return _maritime_alert_system


def configure_alert_integration(app):
    """Configure Flask app with alert system integration"""
    # Initialize alert system
    alert_system = init_maritime_alert_system()
    
    # Hook into log aggregator for pattern-based alerts
    from .log_aggregator import get_log_aggregator
    aggregator = get_log_aggregator()
    
    if aggregator:
        # Override pattern match handler to trigger alerts
        original_generate_alert = aggregator._generate_pattern_alert
        
        def enhanced_generate_alert(pattern_type, pattern, matches, timestamp):
            # Call original method
            result = original_generate_alert(pattern_type, pattern, matches, timestamp)
            
            # Trigger alert system evaluation
            event_data = {
                'pattern_type': pattern_type.value,
                'severity': pattern.severity.value,
                'occurrence_count': len(matches),
                'timestamp': timestamp.isoformat(),
                'maritime_context': {},
                'message': f"Pattern detected: {pattern_type.value}",
                'compliance_flags': pattern.compliance_flags
            }
            
            # Extract maritime context from matches
            for match in matches:
                log_entry = match.get('log_entry', {})
                if 'vessel_id' in log_entry:
                    event_data['maritime_context']['vessel_id'] = log_entry['vessel_id']
                if 'berth_id' in log_entry:
                    event_data['maritime_context']['berth_id'] = log_entry['berth_id']
            
            alert_system.evaluate_event(event_data)
            return result
        
        aggregator._generate_pattern_alert = enhanced_generate_alert
    
    return alert_system


# Export public interface
__all__ = [
    'AlertPriority', 'AlertChannel', 'MaritimeAlertType', 'AlertRule', 'AlertEvent',
    'MaritimeAlertSystem', 'init_maritime_alert_system', 'get_maritime_alert_system',
    'configure_alert_integration'
]