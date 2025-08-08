#!/usr/bin/env python3
"""
Stevedores 3.0 - Phase 6 Advanced Vessel Performance Optimization
Maritime vessel performance optimization with AI-driven fuel efficiency and route optimization.
"""

import sqlite3
import json
import threading
import time
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple
import logging
import math

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ML availability check
try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import mean_absolute_error
    import numpy as np
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("ML libraries not available. Using mock implementations.")

class VesselType(Enum):
    CONTAINER = "container"
    BULK_CARRIER = "bulk_carrier"
    TANKER = "tanker"
    CRUISE = "cruise"
    FERRY = "ferry"
    CARGO = "cargo"
    RO_RO = "ro_ro"

class PerformanceMetric(Enum):
    FUEL_EFFICIENCY = "fuel_efficiency"
    SPEED_OPTIMIZATION = "speed_optimization"
    ROUTE_EFFICIENCY = "route_efficiency"
    EMISSIONS_REDUCTION = "emissions_reduction"
    MAINTENANCE_OPTIMIZATION = "maintenance_optimization"
    CARGO_EFFICIENCY = "cargo_efficiency"

class OptimizationStrategy(Enum):
    FUEL_SAVINGS = "fuel_savings"
    TIME_CRITICAL = "time_critical"
    BALANCED = "balanced"
    ECO_FRIENDLY = "eco_friendly"
    COST_OPTIMIZATION = "cost_optimization"

@dataclass
class VesselSpecifications:
    vessel_id: str
    vessel_name: str
    vessel_type: VesselType
    length: float  # meters
    beam: float    # meters
    draft: float   # meters
    gross_tonnage: float
    deadweight_tonnage: float
    max_speed: float  # knots
    service_speed: float  # knots
    engine_power: float  # kW
    fuel_capacity: float  # tons
    cargo_capacity: float  # TEU or tons
    
class PerformanceData:
    def __init__(self):
        self.speed: float = 0.0
        self.fuel_consumption: float = 0.0  # tons/hour
        self.course: float = 0.0  # degrees
        self.weather_conditions: Dict[str, Any] = {}
        self.sea_state: int = 0  # 0-9 scale
        self.wind_speed: float = 0.0  # knots
        self.wind_direction: float = 0.0  # degrees
        self.current_speed: float = 0.0  # knots
        self.current_direction: float = 0.0  # degrees
        self.cargo_load: float = 0.0  # percentage
        self.engine_load: float = 0.0  # percentage
        self.timestamp: datetime = datetime.now()

@dataclass
class RouteWaypoint:
    latitude: float
    longitude: float
    eta: datetime
    speed_recommendation: float
    fuel_estimate: float
    weather_forecast: Dict[str, Any]

@dataclass
class OptimizationResult:
    optimization_id: str
    vessel_id: str
    strategy: OptimizationStrategy
    original_route: List[RouteWaypoint]
    optimized_route: List[RouteWaypoint]
    fuel_savings: float  # percentage
    time_difference: float  # hours
    cost_savings: float  # USD
    emissions_reduction: float  # percentage
    confidence_score: float
    recommendations: List[str]
    created_at: datetime

