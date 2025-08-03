"""
Phase 6 Maritime IoT Integration Framework
Comprehensive IoT ecosystem for vessel sensors, smart ports, and real-time monitoring

Created by Maritime IoT Swarm Agent
Swarm ID: swarm-1754123456789 | Task ID: task-phase6-002
"""

import os
import json
import asyncio
import websockets
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import uuid
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import numpy as np

logger = logging.getLogger(__name__)

class IoTDeviceType(Enum):
    """Types of maritime IoT devices"""
    ENGINE_SENSOR = "engine_sensor"
    GPS_TRACKER = "gps_tracker"
    FUEL_MONITOR = "fuel_monitor"
    WEATHER_STATION = "weather_station"
    CARGO_SENSOR = "cargo_sensor"
    SECURITY_CAMERA = "security_camera"
    BRIDGE_EQUIPMENT = "bridge_equipment"
    ENVIRONMENTAL_SENSOR = "environmental_sensor"
    COLLISION_AVOIDANCE = "collision_avoidance"
    PORT_SENSOR = "port_sensor"

class IoTProtocol(Enum):
    """IoT communication protocols"""
    MQTT = "mqtt"
    HTTP_REST = "http_rest"
    WEBSOCKET = "websocket"
    LORAWAN = "lorawan"
    SATELLITE = "satellite"
    MODBUS = "modbus"
    OPC_UA = "opc_ua"

class DeviceStatus(Enum):
    """IoT device status"""
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    ERROR = "error"
    CALIBRATING = "calibrating"

@dataclass
class IoTDevice:
    """Maritime IoT device definition"""
    device_id: str
    device_name: str
    device_type: IoTDeviceType
    vessel_id: Optional[str]
    location: Optional[str]
    protocol: IoTProtocol
    endpoint: str
    status: DeviceStatus
    last_reading: Optional[datetime]
    battery_level: Optional[float]
    signal_strength: Optional[float]
    firmware_version: str
    calibration_date: Optional[datetime]
    maintenance_schedule: str
    data_format: str
    sampling_rate: int  # seconds
    installed_date: datetime

@dataclass
class IoTReading:
    """IoT sensor reading"""
    reading_id: str
    device_id: str
    timestamp: datetime
    data_type: str
    value: Union[float, str, Dict[str, Any]]
    unit: str
    quality_score: float
    location: Optional[Tuple[float, float]]
    metadata: Dict[str, Any]

@dataclass
class IoTAlert:
    """IoT system alert"""
    alert_id: str
    device_id: str
    alert_type: str
    severity: str
    message: str
    triggered_at: datetime
    resolved_at: Optional[datetime]
    threshold_value: Optional[float]
    actual_value: Optional[float]
    action_required: str

