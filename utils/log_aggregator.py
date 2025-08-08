"""
Log Aggregation and Maritime Pattern Analysis for Stevedores Dashboard 3.0
Real-time log processing and maritime-specific pattern recognition
"""

import os
import json
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple, Pattern
from collections import defaultdict, deque, Counter
from dataclasses import dataclass, field
import threading
from queue import Queue, Empty
import logging
from enum import Enum

# Import structured logger components
from .structured_logger import LogLevel, MaritimeOperationType, ComponentType, get_structured_logger


class PatternSeverity(Enum):
    """Pattern detection severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class MaritimePatternType(Enum):
    """Maritime-specific log patterns"""
    VESSEL_DELAY = "vessel_delay"
    CARGO_DISCREPANCY = "cargo_discrepancy"
    SECURITY_BREACH = "security_breach"
    EQUIPMENT_FAILURE = "equipment_failure"
    ENVIRONMENTAL_VIOLATION = "environmental_violation"
    COMPLIANCE_VIOLATION = "compliance_violation"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    SYNC_FAILURE = "sync_failure"
    MEMORY_PRESSURE = "memory_pressure"
    DATABASE_SLOWDOWN = "database_slowdown"
    AUTHENTICATION_ANOMALY = "authentication_anomaly"
    RATE_LIMIT_BREACH = "rate_limit_breach"


@dataclass
class LogPattern:
    """Log pattern definition for maritime operations"""
    pattern_type: MaritimePatternType
    regex_patterns: List[str]
    severity: PatternSeverity
    time_window_minutes: int
    occurrence_threshold: int
    description: str
    maritime_impact: str
    compliance_flags: List[str] = field(default_factory=list)
    auto_escalate: bool = False
    
    def __post_init__(self):
        # Compile regex patterns for performance
        self.compiled_patterns: List[Pattern] = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.regex_patterns
        ]


@dataclass
class PatternMatch:
    """Detected pattern match"""
    pattern_type: MaritimePatternType
    severity: PatternSeverity
    timestamp: datetime
    log_entries: List[Dict[str, Any]]
    occurrence_count: int
    time_span_minutes: float
    maritime_context: Dict[str, Any]
    impact_assessment: str
    recommendations: List[str]
    alert_id: str = field(default_factory=lambda: f"alert_{int(time.time())}")


class MaritimeLogAggregator:
    """Advanced log aggregator with maritime pattern recognition"""
    
    def __init__(self, max_buffer_size: int = 10000):
        self.log_buffer = deque(maxlen=max_buffer_size)
        self.pattern_matches = deque(maxlen=1000)  # Store recent pattern matches
        self.processing_queue = Queue(maxsize=5000)
        self.is_processing = False
        self.processing_thread = None
        self.lock = threading.Lock()
        
        # Pattern storage
        self.patterns: Dict[MaritimePatternType, LogPattern] = {}
        self.active_patterns: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        # Performance metrics
        self.processing_stats = {
            'logs_processed': 0,
            'patterns_detected': 0,
            'alerts_generated': 0,
            'processing_errors': 0,
            'last_processing_time': None
        }
        
        # Initialize maritime patterns
        self._initialize_maritime_patterns()
        
        # Start processing
        self.start_processing()
        
        self.logger = get_structured_logger()
        self.logger.info(
            "Maritime log aggregator initialized",
            component=ComponentType.AUDIT_SYSTEM.value,
            patterns_loaded=len(self.patterns)
        )
    
    def _initialize_maritime_patterns(self):
        """Initialize maritime-specific log patterns"""
        
        # Vessel operation patterns
        self.patterns[MaritimePatternType.VESSEL_DELAY] = LogPattern(
            pattern_type=MaritimePatternType.VESSEL_DELAY,
            regex_patterns=[
                r"vessel.*delayed.*(\d+).*minutes",
                r"arrival.*delayed.*berth.*unavailable",
                r"departure.*delayed.*weather.*conditions",
                r"schedule.*deviation.*(\d+).*hours"
            ],
            severity=PatternSeverity.WARNING,
            time_window_minutes=60,
            occurrence_threshold=2,
            description="Vessel operation delays detected",
            maritime_impact="Schedule disruption, port congestion, cost implications",
            compliance_flags=["schedule_compliance", "port_operations"],
            auto_escalate=True
        )
        
        # Cargo handling patterns
        self.patterns[MaritimePatternType.CARGO_DISCREPANCY] = LogPattern(
            pattern_type=MaritimePatternType.CARGO_DISCREPANCY,
            regex_patterns=[
                r"cargo.*tally.*discrepancy.*(\d+).*containers",
                r"manifest.*mismatch.*(\d+).*items",
                r"weight.*discrepancy.*(\d+\.?\d*).*tons",
                r"damaged.*cargo.*reported.*(\d+).*units"
            ],
            severity=PatternSeverity.CRITICAL,
            time_window_minutes=30,
            occurrence_threshold=1,
            description="Cargo handling discrepancies detected",
            maritime_impact="Financial loss, compliance violations, customer disputes",
            compliance_flags=["cargo_compliance", "customs_declaration"],
            auto_escalate=True
        )
        
        # Security patterns
        self.patterns[MaritimePatternType.SECURITY_BREACH] = LogPattern(
            pattern_type=MaritimePatternType.SECURITY_BREACH,
            regex_patterns=[
                r"unauthorized.*access.*attempt",
                r"security.*violation.*detected",
                r"suspicious.*activity.*user.*(\d+)",
                r"failed.*authentication.*(\d+).*attempts",
                r"rate.*limit.*exceeded.*(\d+).*times"
            ],
            severity=PatternSeverity.CRITICAL,
            time_window_minutes=15,
            occurrence_threshold=1,
            description="Security breach or suspicious activity detected",
            maritime_impact="Data security risk, operational disruption, compliance violation",
            compliance_flags=["security_audit", "access_control", "isps_code"],
            auto_escalate=True
        )
        
        # Equipment failure patterns
        self.patterns[MaritimePatternType.EQUIPMENT_FAILURE] = LogPattern(
            pattern_type=MaritimePatternType.EQUIPMENT_FAILURE,
            regex_patterns=[
                r"crane.*(\d+).*malfunction",
                r"equipment.*failure.*berth.*(\d+)",
                r"system.*down.*maintenance.*required",
                r"sensor.*offline.*(\d+).*minutes"
            ],
            severity=PatternSeverity.WARNING,
            time_window_minutes=45,
            occurrence_threshold=2,
            description="Port equipment failure detected",
            maritime_impact="Operational delays, safety concerns, maintenance costs",
            compliance_flags=["equipment_maintenance", "safety_compliance"]
        )
        
        # Environmental monitoring patterns
        self.patterns[MaritimePatternType.ENVIRONMENTAL_VIOLATION] = LogPattern(
            pattern_type=MaritimePatternType.ENVIRONMENTAL_VIOLATION,
            regex_patterns=[
                r"emission.*limit.*exceeded.*(\d+\.?\d*).*ppm",
                r"ballast.*water.*violation",
                r"fuel.*spillage.*(\d+\.?\d*).*liters",
                r"noise.*level.*exceeded.*(\d+).*db"
            ],
            severity=PatternSeverity.CRITICAL,
            time_window_minutes=5,
            occurrence_threshold=1,
            description="Environmental compliance violation detected",
            maritime_impact="Regulatory fines, environmental damage, reputation risk",
            compliance_flags=["marpol_compliance", "environmental_protection"],
            auto_escalate=True
        )
        
        # Performance degradation patterns
        self.patterns[MaritimePatternType.PERFORMANCE_DEGRADATION] = LogPattern(
            pattern_type=MaritimePatternType.PERFORMANCE_DEGRADATION,
            regex_patterns=[
                r"response.*time.*(\d+).*ms.*threshold.*exceeded",
                r"database.*query.*slow.*(\d+\.?\d*).*seconds",
                r"memory.*usage.*(\d+).*percent.*critical",
                r"cpu.*usage.*(\d+).*percent.*sustained"
            ],
            severity=PatternSeverity.WARNING,
            time_window_minutes=10,
            occurrence_threshold=3,
            description="System performance degradation detected",
            maritime_impact="User experience degradation, operational efficiency loss",
            compliance_flags=["system_performance"]
        )
        
        # Sync failure patterns
        self.patterns[MaritimePatternType.SYNC_FAILURE] = LogPattern(
            pattern_type=MaritimePatternType.SYNC_FAILURE,
            regex_patterns=[
                r"sync.*failed.*(\d+).*attempts",
                r"offline.*data.*conflict.*detected",
                r"sync.*timeout.*(\d+).*seconds",
                r"data.*inconsistency.*(\d+).*records"
            ],
            severity=PatternSeverity.WARNING,
            time_window_minutes=20,
            occurrence_threshold=2,
            description="Data synchronization failures detected",
            maritime_impact="Data integrity risk, operational inconsistency",
            compliance_flags=["data_integrity"]
        )
        
        # Memory pressure patterns
        self.patterns[MaritimePatternType.MEMORY_PRESSURE] = LogPattern(
            pattern_type=MaritimePatternType.MEMORY_PRESSURE,
            regex_patterns=[
                r"memory.*usage.*(\d+).*percent.*warning",
                r"garbage.*collection.*frequency.*(\d+).*per.*minute",
                r"worker.*restart.*memory.*threshold",
                r"oom.*killer.*activated"
            ],
            severity=PatternSeverity.CRITICAL,
            time_window_minutes=5,
            occurrence_threshold=1,
            description="System memory pressure detected",
            maritime_impact="System stability risk, potential service interruption",
            compliance_flags=["system_stability"],
            auto_escalate=True
        )
    
    def add_log_entry(self, log_entry: Dict[str, Any]):
        """Add log entry for processing"""
        try:
            self.processing_queue.put_nowait(log_entry)
        except:
            # Queue full, drop oldest entries
            try:
                self.processing_queue.get_nowait()
                self.processing_queue.put_nowait(log_entry)
            except Empty:
                pass
    
    def start_processing(self):
        """Start log processing thread"""
        if self.is_processing:
            return
        
        self.is_processing = True
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        
        self.logger.info(
            "Log processing started",
            component=ComponentType.AUDIT_SYSTEM.value
        )
    
    def stop_processing(self):
        """Stop log processing thread"""
        self.is_processing = False
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=5)
        
        self.logger.info(
            "Log processing stopped",
            component=ComponentType.AUDIT_SYSTEM.value
        )
    
    def _processing_loop(self):
        """Main log processing loop"""
        while self.is_processing:
            try:
                # Process queued log entries
                processed_count = 0
                start_time = time.time()
                
                while processed_count < 100:  # Process in batches
                    try:
                        log_entry = self.processing_queue.get(timeout=1)
                        self._process_log_entry(log_entry)
                        processed_count += 1
                        self.processing_stats['logs_processed'] += 1
                    except Empty:
                        break
                    except Exception as e:
                        self.processing_stats['processing_errors'] += 1
                        self.logger.error(
                            "Error processing log entry",
                            component=ComponentType.AUDIT_SYSTEM.value,
                            exception=e
                        )
                
                # Update processing time
                self.processing_stats['last_processing_time'] = datetime.now(timezone.utc)
                
                # Clean up old pattern matches
                self._cleanup_old_patterns()
                
                # Brief sleep to prevent CPU spinning
                if processed_count == 0:
                    time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(
                    "Error in log processing loop",
                    component=ComponentType.AUDIT_SYSTEM.value,
                    exception=e
                )
                time.sleep(1)
    
    def _process_log_entry(self, log_entry: Dict[str, Any]):
        """Process individual log entry for patterns"""
        with self.lock:
            self.log_buffer.append(log_entry)
        
        # Extract message and other relevant fields
        message = log_entry.get('message', '')
        level = log_entry.get('level', 'INFO')
        timestamp_str = log_entry.get('timestamp', '')
        
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            timestamp = datetime.now(timezone.utc)
        
        # Check against all patterns
        for pattern_type, pattern in self.patterns.items():
            if self._matches_pattern(message, pattern, log_entry):
                self._handle_pattern_match(pattern_type, pattern, log_entry, timestamp)
    
    def _matches_pattern(self, message: str, pattern: LogPattern, log_entry: Dict[str, Any]) -> bool:
        """Check if log entry matches a pattern"""
        # Check message against regex patterns
        for compiled_pattern in pattern.compiled_patterns:
            if compiled_pattern.search(message):
                return True
        
        # Additional context-based matching for maritime operations
        if pattern.pattern_type == MaritimePatternType.SECURITY_BREACH:
            level = log_entry.get('level', '').upper()
            if level in ['SECURITY', 'CRITICAL'] and 'security' in message.lower():
                return True
        
        return False
    
    def _handle_pattern_match(self, pattern_type: MaritimePatternType, pattern: LogPattern, log_entry: Dict[str, Any], timestamp: datetime):
        """Handle detected pattern match"""
        pattern_key = f"{pattern_type.value}_{timestamp.strftime('%Y%m%d_%H%M')}"
        
        # Add to active patterns
        self.active_patterns[pattern_key].append({
            'log_entry': log_entry,
            'timestamp': timestamp,
            'pattern_type': pattern_type
        })
        
        # Check if threshold is met
        time_window_start = timestamp - timedelta(minutes=pattern.time_window_minutes)
        recent_matches = [
            match for match in self.active_patterns[pattern_key]
            if match['timestamp'] >= time_window_start
        ]
        
        if len(recent_matches) >= pattern.occurrence_threshold:
            self._generate_pattern_alert(pattern_type, pattern, recent_matches, timestamp)
    
    def _generate_pattern_alert(self, pattern_type: MaritimePatternType, pattern: LogPattern, matches: List[Dict[str, Any]], timestamp: datetime):
        """Generate alert for detected pattern"""
        try:
            # Calculate time span
            timestamps = [match['timestamp'] for match in matches]
            time_span = (max(timestamps) - min(timestamps)).total_seconds() / 60.0
            
            # Extract maritime context
            maritime_context = {}
            for match in matches:
                log_entry = match['log_entry']
                if 'vessel_id' in log_entry:
                    maritime_context['vessel_id'] = log_entry['vessel_id']
                if 'port_code' in log_entry:
                    maritime_context['port_code'] = log_entry['port_code']
                if 'berth_id' in log_entry:
                    maritime_context['berth_id'] = log_entry['berth_id']
            
            # Generate recommendations
            recommendations = self._generate_recommendations(pattern_type, matches)
            
            # Create pattern match
            pattern_match = PatternMatch(
                pattern_type=pattern_type,
                severity=pattern.severity,
                timestamp=timestamp,
                log_entries=[match['log_entry'] for match in matches],
                occurrence_count=len(matches),
                time_span_minutes=time_span,
                maritime_context=maritime_context,
                impact_assessment=pattern.maritime_impact,
                recommendations=recommendations
            )
            
            # Store pattern match
            with self.lock:
                self.pattern_matches.append(pattern_match)
            
            # Update stats
            self.processing_stats['patterns_detected'] += 1
            self.processing_stats['alerts_generated'] += 1
            
            # Log the alert
            self.logger.log(
                LogLevel.MARITIME_ALERT if pattern.severity != PatternSeverity.CRITICAL else LogLevel.CRITICAL,
                f"Maritime pattern detected: {pattern_type.value}",
                component=ComponentType.AUDIT_SYSTEM.value,
                pattern_type=pattern_type.value,
                severity=pattern.severity.value,
                occurrence_count=len(matches),
                time_span_minutes=time_span,
                maritime_impact=pattern.maritime_impact,
                recommendations=recommendations,
                compliance_flags=pattern.compliance_flags,
                auto_escalate=pattern.auto_escalate,
                alert_id=pattern_match.alert_id,
                **maritime_context
            )
            
            # Auto-escalate if configured
            if pattern.auto_escalate:
                self._escalate_alert(pattern_match)
                
        except Exception as e:
            self.processing_stats['processing_errors'] += 1
            self.logger.error(
                "Error generating pattern alert",
                component=ComponentType.AUDIT_SYSTEM.value,
                pattern_type=pattern_type.value,
                exception=e
            )
    
    def _generate_recommendations(self, pattern_type: MaritimePatternType, matches: List[Dict[str, Any]]) -> List[str]:
        """Generate actionable recommendations based on pattern type"""
        recommendations = []
        
        if pattern_type == MaritimePatternType.VESSEL_DELAY:
            recommendations.extend([
                "Review berth allocation and scheduling",
                "Contact vessel operator for updated ETA",
                "Consider alternative berthing arrangements",
                "Notify affected stakeholders of delays"
            ])
        
        elif pattern_type == MaritimePatternType.CARGO_DISCREPANCY:
            recommendations.extend([
                "Initiate cargo reconciliation process",
                "Contact shipping line for manifest verification",
                "Document discrepancies for insurance claims",
                "Review tally procedures and training"
            ])
        
        elif pattern_type == MaritimePatternType.SECURITY_BREACH:
            recommendations.extend([
                "Immediately review access logs",
                "Reset potentially compromised accounts",
                "Increase security monitoring",
                "Contact security team for incident response"
            ])
        
        elif pattern_type == MaritimePatternType.MEMORY_PRESSURE:
            recommendations.extend([
                "Monitor system performance closely",
                "Consider scaling resources",
                "Review application memory usage",
                "Prepare for potential service restart"
            ])
        
        elif pattern_type == MaritimePatternType.ENVIRONMENTAL_VIOLATION:
            recommendations.extend([
                "Immediately investigate emission source",
                "Contact environmental compliance officer",
                "Document incident for regulatory reporting",
                "Implement corrective measures"
            ])
        
        return recommendations
    
    def _escalate_alert(self, pattern_match: PatternMatch):
        """Escalate high-priority alerts"""
        self.logger.critical(
            f"ESCALATED ALERT: {pattern_match.pattern_type.value}",
            component=ComponentType.AUDIT_SYSTEM.value,
            alert_id=pattern_match.alert_id,
            severity="ESCALATED",
            maritime_impact=pattern_match.impact_assessment,
            recommendations=pattern_match.recommendations,
            requires_immediate_attention=True
        )
    
    def _cleanup_old_patterns(self):
        """Clean up old pattern tracking data"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        
        with self.lock:
            # Clean up active patterns
            keys_to_remove = []
            for pattern_key, matches in self.active_patterns.items():
                # Remove old matches
                self.active_patterns[pattern_key] = [
                    match for match in matches
                    if match['timestamp'] > cutoff_time
                ]
                
                # Remove empty pattern keys
                if not self.active_patterns[pattern_key]:
                    keys_to_remove.append(pattern_key)
            
            for key in keys_to_remove:
                del self.active_patterns[key]
    
    def get_recent_patterns(self, hours: int = 24) -> List[PatternMatch]:
        """Get recent pattern matches"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        with self.lock:
            return [
                match for match in self.pattern_matches
                if match.timestamp > cutoff_time
            ]
    
    def get_pattern_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get summary of detected patterns"""
        recent_patterns = self.get_recent_patterns(hours)
        
        # Count by type and severity
        pattern_counts = Counter(match.pattern_type.value for match in recent_patterns)
        severity_counts = Counter(match.severity.value for match in recent_patterns)
        
        # Get most frequent patterns
        top_patterns = pattern_counts.most_common(5)
        
        # Calculate alert frequency
        alert_frequency = len(recent_patterns) / max(1, hours) if recent_patterns else 0
        
        return {
            'time_period_hours': hours,
            'total_patterns': len(recent_patterns),
            'pattern_counts': dict(pattern_counts),
            'severity_counts': dict(severity_counts),
            'top_patterns': top_patterns,
            'alert_frequency_per_hour': round(alert_frequency, 2),
            'processing_stats': self.processing_stats.copy(),
            'active_pattern_keys': len(self.active_patterns),
            'buffer_size': len(self.log_buffer)
        }
    
    def get_maritime_dashboard_data(self) -> Dict[str, Any]:
        """Get maritime-specific dashboard data"""
        recent_patterns = self.get_recent_patterns(8)  # 8-hour shift
        
        # Maritime-specific categorization
        maritime_categories = {
            'vessel_operations': [MaritimePatternType.VESSEL_DELAY],
            'cargo_handling': [MaritimePatternType.CARGO_DISCREPANCY],
            'security_incidents': [MaritimePatternType.SECURITY_BREACH, MaritimePatternType.AUTHENTICATION_ANOMALY],
            'equipment_issues': [MaritimePatternType.EQUIPMENT_FAILURE],
            'environmental_concerns': [MaritimePatternType.ENVIRONMENTAL_VIOLATION],
            'system_performance': [MaritimePatternType.PERFORMANCE_DEGRADATION, MaritimePatternType.MEMORY_PRESSURE],
            'data_integrity': [MaritimePatternType.SYNC_FAILURE]
        }
        
        categorized_alerts = {}
        for category, pattern_types in maritime_categories.items():
            category_matches = [
                match for match in recent_patterns
                if match.pattern_type in pattern_types
            ]
            categorized_alerts[category] = {
                'count': len(category_matches),
                'critical_count': len([m for m in category_matches if m.severity == PatternSeverity.CRITICAL]),
                'latest_alert': category_matches[-1].timestamp.isoformat() if category_matches else None
            }
        
        return {
            'shift_summary': {
                'total_alerts': len(recent_patterns),
                'critical_alerts': len([m for m in recent_patterns if m.severity == PatternSeverity.CRITICAL]),
                'operational_categories': categorized_alerts
            },
            'processing_health': {
                'logs_processed_rate': self.processing_stats['logs_processed'] / max(1, time.time() - (self.processing_stats.get('start_time', time.time()))),
                'pattern_detection_rate': self.processing_stats['patterns_detected'] / max(1, self.processing_stats['logs_processed']),
                'error_rate': self.processing_stats['processing_errors'] / max(1, self.processing_stats['logs_processed'])
            },
            'recent_critical_alerts': [
                {
                    'alert_id': match.alert_id,
                    'type': match.pattern_type.value,
                    'timestamp': match.timestamp.isoformat(),
                    'impact': match.impact_assessment,
                    'recommendations': match.recommendations[:2]  # First 2 recommendations
                }
                for match in recent_patterns[-10:]  # Last 10 alerts
                if match.severity in [PatternSeverity.CRITICAL, PatternSeverity.EMERGENCY]
            ]
        }