class Phase6VesselPerformance:
    def __init__(self):
        self.db_path = "stevedores_vessel_performance.db"
        self.performance_models = {}
        self.optimization_cache = {}
        self.real_time_data = {}
        self.lock = threading.Lock()
        self._initialize_database()
        self._load_performance_models()
        
    def _initialize_database(self):
        """Initialize SQLite database for vessel performance data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Vessel specifications table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS vessel_specifications (
                    vessel_id TEXT PRIMARY KEY,
                    vessel_name TEXT NOT NULL,
                    vessel_type TEXT NOT NULL,
                    specifications TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Performance data table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_data (
                    id TEXT PRIMARY KEY,
                    vessel_id TEXT NOT NULL,
                    performance_data TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (vessel_id) REFERENCES vessel_specifications (vessel_id)
                )
                ''')
                
                # Optimization results table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS optimization_results (
                    optimization_id TEXT PRIMARY KEY,
                    vessel_id TEXT NOT NULL,
                    optimization_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (vessel_id) REFERENCES vessel_specifications (vessel_id)
                )
                ''')
                
                # Performance models table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_models (
                    model_id TEXT PRIMARY KEY,
                    vessel_type TEXT NOT NULL,
                    model_type TEXT NOT NULL,
                    model_data TEXT NOT NULL,
                    accuracy_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                conn.commit()
                logger.info("Vessel performance database initialized")
                
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            raise
    
    def register_vessel(self, specifications: VesselSpecifications) -> str:
        """Register vessel specifications for performance optimization."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                INSERT OR REPLACE INTO vessel_specifications 
                (vessel_id, vessel_name, vessel_type, specifications)
                VALUES (?, ?, ?, ?)
                ''', (
                    specifications.vessel_id,
                    specifications.vessel_name,
                    specifications.vessel_type.value,
                    json.dumps(asdict(specifications))
                ))
                
                conn.commit()
                
                # Initialize real-time data tracking
                self.real_time_data[specifications.vessel_id] = PerformanceData()
                
                logger.info(f"Vessel {specifications.vessel_id} registered for performance optimization")
                return specifications.vessel_id
                
        except Exception as e:
            logger.error(f"Vessel registration error: {e}")
            raise
    
    def update_performance_data(self, vessel_id: str, performance_data: PerformanceData) -> str:
        """Update real-time vessel performance data."""
        try:
            with self.lock:
                # Store in real-time cache
                self.real_time_data[vessel_id] = performance_data
                
                # Persist to database
                data_id = str(uuid.uuid4())
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                    INSERT INTO performance_data (id, vessel_id, performance_data)
                    VALUES (?, ?, ?)
                    ''', (
                        data_id,
                        vessel_id,
                        json.dumps(asdict(performance_data), default=str)
                    ))
                    
                    conn.commit()
                
                # Trigger real-time optimization if needed
                self._check_optimization_triggers(vessel_id, performance_data)
                
                logger.info(f"Performance data updated for vessel {vessel_id}")
                return data_id
                
        except Exception as e:
            logger.error(f"Performance data update error: {e}")
            raise
    
    def optimize_fuel_consumption(self, vessel_id: str, route_data: List[RouteWaypoint], 
                                 strategy: OptimizationStrategy = OptimizationStrategy.FUEL_SAVINGS) -> OptimizationResult:
        """Optimize vessel fuel consumption for given route."""
        try:
            # Get vessel specifications
            vessel_specs = self._get_vessel_specifications(vessel_id)
            if not vessel_specs:
                raise ValueError(f"Vessel {vessel_id} not found")
            
            # Get historical performance data
            historical_data = self._get_historical_performance(vessel_id)
            
            # Apply optimization algorithms
            optimized_route = self._optimize_route(vessel_specs, route_data, historical_data, strategy)
            
            # Calculate savings and metrics
            savings_analysis = self._calculate_savings(route_data, optimized_route, vessel_specs)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(vessel_specs, optimized_route, strategy)
            
            # Create optimization result
            result = OptimizationResult(
                optimization_id=str(uuid.uuid4()),
                vessel_id=vessel_id,
                strategy=strategy,
                original_route=route_data,
                optimized_route=optimized_route,
                fuel_savings=savings_analysis['fuel_savings'],
                time_difference=savings_analysis['time_difference'],
                cost_savings=savings_analysis['cost_savings'],
                emissions_reduction=savings_analysis['emissions_reduction'],
                confidence_score=savings_analysis['confidence_score'],
                recommendations=recommendations,
                created_at=datetime.now()
            )
            
            # Store optimization result
            self._store_optimization_result(result)
            
            logger.info(f"Fuel optimization completed for vessel {vessel_id}")
            return result
            
        except Exception as e:
            logger.error(f"Fuel optimization error: {e}")
            raise
    
    def optimize_route_efficiency(self, vessel_id: str, start_port: Tuple[float, float], 
                                 end_port: Tuple[float, float], departure_time: datetime) -> OptimizationResult:
        """Optimize route efficiency considering weather, currents, and traffic."""
        try:
            # Get vessel specifications
            vessel_specs = self._get_vessel_specifications(vessel_id)
            
            # Generate route options
            route_options = self._generate_route_options(start_port, end_port, departure_time)
            
            # Analyze each route option
            best_route = None
            best_score = float('-inf')
            
            for route in route_options:
                # Get weather forecast for route
                weather_data = self._get_weather_forecast(route)
                
                # Calculate route efficiency score
                efficiency_score = self._calculate_route_efficiency(vessel_specs, route, weather_data)
                
                if efficiency_score > best_score:
                    best_score = efficiency_score
                    best_route = route
            
            # Create optimization result for best route
            if best_route:
                savings_analysis = self._analyze_route_savings(vessel_specs, best_route)
                
                result = OptimizationResult(
                    optimization_id=str(uuid.uuid4()),
                    vessel_id=vessel_id,
                    strategy=OptimizationStrategy.BALANCED,
                    original_route=[],  # No original route for new planning
                    optimized_route=best_route,
                    fuel_savings=savings_analysis['fuel_savings'],
                    time_difference=savings_analysis['time_difference'],
                    cost_savings=savings_analysis['cost_savings'],
                    emissions_reduction=savings_analysis['emissions_reduction'],
                    confidence_score=best_score,
                    recommendations=self._generate_route_recommendations(best_route),
                    created_at=datetime.now()
                )
                
                self._store_optimization_result(result)
                return result
            else:
                raise ValueError("No viable route found")
                
        except Exception as e:
            logger.error(f"Route optimization error: {e}")
            raise
    
    def get_real_time_performance(self, vessel_id: str) -> Dict[str, Any]:
        """Get current real-time performance metrics for vessel."""
        try:
            with self.lock:
                if vessel_id not in self.real_time_data:
                    return {"error": "Vessel not found in real-time data"}
                
                performance_data = self.real_time_data[vessel_id]
                vessel_specs = self._get_vessel_specifications(vessel_id)
                
                # Calculate efficiency metrics
                metrics = {
                    "vessel_id": vessel_id,
                    "current_speed": performance_data.speed,
                    "fuel_consumption_rate": performance_data.fuel_consumption,
                    "engine_efficiency": self._calculate_engine_efficiency(performance_data, vessel_specs),
                    "fuel_efficiency_index": self._calculate_fuel_efficiency_index(performance_data, vessel_specs),
                    "emissions_rate": self._calculate_emissions_rate(performance_data),
                    "performance_score": self._calculate_performance_score(performance_data, vessel_specs),
                    "recommendations": self._get_real_time_recommendations(performance_data, vessel_specs),
                    "timestamp": performance_data.timestamp.isoformat()
                }
                
                return metrics
                
        except Exception as e:
            logger.error(f"Real-time performance error: {e}")
            return {"error": str(e)}
    
    def generate_performance_report(self, vessel_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Generate comprehensive performance report for specified period."""
        try:
            # Get historical performance data
            historical_data = self._get_performance_data_range(vessel_id, start_date, end_date)
            
            if not historical_data:
                return {"error": "No performance data found for specified period"}
            
            # Calculate performance statistics
            stats = self._calculate_performance_statistics(historical_data)
            
            # Get optimization history
            optimization_history = self._get_optimization_history(vessel_id, start_date, end_date)
            
            # Generate insights and trends
            insights = self._generate_performance_insights(historical_data, optimization_history)
            
            report = {
                "vessel_id": vessel_id,
                "report_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "performance_statistics": stats,
                "optimization_summary": {
                    "total_optimizations": len(optimization_history),
                    "total_fuel_savings": sum(opt.get('fuel_savings', 0) for opt in optimization_history),
                    "total_cost_savings": sum(opt.get('cost_savings', 0) for opt in optimization_history),
                    "average_confidence_score": np.mean([opt.get('confidence_score', 0) for opt in optimization_history]) if optimization_history else 0
                },
                "performance_trends": insights['trends'],
                "efficiency_metrics": insights['efficiency'],
                "recommendations": insights['recommendations'],
                "generated_at": datetime.now().isoformat()
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Performance report generation error: {e}")
            return {"error": str(e)}
    
    def _load_performance_models(self):
        """Load ML models for performance prediction."""
        if not ML_AVAILABLE:
            logger.info("ML libraries not available, using mock models")
            return
            
        try:
            # Load or train models for different vessel types
            for vessel_type in VesselType:
                self.performance_models[vessel_type.value] = {
                    'fuel_consumption': RandomForestRegressor(n_estimators=100),
                    'speed_optimization': LinearRegression(),
                    'maintenance_prediction': RandomForestRegressor(n_estimators=50)
                }
            
            logger.info("Performance models loaded")
            
        except Exception as e:
            logger.error(f"Model loading error: {e}")
    
    def _get_vessel_specifications(self, vessel_id: str) -> Optional[VesselSpecifications]:
        """Retrieve vessel specifications from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT specifications FROM vessel_specifications WHERE vessel_id = ?', (vessel_id,))
                result = cursor.fetchone()
                
                if result:
                    specs_data = json.loads(result[0])
                    return VesselSpecifications(**specs_data)
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving vessel specifications: {e}")
            return None
    
    def _optimize_route(self, vessel_specs: VesselSpecifications, route_data: List[RouteWaypoint], 
                       historical_data: List[Dict], strategy: OptimizationStrategy) -> List[RouteWaypoint]:
        """Apply route optimization algorithms."""
        optimized_route = []
        
        for i, waypoint in enumerate(route_data):
            optimized_waypoint = RouteWaypoint(
                latitude=waypoint.latitude,
                longitude=waypoint.longitude,
                eta=waypoint.eta,
                speed_recommendation=self._optimize_speed_for_waypoint(vessel_specs, waypoint, strategy),
                fuel_estimate=self._estimate_fuel_consumption(vessel_specs, waypoint),
                weather_forecast=self._get_waypoint_weather(waypoint)
            )
            optimized_route.append(optimized_waypoint)
        
        return optimized_route
    
    def _calculate_savings(self, original_route: List[RouteWaypoint], optimized_route: List[RouteWaypoint], 
                          vessel_specs: VesselSpecifications) -> Dict[str, float]:
        """Calculate fuel and cost savings from optimization."""
        original_fuel = sum(wp.fuel_estimate for wp in original_route)
        optimized_fuel = sum(wp.fuel_estimate for wp in optimized_route)
        
        fuel_savings = ((original_fuel - optimized_fuel) / original_fuel) * 100 if original_fuel > 0 else 0
        
        # Mock calculations for demonstration
        cost_savings = fuel_savings * 500  # Assuming $500 per percentage point of fuel saved
        emissions_reduction = fuel_savings * 0.8  # Emissions roughly correlate with fuel consumption
        time_difference = 0.5  # Mock time difference
        confidence_score = 0.85  # Mock confidence score
        
        return {
            'fuel_savings': fuel_savings,
            'cost_savings': cost_savings,
            'emissions_reduction': emissions_reduction,
            'time_difference': time_difference,
            'confidence_score': confidence_score
        }
    
    def _generate_recommendations(self, vessel_specs: VesselSpecifications, optimized_route: List[RouteWaypoint], 
                                 strategy: OptimizationStrategy) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = [
            f"Maintain optimal speed of {optimized_route[0].speed_recommendation:.1f} knots",
            "Monitor weather conditions for route adjustments",
            "Consider fuel efficiency when adjusting engine load"
        ]
        
        if strategy == OptimizationStrategy.ECO_FRIENDLY:
            recommendations.append("Prioritize emissions reduction measures")
        elif strategy == OptimizationStrategy.TIME_CRITICAL:
            recommendations.append("Balance speed optimization with fuel efficiency")
        
        return recommendations
    
    def _store_optimization_result(self, result: OptimizationResult):
        """Store optimization result in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                INSERT INTO optimization_results (optimization_id, vessel_id, optimization_data)
                VALUES (?, ?, ?)
                ''', (
                    result.optimization_id,
                    result.vessel_id,
                    json.dumps(asdict(result), default=str)
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error storing optimization result: {e}")
    
    def _check_optimization_triggers(self, vessel_id: str, performance_data: PerformanceData):
        """Check if real-time data triggers optimization recommendations."""
        # Mock trigger logic
        if performance_data.fuel_consumption > 5.0:  # High fuel consumption threshold
            logger.warning(f"High fuel consumption detected for vessel {vessel_id}: {performance_data.fuel_consumption}")
    
    def _get_historical_performance(self, vessel_id: str) -> List[Dict]:
        """Get historical performance data for vessel."""
        # Mock historical data
        return [{"fuel_consumption": 4.5, "speed": 12.0, "efficiency": 0.85}]
    
    def _generate_route_options(self, start_port: Tuple[float, float], end_port: Tuple[float, float], 
                               departure_time: datetime) -> List[List[RouteWaypoint]]:
        """Generate multiple route options."""
        # Mock route generation
        route = [
            RouteWaypoint(start_port[0], start_port[1], departure_time, 12.0, 4.5, {}),
            RouteWaypoint(end_port[0], end_port[1], departure_time + timedelta(hours=24), 12.0, 4.5, {})
        ]
        return [route]
    
    def _get_weather_forecast(self, route: List[RouteWaypoint]) -> Dict[str, Any]:
        """Get weather forecast for route."""
        return {"wind_speed": 15, "wave_height": 2.5, "visibility": "good"}
    
    def _calculate_route_efficiency(self, vessel_specs: VesselSpecifications, route: List[RouteWaypoint], 
                                   weather_data: Dict[str, Any]) -> float:
        """Calculate route efficiency score."""
        return 0.85  # Mock efficiency score
    
    def _analyze_route_savings(self, vessel_specs: VesselSpecifications, route: List[RouteWaypoint]) -> Dict[str, float]:
        """Analyze potential savings for route."""
        return {
            'fuel_savings': 12.5,
            'time_difference': -0.5,
            'cost_savings': 6250,
            'emissions_reduction': 10.0
        }
    
    def _generate_route_recommendations(self, route: List[RouteWaypoint]) -> List[str]:
        """Generate route-specific recommendations."""
        return ["Monitor weather conditions", "Maintain optimal speed", "Consider alternative routes if weather deteriorates"]
    
    def _calculate_engine_efficiency(self, performance_data: PerformanceData, vessel_specs: VesselSpecifications) -> float:
        """Calculate current engine efficiency."""
        if vessel_specs and performance_data.engine_load > 0:
            return min(1.0, (performance_data.speed / vessel_specs.service_speed) / (performance_data.engine_load / 100))
        return 0.0
    
    def _calculate_fuel_efficiency_index(self, performance_data: PerformanceData, vessel_specs: VesselSpecifications) -> float:
        """Calculate fuel efficiency index."""
        if performance_data.fuel_consumption > 0 and performance_data.speed > 0:
            return performance_data.speed / performance_data.fuel_consumption
        return 0.0
    
    def _calculate_emissions_rate(self, performance_data: PerformanceData) -> float:
        """Calculate current emissions rate."""
        return performance_data.fuel_consumption * 3.1  # CO2 factor
    
    def _calculate_performance_score(self, performance_data: PerformanceData, vessel_specs: VesselSpecifications) -> float:
        """Calculate overall performance score."""
        efficiency = self._calculate_engine_efficiency(performance_data, vessel_specs)
        fuel_efficiency = self._calculate_fuel_efficiency_index(performance_data, vessel_specs)
        return (efficiency + min(fuel_efficiency / 3, 1.0)) / 2
    
    def _get_real_time_recommendations(self, performance_data: PerformanceData, vessel_specs: VesselSpecifications) -> List[str]:
        """Get real-time optimization recommendations."""
        recommendations = []
        
        if performance_data.fuel_consumption > 5.0:
            recommendations.append("Reduce engine load to improve fuel efficiency")
        
        if performance_data.speed < vessel_specs.service_speed * 0.8:
            recommendations.append("Consider increasing speed for better schedule adherence")
        
        return recommendations
    
    def _get_performance_data_range(self, vessel_id: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get performance data for date range."""
        # Mock performance data
        return [{"fuel_consumption": 4.5, "speed": 12.0, "timestamp": datetime.now().isoformat()}]
    
    def _get_optimization_history(self, vessel_id: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get optimization history for period."""
        # Mock optimization history
        return [{"fuel_savings": 10.5, "cost_savings": 5250, "confidence_score": 0.88}]
    
    def _calculate_performance_statistics(self, historical_data: List[Dict]) -> Dict[str, Any]:
        """Calculate performance statistics."""
        return {
            "average_fuel_consumption": 4.5,
            "average_speed": 12.0,
            "efficiency_trend": "improving",
            "total_distance": 2400.0
        }
    
    def _generate_performance_insights(self, historical_data: List[Dict], optimization_history: List[Dict]) -> Dict[str, Any]:
        """Generate performance insights and trends."""
        return {
            "trends": {"fuel_efficiency": "improving", "speed_consistency": "stable"},
            "efficiency": {"overall_score": 0.82, "fuel_efficiency": 0.78, "time_efficiency": 0.86},
            "recommendations": ["Continue current optimization strategy", "Monitor weather impact on performance"]
        }
    
    def _optimize_speed_for_waypoint(self, vessel_specs: VesselSpecifications, waypoint: RouteWaypoint, 
                                    strategy: OptimizationStrategy) -> float:
        """Optimize speed for specific waypoint."""
        base_speed = vessel_specs.service_speed
        
        if strategy == OptimizationStrategy.FUEL_SAVINGS:
            return base_speed * 0.9  # Reduce speed for fuel savings
        elif strategy == OptimizationStrategy.TIME_CRITICAL:
            return min(base_speed * 1.1, vessel_specs.max_speed)  # Increase speed
        else:
            return base_speed
    
    def _estimate_fuel_consumption(self, vessel_specs: VesselSpecifications, waypoint: RouteWaypoint) -> float:
        """Estimate fuel consumption for waypoint."""
        # Mock fuel consumption calculation
        return 4.5
    
    def _get_waypoint_weather(self, waypoint: RouteWaypoint) -> Dict[str, Any]:
        """Get weather forecast for waypoint."""
        return {"wind_speed": 12, "wave_height": 1.8, "temperature": 15}

def main():
    """Demonstrate Phase 6 vessel performance optimization capabilities."""
    print("=== Stevedores 3.0 Phase 6 - Vessel Performance Optimization ===")
    
    # Initialize performance optimization system
    performance_system = Phase6VesselPerformance()
    
    # Register test vessel
    vessel_specs = VesselSpecifications(
        vessel_id="PERF_001",
        vessel_name="Efficiency Pioneer",
        vessel_type=VesselType.CONTAINER,
        length=300.0,
        beam=48.0,
        draft=14.5,
        gross_tonnage=95000,
        deadweight_tonnage=108000,
        max_speed=24.0,
        service_speed=20.0,
        engine_power=52000,
        fuel_capacity=4500,
        cargo_capacity=9000
    )
    
    vessel_id = performance_system.register_vessel(vessel_specs)
    print(f"✓ Vessel registered: {vessel_id}")
    
    # Update performance data
    performance_data = PerformanceData()
    performance_data.speed = 18.5
    performance_data.fuel_consumption = 4.8
    performance_data.engine_load = 75.0
    performance_data.cargo_load = 85.0
    performance_data.weather_conditions = {"wind_speed": 15, "sea_state": 3}
    
    data_id = performance_system.update_performance_data(vessel_id, performance_data)
    print(f"✓ Performance data updated: {data_id}")
    
    # Optimize fuel consumption
    route_waypoints = [
        RouteWaypoint(51.5074, -0.1278, datetime.now(), 18.0, 4.5, {}),  # London
        RouteWaypoint(40.7128, -74.0060, datetime.now() + timedelta(days=5), 18.0, 4.5, {})  # New York
    ]
    
    optimization_result = performance_system.optimize_fuel_consumption(
        vessel_id, route_waypoints, OptimizationStrategy.FUEL_SAVINGS
    )
    print(f"✓ Fuel optimization completed: {optimization_result.fuel_savings:.1f}% savings")
    
    # Get real-time performance
    real_time_metrics = performance_system.get_real_time_performance(vessel_id)
    print(f"✓ Real-time performance score: {real_time_metrics.get('performance_score', 0):.2f}")
    
    # Generate performance report
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    report = performance_system.generate_performance_report(vessel_id, start_date, end_date)
    print(f"✓ Performance report generated for 30-day period")
    
    print(f"\n=== Performance Optimization Summary ===")
    print(f"Fuel Savings: {optimization_result.fuel_savings:.1f}%")
    print(f"Cost Savings: ${optimization_result.cost_savings:,.2f}")
    print(f"Emissions Reduction: {optimization_result.emissions_reduction:.1f}%")
    print(f"Confidence Score: {optimization_result.confidence_score:.2f}")
    print(f"Recommendations: {len(optimization_result.recommendations)}")

if __name__ == "__main__":
    main()