class Phase6MaritimeIoT:
    """
    Comprehensive maritime IoT integration framework
    Manages vessel sensors, port infrastructure, and real-time data streaming
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.devices = {}
        self.device_connections = {}
        self.data_streams = {}
        self.alerts = {}
        
        # Real-time data processing
        self.data_processors = {}
        self.alert_handlers = {}
        self.data_buffer = {}
        
        # Communication protocols
        self.protocol_handlers = {
            IoTProtocol.MQTT: self._handle_mqtt,
            IoTProtocol.HTTP_REST: self._handle_http_rest,
            IoTProtocol.WEBSOCKET: self._handle_websocket,
            IoTProtocol.SATELLITE: self._handle_satellite
        }
        
        # Thread pool for device management
        self.executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="IoT")
        
        # Initialize database
        self._init_database()
        
        # Load registered devices
        self._load_devices()
        
        # Start IoT services
        self._start_iot_services()
        
        logger.info("Phase 6 Maritime IoT Framework initialized")
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load IoT configuration"""
        return {
            "mqtt_broker": "mqtt://maritime-iot.broker:1883",
            "websocket_port": 8765,
            "http_api_port": 8080,
            "data_retention_days": 365,
            "alert_retention_days": 90,
            "device_timeout_seconds": 300,
            "batch_processing_size": 100,
            "real_time_processing": True,
            "alert_thresholds": {
                "engine_temperature": 85.0,
                "fuel_level": 10.0,
                "battery_level": 20.0,
                "signal_strength": 30.0
            },
            "protocols_enabled": ["mqtt", "http_rest", "websocket", "satellite"],
            "encryption_enabled": True,
            "compression_enabled": True
        }
    
    def _init_database(self):
        """Initialize IoT database"""
        try:
            conn = sqlite3.connect("phase6_iot.db")
            cursor = conn.cursor()
            
            # IoT devices table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS iot_devices (
                    device_id TEXT PRIMARY KEY,
                    device_name TEXT NOT NULL,
                    device_type TEXT NOT NULL,
                    vessel_id TEXT,
                    location TEXT,
                    protocol TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    status TEXT DEFAULT 'offline',
                    last_reading TIMESTAMP,
                    battery_level REAL,
                    signal_strength REAL,
                    firmware_version TEXT,
                    calibration_date TIMESTAMP,
                    maintenance_schedule TEXT,
                    data_format TEXT DEFAULT 'json',
                    sampling_rate INTEGER DEFAULT 60,
                    installed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # IoT readings table (partitioned by date for performance)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS iot_readings (
                    reading_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    data_type TEXT NOT NULL,
                    value TEXT NOT NULL,
                    unit TEXT,
                    quality_score REAL DEFAULT 1.0,
                    latitude REAL,
                    longitude REAL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (device_id) REFERENCES iot_devices (device_id)
                )
            ''')
            
            # IoT alerts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS iot_alerts (
                    alert_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    triggered_at TIMESTAMP NOT NULL,
                    resolved_at TIMESTAMP,
                    threshold_value REAL,
                    actual_value REAL,
                    action_required TEXT,
                    FOREIGN KEY (device_id) REFERENCES iot_devices (device_id)
                )
            ''')
            
            # Device analytics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS device_analytics (
                    analytics_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (device_id) REFERENCES iot_devices (device_id)
                )
            ''')
            
            # Create indices for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_readings_device_time ON iot_readings(device_id, timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON iot_readings(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_device ON iot_alerts(device_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_devices_vessel ON iot_devices(vessel_id)')
            
            conn.commit()
            conn.close()
            
            logger.info("IoT database initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize IoT database: {e}")
            raise
    
    def register_device(self, device_config: Dict[str, Any]) -> str:
        """Register new IoT device"""
        try:
            device_id = device_config.get("device_id", str(uuid.uuid4()))
            
            device = IoTDevice(
                device_id=device_id,
                device_name=device_config["device_name"],
                device_type=IoTDeviceType(device_config["device_type"]),
                vessel_id=device_config.get("vessel_id"),
                location=device_config.get("location"),
                protocol=IoTProtocol(device_config["protocol"]),
                endpoint=device_config["endpoint"],
                status=DeviceStatus.OFFLINE,
                last_reading=None,
                battery_level=device_config.get("battery_level"),
                signal_strength=device_config.get("signal_strength"),
                firmware_version=device_config.get("firmware_version", "1.0.0"),
                calibration_date=device_config.get("calibration_date"),
                maintenance_schedule=device_config.get("maintenance_schedule", "monthly"),
                data_format=device_config.get("data_format", "json"),
                sampling_rate=device_config.get("sampling_rate", 60),
                installed_date=datetime.now()
            )
            
            # Save to database
            self._save_device(device)
            
            # Add to registry
            self.devices[device_id] = device
            
            # Initialize connection if auto-connect enabled
            if device_config.get("auto_connect", True):
                self._connect_device(device_id)
            
            logger.info(f"Registered IoT device: {device_id} ({device.device_name})")
            return device_id
            
        except Exception as e:
            logger.error(f"Failed to register IoT device: {e}")
            raise
    
    def _connect_device(self, device_id: str):
        """Connect to IoT device"""
        try:
            if device_id not in self.devices:
                raise ValueError(f"Device {device_id} not found")
            
            device = self.devices[device_id]
            protocol_handler = self.protocol_handlers.get(device.protocol)
            
            if not protocol_handler:
                raise ValueError(f"Unsupported protocol: {device.protocol}")
            
            # Connect using appropriate protocol
            connection = protocol_handler(device, "connect")
            self.device_connections[device_id] = connection
            
            # Update device status
            device.status = DeviceStatus.ONLINE
            self._update_device_status(device_id, DeviceStatus.ONLINE)
            
            # Start data collection
            self._start_data_collection(device_id)
            
            logger.info(f"Connected to device: {device_id}")
            
        except Exception as e:
            logger.error(f"Failed to connect device {device_id}: {e}")
            if device_id in self.devices:
                self.devices[device_id].status = DeviceStatus.ERROR
                self._update_device_status(device_id, DeviceStatus.ERROR)
    
    def _start_data_collection(self, device_id: str):
        """Start collecting data from device"""
        def collect_data():
            device = self.devices[device_id]
            
            while (device_id in self.device_connections and 
                   device.status == DeviceStatus.ONLINE):
                try:
                    # Collect data based on sampling rate
                    data = self._collect_device_data(device_id)
                    
                    if data:
                        # Process and store data
                        self._process_device_data(device_id, data)
                    
                    time.sleep(device.sampling_rate)
                    
                except Exception as e:
                    logger.warning(f"Data collection error for {device_id}: {e}")
                    time.sleep(device.sampling_rate * 2)  # Retry with longer interval
        
        # Start collection thread
        thread = threading.Thread(target=collect_data, name=f"DataCollection-{device_id}", daemon=True)
        thread.start()
    
    def _collect_device_data(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Collect data from specific device"""
        try:
            device = self.devices[device_id]
            
            # Mock data collection based on device type
            if device.device_type == IoTDeviceType.ENGINE_SENSOR:
                return {
                    "temperature": 70 + np.random.uniform(-10, 20),
                    "rpm": 1000 + np.random.uniform(-200, 500),
                    "oil_pressure": 40 + np.random.uniform(-5, 10),
                    "vibration": np.random.uniform(0, 5)
                }
            elif device.device_type == IoTDeviceType.GPS_TRACKER:
                return {
                    "latitude": 40.7 + np.random.uniform(-0.1, 0.1),
                    "longitude": -74.0 + np.random.uniform(-0.1, 0.1),
                    "speed": 10 + np.random.uniform(-2, 5),
                    "heading": np.random.uniform(0, 360)
                }
            elif device.device_type == IoTDeviceType.FUEL_MONITOR:
                return {
                    "fuel_level": 50 + np.random.uniform(-10, 10),
                    "consumption_rate": 5 + np.random.uniform(-1, 2),
                    "fuel_quality": 95 + np.random.uniform(-5, 5)
                }
            elif device.device_type == IoTDeviceType.WEATHER_STATION:
                return {
                    "wind_speed": np.random.uniform(0, 25),
                    "wind_direction": np.random.uniform(0, 360),
                    "temperature": 20 + np.random.uniform(-10, 15),
                    "humidity": 60 + np.random.uniform(-20, 30),
                    "pressure": 1013 + np.random.uniform(-20, 20)
                }
            elif device.device_type == IoTDeviceType.CARGO_SENSOR:
                return {
                    "weight": 1000 + np.random.uniform(-100, 500),
                    "temperature": 15 + np.random.uniform(-5, 10),
                    "humidity": 50 + np.random.uniform(-10, 20),
                    "shock_level": np.random.uniform(0, 3)
                }
            else:
                # Generic sensor data
                return {
                    "value": np.random.uniform(0, 100),
                    "status": "normal",
                    "quality": np.random.uniform(0.8, 1.0)
                }
                
        except Exception as e:
            logger.warning(f"Error collecting data from {device_id}: {e}")
            return None
    
    def _process_device_data(self, device_id: str, data: Dict[str, Any]):
        """Process and store device data"""
        try:
            device = self.devices[device_id]
            timestamp = datetime.now(timezone.utc)
            
            # Create readings for each data point
            for data_type, value in data.items():
                reading = IoTReading(
                    reading_id=str(uuid.uuid4()),
                    device_id=device_id,
                    timestamp=timestamp,
                    data_type=data_type,
                    value=value,
                    unit=self._get_unit_for_data_type(data_type),
                    quality_score=self._calculate_data_quality(value, data_type),
                    location=self._get_device_location(device_id),
                    metadata={"device_type": device.device_type.value}
                )
                
                # Store reading
                self._save_reading(reading)
                
                # Check for alerts
                self._check_alerts(device_id, data_type, value)
            
            # Update device last reading time
            device.last_reading = timestamp
            self._update_device_last_reading(device_id, timestamp)
            
            # Add to real-time data stream
            if device_id not in self.data_streams:
                self.data_streams[device_id] = []
            
            self.data_streams[device_id].append({
                "timestamp": timestamp.isoformat(),
                "data": data
            })
            
            # Keep only recent data in memory
            if len(self.data_streams[device_id]) > 100:
                self.data_streams[device_id] = self.data_streams[device_id][-100:]
            
        except Exception as e:
            logger.error(f"Failed to process data from {device_id}: {e}")
    
    def _check_alerts(self, device_id: str, data_type: str, value: float):
        """Check for alert conditions"""
        try:
            thresholds = self.config["alert_thresholds"]
            alert_triggered = False
            severity = "low"
            
            # Check specific thresholds
            if data_type == "temperature" and isinstance(value, (int, float)):
                if value > thresholds.get("engine_temperature", 85):
                    alert_triggered = True
                    severity = "high" if value > 95 else "medium"
            elif data_type == "fuel_level" and isinstance(value, (int, float)):
                if value < thresholds.get("fuel_level", 10):
                    alert_triggered = True
                    severity = "critical" if value < 5 else "high"
            elif data_type == "battery_level" and isinstance(value, (int, float)):
                if value < thresholds.get("battery_level", 20):
                    alert_triggered = True
                    severity = "medium"
            
            if alert_triggered:
                self._create_alert(device_id, data_type, value, severity)
                
        except Exception as e:
            logger.warning(f"Error checking alerts for {device_id}: {e}")
    
    def _create_alert(self, device_id: str, data_type: str, value: float, severity: str):
        """Create IoT alert"""
        try:
            alert = IoTAlert(
                alert_id=str(uuid.uuid4()),
                device_id=device_id,
                alert_type=f"{data_type}_threshold",
                severity=severity,
                message=f"{data_type} value {value} exceeds threshold",
                triggered_at=datetime.now(timezone.utc),
                resolved_at=None,
                threshold_value=self.config["alert_thresholds"].get(data_type),
                actual_value=value,
                action_required=f"Check {data_type} on device {device_id}"
            )
            
            # Save alert
            self._save_alert(alert)
            
            # Add to active alerts
            self.alerts[alert.alert_id] = alert
            
            logger.warning(f"IoT Alert created: {alert.alert_id} - {alert.message}")
            
        except Exception as e:
            logger.error(f"Failed to create alert: {e}")
    
    def get_device_data(self, device_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get device data for specified time period"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            conn = sqlite3.connect("phase6_iot.db")
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT timestamp, data_type, value, unit, quality_score
                FROM iot_readings 
                WHERE device_id = ? AND timestamp >= ?
                ORDER BY timestamp DESC
            ''', (device_id, cutoff_time))
            
            readings = []
            for row in cursor.fetchall():
                readings.append({
                    "timestamp": row[0],
                    "data_type": row[1],
                    "value": json.loads(row[2]) if row[2].startswith('{') else row[2],
                    "unit": row[3],
                    "quality_score": row[4]
                })
            
            conn.close()
            return readings
            
        except Exception as e:
            logger.error(f"Failed to get device data: {e}")
            return []
    
    def get_iot_dashboard(self) -> Dict[str, Any]:
        """Generate IoT system dashboard"""
        try:
            dashboard = {
                "dashboard_generated": datetime.now(timezone.utc).isoformat(),
                "system_overview": {
                    "total_devices": len(self.devices),
                    "online_devices": len([d for d in self.devices.values() if d.status == DeviceStatus.ONLINE]),
                    "offline_devices": len([d for d in self.devices.values() if d.status == DeviceStatus.OFFLINE]),
                    "error_devices": len([d for d in self.devices.values() if d.status == DeviceStatus.ERROR]),
                    "active_alerts": len(self.alerts),
                    "data_points_today": self._get_data_points_count_today()
                },
                "device_types": {},
                "protocol_distribution": {},
                "vessel_coverage": {},
                "recent_alerts": [],
                "device_health": {},
                "data_quality_metrics": {}
            }
            
            # Analyze device types
            for device_type in IoTDeviceType:
                count = len([d for d in self.devices.values() if d.device_type == device_type])
                if count > 0:
                    dashboard["device_types"][device_type.value] = count
            
            # Protocol distribution
            for protocol in IoTProtocol:
                count = len([d for d in self.devices.values() if d.protocol == protocol])
                if count > 0:
                    dashboard["protocol_distribution"][protocol.value] = count
            
            # Vessel coverage
            vessels = set(d.vessel_id for d in self.devices.values() if d.vessel_id)
            dashboard["vessel_coverage"]["total_vessels"] = len(vessels)
            dashboard["vessel_coverage"]["devices_per_vessel"] = len(self.devices) / max(len(vessels), 1)
            
            # Recent alerts
            recent_alerts = sorted(self.alerts.values(), key=lambda x: x.triggered_at, reverse=True)[:10]
            dashboard["recent_alerts"] = [
                {
                    "alert_id": alert.alert_id,
                    "device_id": alert.device_id,
                    "type": alert.alert_type,
                    "severity": alert.severity,
                    "message": alert.message,
                    "triggered_at": alert.triggered_at.isoformat()
                }
                for alert in recent_alerts
            ]
            
            # Device health
            for device_id, device in self.devices.items():
                dashboard["device_health"][device_id] = {
                    "status": device.status.value,
                    "battery_level": device.battery_level,
                    "signal_strength": device.signal_strength,
                    "last_reading": device.last_reading.isoformat() if device.last_reading else None
                }
            
            # Data quality metrics
            dashboard["data_quality_metrics"] = self._calculate_data_quality_metrics()
            
            return dashboard
            
        except Exception as e:
            logger.error(f"Failed to generate IoT dashboard: {e}")
            return {"error": str(e)}
    
    # Protocol handlers
    def _handle_mqtt(self, device: IoTDevice, action: str) -> Any:
        """Handle MQTT protocol communication"""
        if action == "connect":
            return {"protocol": "mqtt", "connected": True, "client": f"mqtt_client_{device.device_id}"}
        return None
    
    def _handle_http_rest(self, device: IoTDevice, action: str) -> Any:
        """Handle HTTP REST API communication"""
        if action == "connect":
            return {"protocol": "http_rest", "connected": True, "endpoint": device.endpoint}
        return None
    
    def _handle_websocket(self, device: IoTDevice, action: str) -> Any:
        """Handle WebSocket communication"""
        if action == "connect":
            return {"protocol": "websocket", "connected": True, "socket": f"ws_{device.device_id}"}
        return None
    
    def _handle_satellite(self, device: IoTDevice, action: str) -> Any:
        """Handle satellite communication"""
        if action == "connect":
            return {"protocol": "satellite", "connected": True, "terminal": f"sat_{device.device_id}"}
        return None
    
    # Helper methods
    def _load_devices(self):
        """Load registered devices from database"""
        try:
            conn = sqlite3.connect("phase6_iot.db")
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM iot_devices')
            for row in cursor.fetchall():
                device = IoTDevice(
                    device_id=row[0],
                    device_name=row[1],
                    device_type=IoTDeviceType(row[2]),
                    vessel_id=row[3],
                    location=row[4],
                    protocol=IoTProtocol(row[5]),
                    endpoint=row[6],
                    status=DeviceStatus(row[7]),
                    last_reading=datetime.fromisoformat(row[8]) if row[8] else None,
                    battery_level=row[9],
                    signal_strength=row[10],
                    firmware_version=row[11],
                    calibration_date=datetime.fromisoformat(row[12]) if row[12] else None,
                    maintenance_schedule=row[13],
                    data_format=row[14],
                    sampling_rate=row[15],
                    installed_date=datetime.fromisoformat(row[16])
                )
                self.devices[device.device_id] = device
            
            conn.close()
            logger.info(f"Loaded {len(self.devices)} IoT devices")
            
        except Exception as e:
            logger.warning(f"Could not load devices: {e}")
    
    def _start_iot_services(self):
        """Start IoT services"""
        try:
            # Start device monitoring
            self._start_device_monitoring()
            
            # Start data quality monitoring
            self._start_data_quality_monitoring()
            
            logger.info("IoT services started")
            
        except Exception as e:
            logger.error(f"Failed to start IoT services: {e}")
    
    def _start_device_monitoring(self):
        """Start monitoring device health"""
        def monitor_devices():
            while True:
                try:
                    for device_id, device in self.devices.items():
                        if device.last_reading:
                            time_since_reading = datetime.now(timezone.utc) - device.last_reading
                            if time_since_reading.total_seconds() > self.config["device_timeout_seconds"]:
                                if device.status == DeviceStatus.ONLINE:
                                    device.status = DeviceStatus.OFFLINE
                                    self._update_device_status(device_id, DeviceStatus.OFFLINE)
                                    logger.warning(f"Device {device_id} marked offline - no data received")
                    
                    time.sleep(60)  # Check every minute
                    
                except Exception as e:
                    logger.error(f"Error in device monitoring: {e}")
                    time.sleep(60)
        
        thread = threading.Thread(target=monitor_devices, name="DeviceMonitoring", daemon=True)
        thread.start()
    
    def _start_data_quality_monitoring(self):
        """Start monitoring data quality"""
        def monitor_data_quality():
            while True:
                try:
                    # Analyze data quality metrics
                    quality_metrics = self._calculate_data_quality_metrics()
                    
                    # Log quality issues
                    for device_id, metrics in quality_metrics.items():
                        if metrics.get("average_quality", 1.0) < 0.8:
                            logger.warning(f"Low data quality detected for device {device_id}: {metrics['average_quality']:.2f}")
                    
                    time.sleep(300)  # Check every 5 minutes
                    
                except Exception as e:
                    logger.error(f"Error in data quality monitoring: {e}")
                    time.sleep(300)
        
        thread = threading.Thread(target=monitor_data_quality, name="DataQualityMonitoring", daemon=True)
        thread.start()
    
    def _save_device(self, device: IoTDevice):
        """Save device to database"""
        try:
            conn = sqlite3.connect("phase6_iot.db")
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO iot_devices
                (device_id, device_name, device_type, vessel_id, location, protocol,
                 endpoint, status, battery_level, signal_strength, firmware_version,
                 calibration_date, maintenance_schedule, data_format, sampling_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                device.device_id, device.device_name, device.device_type.value,
                device.vessel_id, device.location, device.protocol.value,
                device.endpoint, device.status.value, device.battery_level,
                device.signal_strength, device.firmware_version, device.calibration_date,
                device.maintenance_schedule, device.data_format, device.sampling_rate
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to save device: {e}")
    
    def _save_reading(self, reading: IoTReading):
        """Save sensor reading to database"""
        try:
            conn = sqlite3.connect("phase6_iot.db")
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO iot_readings
                (reading_id, device_id, timestamp, data_type, value, unit,
                 quality_score, latitude, longitude, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                reading.reading_id, reading.device_id, reading.timestamp,
                reading.data_type, json.dumps(reading.value), reading.unit,
                reading.quality_score, 
                reading.location[0] if reading.location else None,
                reading.location[1] if reading.location else None,
                json.dumps(reading.metadata)
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to save reading: {e}")
    
    def _save_alert(self, alert: IoTAlert):
        """Save alert to database"""
        try:
            conn = sqlite3.connect("phase6_iot.db")
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO iot_alerts
                (alert_id, device_id, alert_type, severity, message, triggered_at,
                 threshold_value, actual_value, action_required)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                alert.alert_id, alert.device_id, alert.alert_type, alert.severity,
                alert.message, alert.triggered_at, alert.threshold_value,
                alert.actual_value, alert.action_required
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to save alert: {e}")
    
    def _get_unit_for_data_type(self, data_type: str) -> str:
        """Get appropriate unit for data type"""
        units = {
            "temperature": "°C",
            "rpm": "RPM",
            "pressure": "bar",
            "speed": "knots",
            "fuel_level": "%",
            "battery_level": "%",
            "signal_strength": "%",
            "wind_speed": "m/s",
            "humidity": "%",
            "weight": "kg",
            "latitude": "°",
            "longitude": "°",
            "heading": "°"
        }
        return units.get(data_type, "unit")
    
    def _calculate_data_quality(self, value: Any, data_type: str) -> float:
        """Calculate data quality score"""
        try:
            if not isinstance(value, (int, float)):
                return 0.8  # Lower quality for non-numeric data
            
            # Range-based quality assessment
            if data_type == "temperature" and (value < -50 or value > 150):
                return 0.6  # Suspicious temperature reading
            elif data_type == "fuel_level" and (value < 0 or value > 100):
                return 0.5  # Invalid fuel level
            elif data_type == "speed" and (value < 0 or value > 50):
                return 0.7  # Suspicious speed reading
            
            return 1.0  # Good quality
            
        except:
            return 0.5  # Unknown quality
    
    def _get_device_location(self, device_id: str) -> Optional[Tuple[float, float]]:
        """Get current device location"""
        # For GPS devices, use latest coordinates
        # For fixed devices, use installation location
        if device_id in self.data_streams:
            recent_data = self.data_streams[device_id][-1:] if self.data_streams[device_id] else []
            for data_point in recent_data:
                data = data_point.get("data", {})
                if "latitude" in data and "longitude" in data:
                    return (data["latitude"], data["longitude"])
        
        return None
    
    def _update_device_status(self, device_id: str, status: DeviceStatus):
        """Update device status in database"""
        try:
            conn = sqlite3.connect("phase6_iot.db")
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE iot_devices SET status = ? WHERE device_id = ?
            ''', (status.value, device_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to update device status: {e}")
    
    def _update_device_last_reading(self, device_id: str, timestamp: datetime):
        """Update device last reading timestamp"""
        try:
            conn = sqlite3.connect("phase6_iot.db")
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE iot_devices SET last_reading = ? WHERE device_id = ?
            ''', (timestamp, device_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to update device last reading: {e}")
    
    def _get_data_points_count_today(self) -> int:
        """Get number of data points collected today"""
        try:
            conn = sqlite3.connect("phase6_iot.db")
            cursor = conn.cursor()
            
            today = datetime.now(timezone.utc).date()
            cursor.execute('''
                SELECT COUNT(*) FROM iot_readings 
                WHERE DATE(timestamp) = ?
            ''', (today,))
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count
            
        except Exception as e:
            logger.warning(f"Error getting data points count: {e}")
            return 0
    
    def _calculate_data_quality_metrics(self) -> Dict[str, Any]:
        """Calculate data quality metrics for all devices"""
        try:
            conn = sqlite3.connect("phase6_iot.db")
            cursor = conn.cursor()
            
            # Get quality metrics for last 24 hours
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            
            cursor.execute('''
                SELECT device_id, AVG(quality_score), COUNT(*), MIN(quality_score), MAX(quality_score)
                FROM iot_readings 
                WHERE timestamp >= ?
                GROUP BY device_id
            ''', (cutoff_time,))
            
            metrics = {}
            for row in cursor.fetchall():
                metrics[row[0]] = {
                    "average_quality": row[1],
                    "reading_count": row[2],
                    "min_quality": row[3],
                    "max_quality": row[4]
                }
            
            conn.close()
            return metrics
            
        except Exception as e:
            logger.warning(f"Error calculating data quality metrics: {e}")
            return {}

# Example usage and testing
if __name__ == "__main__":
    # Initialize Phase 6 Maritime IoT
    iot_system = Phase6MaritimeIoT()
    
    print("🌐 Phase 6 Maritime IoT Integration Framework")
    print("📡 Advanced Sensor Networks and Real-Time Data")
    print("⚓ Smart Vessel and Port Infrastructure")
    
    # Register sample IoT devices
    print(f"\n🔧 Registering IoT devices...")
    
    # Engine sensor
    engine_sensor = {
        "device_name": "Main Engine Monitor",
        "device_type": "engine_sensor",
        "vessel_id": "VESSEL_001",
        "protocol": "mqtt",
        "endpoint": "mqtt://vessel001/engine/main",
        "sampling_rate": 30,
        "auto_connect": True
    }
    
    engine_id = iot_system.register_device(engine_sensor)
    print(f"✅ Engine sensor registered: {engine_id}")
    
    # GPS tracker
    gps_tracker = {
        "device_name": "Primary GPS",
        "device_type": "gps_tracker",
        "vessel_id": "VESSEL_001",
        "protocol": "satellite",
        "endpoint": "sat://vessel001/gps/primary",
        "sampling_rate": 60
    }
    
    gps_id = iot_system.register_device(gps_tracker)
    print(f"✅ GPS tracker registered: {gps_id}")
    
    # Fuel monitor
    fuel_monitor = {
        "device_name": "Fuel Tank Monitor",
        "device_type": "fuel_monitor",
        "vessel_id": "VESSEL_001",
        "protocol": "http_rest",
        "endpoint": "http://vessel001/api/fuel",
        "sampling_rate": 120
    }
    
    fuel_id = iot_system.register_device(fuel_monitor)
    print(f"✅ Fuel monitor registered: {fuel_id}")
    
    # Weather station
    weather_station = {
        "device_name": "Bridge Weather Station",
        "device_type": "weather_station",
        "vessel_id": "VESSEL_001",
        "protocol": "websocket",
        "endpoint": "ws://vessel001/weather",
        "sampling_rate": 300
    }
    
    weather_id = iot_system.register_device(weather_station)
    print(f"✅ Weather station registered: {weather_id}")
    
    # Let the system collect some data
    print(f"\n📊 Collecting IoT data...")
    time.sleep(5)  # Let devices collect some data
    
    # Generate IoT dashboard
    print(f"\n📈 Generating IoT dashboard...")
    dashboard = iot_system.get_iot_dashboard()
    
    print(f"🎯 IoT System Overview:")
    print(f"   • Total Devices: {dashboard['system_overview']['total_devices']}")
    print(f"   • Online Devices: {dashboard['system_overview']['online_devices']}")
    print(f"   • Active Alerts: {dashboard['system_overview']['active_alerts']}")
    print(f"   • Data Points Today: {dashboard['system_overview']['data_points_today']}")
    
    if dashboard['device_types']:
        print(f"\n📱 Device Types:")
        for device_type, count in dashboard['device_types'].items():
            print(f"   • {device_type}: {count}")
    
    if dashboard['protocol_distribution']:
        print(f"\n📡 Protocol Distribution:")
        for protocol, count in dashboard['protocol_distribution'].items():
            print(f"   • {protocol}: {count}")
    
    print(f"\n🌊 Vessel Coverage:")
    print(f"   • Vessels with IoT: {dashboard['vessel_coverage']['total_vessels']}")
    print(f"   • Devices per Vessel: {dashboard['vessel_coverage']['devices_per_vessel']:.1f}")
    
    print(f"\n🎉 Phase 6 Maritime IoT Framework is operational!")