# Global aggregator instance
_log_aggregator: Optional[MaritimeLogAggregator] = None


def init_log_aggregator() -> MaritimeLogAggregator:
    """Initialize the global log aggregator"""
    global _log_aggregator
    
    if _log_aggregator is None:
        _log_aggregator = MaritimeLogAggregator()
    
    return _log_aggregator


def get_log_aggregator() -> Optional[MaritimeLogAggregator]:
    """Get the global log aggregator instance"""
    return _log_aggregator


def configure_log_aggregation(app):
    """Configure Flask app with log aggregation"""
    # Initialize aggregator
    aggregator = init_log_aggregator()
    
    # Hook into structured logger to feed aggregator
    original_log = logging.Logger._log
    
    def enhanced_log(self, level, msg, args, exc_info=None, extra=None, stack_info=False):
        # Call original log method
        result = original_log(self, level, msg, args, exc_info, extra, stack_info)
        
        # Feed to aggregator if it's a maritime-related log
        if extra and aggregator:
            log_entry = {
                'level': logging.getLevelName(level),
                'message': str(msg) % args if args else str(msg),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                **extra
            }
            aggregator.add_log_entry(log_entry)
        
        return result
    
    # Monkey patch the logger
    logging.Logger._log = enhanced_log
    
    return aggregator


# Export public interface
__all__ = [
    'PatternSeverity', 'MaritimePatternType', 'LogPattern', 'PatternMatch',
    'MaritimeLogAggregator', 'init_log_aggregator', 'get_log_aggregator',
    'configure_log_aggregation'
]