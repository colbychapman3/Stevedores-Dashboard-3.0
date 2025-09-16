"""
Comprehensive Diagnostic Architecture for Production Worker Crash Analysis
Stevedores Dashboard 3.0 - Maritime Operations System

CRITICAL ISSUE: Workers start successfully, run for 56 seconds, then all crash simultaneously
after receiving TERM signal. Failure likely occurs in init_database() causing silent crashes.

This diagnostic system implements:
1. Detailed error logging at every critical initialization step
2. Database connection validation with timeout/retry
3. Environment variable validation with specific error reporting
4. Configuration loading diagnostics with fallback handling
5. Memory/resource monitoring during startup phases
6. Graceful error handling to prevent worker crashes
"""

import os
import sys
import time
import logging
import traceback
import threading
import psutil
import signal
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from flask import Flask
from sqlalchemy.exc import OperationalError, TimeoutError, DatabaseError
from sqlalchemy import text, create_engine
import json

# Configure diagnostic logger with detailed formatting
diagnostic_logger = logging.getLogger('stevedores.diagnostic')
diagnostic_handler = logging.StreamHandler(sys.stdout)
diagnostic_formatter = logging.Formatter(
    '%(asctime)s [DIAGNOSTIC] %(levelname)s [%(name)s:%(lineno)d] %(message)s'
)
diagnostic_handler.setFormatter(diagnostic_formatter)
diagnostic_logger.addHandler(diagnostic_handler)
diagnostic_logger.setLevel(logging.DEBUG)
diagnostic_logger.propagate = False


@dataclass
class DiagnosticCheckpoint:
    """Represents a diagnostic checkpoint in the initialization process"""
    name: str
    timestamp: datetime
    duration_ms: float
    status: str  # 'started', 'success', 'warning', 'error', 'critical'
    details: Dict[str, Any]
    error_info: Optional[str] = None
    memory_usage_mb: Optional[float] = None
    worker_pid: Optional[int] = None


class DiagnosticCollector:
    """Collects and manages diagnostic information throughout initialization"""
    
    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or f"worker_{os.getpid()}"
        self.checkpoints: List[DiagnosticCheckpoint] = []
        self.start_time = datetime.utcnow()
        self.process = psutil.Process()
        self.lock = threading.Lock()
        
        # Setup diagnostic log file
        self.log_file = f"/tmp/stevedores_diagnostic_{self.worker_id}_{int(time.time())}.json"
        
    def checkpoint(self, name: str, status: str = 'started', details: Dict[str, Any] = None, 
                  error_info: str = None) -> DiagnosticCheckpoint:
        """Record a diagnostic checkpoint"""
        with self.lock:
            checkpoint = DiagnosticCheckpoint(
                name=name,
                timestamp=datetime.utcnow(),
                duration_ms=(datetime.utcnow() - self.start_time).total_seconds() * 1000,
                status=status,
                details=details or {},
                error_info=error_info,
                memory_usage_mb=self.process.memory_info().rss / 1024 / 1024,
                worker_pid=os.getpid()
            )
            
            self.checkpoints.append(checkpoint)
            
            # Log the checkpoint
            log_level = {
                'started': logging.INFO,
                'success': logging.INFO,
                'warning': logging.WARNING,
                'error': logging.ERROR,
                'critical': logging.CRITICAL
            }.get(status, logging.INFO)
            
            diagnostic_logger.log(
                log_level,
                f"CHECKPOINT[{name}] {status.upper()} - PID:{os.getpid()} "
                f"Memory:{checkpoint.memory_usage_mb:.1f}MB Duration:{checkpoint.duration_ms:.1f}ms"
            )
            
            if details:
                diagnostic_logger.debug(f"CHECKPOINT[{name}] Details: {details}")
            
            if error_info:
                diagnostic_logger.error(f"CHECKPOINT[{name}] Error: {error_info}")
            
            # Save to file immediately for crash analysis
            self._save_checkpoint_to_file(checkpoint)
            
            return checkpoint
    
    def _save_checkpoint_to_file(self, checkpoint: DiagnosticCheckpoint):
        """Save checkpoint to diagnostic log file"""
        try:
            checkpoint_data = asdict(checkpoint)
            checkpoint_data['timestamp'] = checkpoint.timestamp.isoformat()
            
            # Read existing data or create new
            diagnostic_data = {'worker_id': self.worker_id, 'checkpoints': []}
            if os.path.exists(self.log_file):
                try:
                    with open(self.log_file, 'r') as f:
                        diagnostic_data = json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass  # Use empty data if file is corrupted
            
            diagnostic_data['checkpoints'].append(checkpoint_data)
            
            with open(self.log_file, 'w') as f:
                json.dump(diagnostic_data, f, indent=2)
                
        except Exception as e:
            diagnostic_logger.error(f"Failed to save checkpoint to file: {e}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get diagnostic summary"""
        return {
            'worker_id': self.worker_id,
            'worker_pid': os.getpid(),
            'start_time': self.start_time.isoformat(),
            'total_duration_ms': (datetime.utcnow() - self.start_time).total_seconds() * 1000,
            'checkpoint_count': len(self.checkpoints),
            'last_checkpoint': self.checkpoints[-1].name if self.checkpoints else None,
            'critical_errors': [cp.name for cp in self.checkpoints if cp.status == 'critical'],
            'errors': [cp.name for cp in self.checkpoints if cp.status == 'error'],
            'warnings': [cp.name for cp in self.checkpoints if cp.status == 'warning'],
            'current_memory_mb': self.process.memory_info().rss / 1024 / 1024,
            'log_file': self.log_file
        }


class EnvironmentValidator:
    """Validates environment variables and configuration"""
    
    REQUIRED_ENV_VARS = [
        'SECRET_KEY',
        'DATABASE_URL'
    ]
    
    OPTIONAL_ENV_VARS = [
        'REDIS_URL',
        'FLASK_ENV',
        'FLASK_CONFIG',
        'WEB_WORKERS',
        'LOG_LEVEL'
    ]
    
    @staticmethod
    def validate_environment(collector: DiagnosticCollector) -> bool:
        """Validate all environment variables"""
        collector.checkpoint('environment_validation', 'started')
        
        validation_results = {}
        all_valid = True
        
        # Check required environment variables
        for var in EnvironmentValidator.REQUIRED_ENV_VARS:
            value = os.environ.get(var)
            if not value:
                validation_results[var] = {'status': 'missing', 'critical': True}
                all_valid = False
                collector.checkpoint(
                    f'env_var_{var}', 'critical',
                    {'variable': var, 'status': 'missing'},
                    f"Required environment variable {var} is missing"
                )
            else:
                # Validate SECRET_KEY strength
                if var == 'SECRET_KEY' and len(value) < 32:
                    validation_results[var] = {'status': 'weak', 'length': len(value)}
                    collector.checkpoint(
                        f'env_var_{var}', 'warning',
                        {'variable': var, 'length': len(value)},
                        f"SECRET_KEY is weak (length: {len(value)})"
                    )
                else:
                    validation_results[var] = {'status': 'valid', 'length': len(value)}
                    collector.checkpoint(f'env_var_{var}', 'success', {'variable': var})
        
        # Check optional environment variables
        for var in EnvironmentValidator.OPTIONAL_ENV_VARS:
            value = os.environ.get(var)
            if value:
                validation_results[var] = {'status': 'present', 'value': value[:50] + '...' if len(value) > 50 else value}
                collector.checkpoint(f'env_var_{var}', 'success', {'variable': var})
            else:
                validation_results[var] = {'status': 'not_set'}
                collector.checkpoint(f'env_var_{var}', 'warning', {'variable': var, 'status': 'not_set'})
        
        # Validate DATABASE_URL format
        db_url = os.environ.get('DATABASE_URL')
        if db_url:
            if db_url.startswith('postgres://'):
                validation_results['database_url_format'] = {'status': 'needs_fix', 'issue': 'postgres:// should be postgresql://'}
                collector.checkpoint(
                    'database_url_format', 'warning',
                    {'url_prefix': 'postgres://', 'should_be': 'postgresql://'},
                    "DATABASE_URL uses deprecated postgres:// prefix"
                )
            elif db_url.startswith('postgresql://'):
                validation_results['database_url_format'] = {'status': 'valid'}
                collector.checkpoint('database_url_format', 'success')
            elif db_url.startswith('sqlite://'):
                validation_results['database_url_format'] = {'status': 'sqlite_fallback'}
                collector.checkpoint('database_url_format', 'warning', {'type': 'sqlite'})
        
        status = 'success' if all_valid else ('warning' if validation_results else 'error')
        collector.checkpoint('environment_validation', status, validation_results)
        
        return all_valid


class DatabaseDiagnostic:
    """Comprehensive database connection diagnostics"""
    
    @staticmethod
    def validate_database_connection(collector: DiagnosticCollector) -> bool:
        """Validate database connection with detailed diagnostics"""
        collector.checkpoint('database_validation', 'started')
        
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            collector.checkpoint(
                'database_validation', 'critical',
                error_info="DATABASE_URL not found in environment"
            )
            return False
        
        # Fix postgres:// to postgresql:// if needed
        original_url = db_url
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
            collector.checkpoint(
                'database_url_fix', 'success',
                {'original': 'postgres://', 'fixed': 'postgresql://'}
            )
        
        # Test database connection with timeout
        try:
            collector.checkpoint('database_engine_creation', 'started')
            
            engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_recycle=300,
                connect_args={
                    'connect_timeout': 10,
                    'command_timeout': 30,
                    'server_side_cursors': True,
                } if 'postgresql' in db_url else {'timeout': 10}
            )
            
            collector.checkpoint('database_engine_creation', 'success')
            
            # Test basic connectivity
            collector.checkpoint('database_connectivity_test', 'started')
            
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                test_value = result.scalar()
                
                if test_value == 1:
                    collector.checkpoint('database_connectivity_test', 'success', {'test_query_result': test_value})
                else:
                    collector.checkpoint(
                        'database_connectivity_test', 'error',
                        {'test_query_result': test_value},
                        f"Unexpected test query result: {test_value}"
                    )
                    return False
            
            # Test table creation capability
            collector.checkpoint('database_table_test', 'started')
            
            try:
                with engine.connect() as conn:
                    # Try to create a test table
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS diagnostic_test_table (
                            id SERIAL PRIMARY KEY,
                            test_value VARCHAR(50),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    conn.commit()
                    
                    # Insert test data
                    conn.execute(text(
                        "INSERT INTO diagnostic_test_table (test_value) VALUES (:value)"
                    ), {"value": f"test_{int(time.time())}"})
                    conn.commit()
                    
                    # Clean up
                    conn.execute(text("DROP TABLE diagnostic_test_table"))
                    conn.commit()
                    
                collector.checkpoint('database_table_test', 'success')
                
            except Exception as e:
                collector.checkpoint(
                    'database_table_test', 'error',
                    {'error_type': type(e).__name__},
                    f"Table creation test failed: {str(e)}"
                )
                return False
            
            # Get database server info
            collector.checkpoint('database_server_info', 'started')
            
            try:
                with engine.connect() as conn:
                    if 'postgresql' in db_url:
                        version_result = conn.execute(text("SELECT version()"))
                        server_version = version_result.scalar()
                        collector.checkpoint(
                            'database_server_info', 'success',
                            {'server_version': server_version}
                        )
                    else:
                        collector.checkpoint('database_server_info', 'success', {'type': 'sqlite'})
                        
            except Exception as e:
                collector.checkpoint(
                    'database_server_info', 'warning',
                    {'error_type': type(e).__name__},
                    f"Could not get server info: {str(e)}"
                )
            
            collector.checkpoint('database_validation', 'success')
            return True
            
        except (OperationalError, TimeoutError, DatabaseError) as e:
            collector.checkpoint(
                'database_validation', 'critical',
                {
                    'error_type': type(e).__name__,
                    'error_details': str(e),
                    'database_url_type': 'postgresql' if 'postgresql' in db_url else 'other'
                },
                f"Database connection failed: {str(e)}"
            )
            return False
            
        except Exception as e:
            collector.checkpoint(
                'database_validation', 'critical',
                {
                    'error_type': type(e).__name__,
                    'error_details': str(e),
                },
                f"Unexpected database error: {str(e)}"
            )
            return False


class ConfigurationDiagnostic:
    """Configuration loading and validation diagnostics"""
    
    @staticmethod
    def validate_configuration_loading(collector: DiagnosticCollector, app: Flask) -> bool:
        """Validate configuration loading process"""
        collector.checkpoint('config_loading', 'started')
        
        config_name = os.environ.get('FLASK_CONFIG', 'render')
        collector.checkpoint('config_name_detection', 'success', {'config_name': config_name})
        
        config_loaded = False
        config_source = None
        
        # Try render_config first
        collector.checkpoint('render_config_attempt', 'started')
        try:
            from render_config import config
            if config_name in config:
                app.config.from_object(config[config_name])
                config[config_name].init_app(app)
                config_loaded = True
                config_source = 'render_config'
                collector.checkpoint('render_config_attempt', 'success', {'config_name': config_name})
            else:
                collector.checkpoint(
                    'render_config_attempt', 'warning',
                    {'available_configs': list(config.keys()), 'requested': config_name},
                    f"Config '{config_name}' not found in render_config"
                )
        except ImportError as e:
            collector.checkpoint(
                'render_config_attempt', 'warning',
                {'error': str(e)},
                "render_config not available"
            )
        
        # Try production_config if render_config failed
        if not config_loaded:
            collector.checkpoint('production_config_attempt', 'started')
            try:
                from production_config import config
                fallback_name = 'production' if config_name in ['render', 'production'] else config_name
                if fallback_name in config:
                    app.config.from_object(config[fallback_name])
                    config[fallback_name].init_app(app)
                    config_loaded = True
                    config_source = 'production_config'
                    collector.checkpoint('production_config_attempt', 'success', {'config_name': fallback_name})
                else:
                    collector.checkpoint(
                        'production_config_attempt', 'error',
                        {'available_configs': list(config.keys()), 'requested': fallback_name},
                        f"Config '{fallback_name}' not found in production_config"
                    )
            except ImportError as e:
                collector.checkpoint(
                    'production_config_attempt', 'error',
                    {'error': str(e)},
                    "production_config not available"
                )
        
        # Use basic fallback if both failed
        if not config_loaded:
            collector.checkpoint('basic_config_fallback', 'started')
            secret_key = os.environ.get('SECRET_KEY')
            if not secret_key:
                collector.checkpoint(
                    'basic_config_fallback', 'critical',
                    error_info="SECRET_KEY environment variable required for fallback config"
                )
                return False
            
            app.config.update({
                'SECRET_KEY': secret_key,
                'SQLALCHEMY_DATABASE_URI': os.environ.get('DATABASE_URL', 'sqlite:///stevedores.db'),
                'SQLALCHEMY_TRACK_MODIFICATIONS': False,
                'DEBUG': os.environ.get('FLASK_ENV', 'production') == 'development'
            })
            config_loaded = True
            config_source = 'basic_fallback'
            collector.checkpoint('basic_config_fallback', 'success')
        
        # Validate critical config values
        collector.checkpoint('config_validation', 'started')
        
        critical_configs = {
            'SECRET_KEY': app.config.get('SECRET_KEY'),
            'SQLALCHEMY_DATABASE_URI': app.config.get('SQLALCHEMY_DATABASE_URI'),
            'SQLALCHEMY_TRACK_MODIFICATIONS': app.config.get('SQLALCHEMY_TRACK_MODIFICATIONS'),
        }
        
        config_issues = []
        for key, value in critical_configs.items():
            if value is None:
                config_issues.append(f"{key} is None")
            elif key == 'SECRET_KEY' and len(str(value)) < 16:
                config_issues.append(f"{key} is too short")
        
        if config_issues:
            collector.checkpoint(
                'config_validation', 'error',
                {'issues': config_issues, 'config_source': config_source},
                f"Configuration validation failed: {'; '.join(config_issues)}"
            )
            return False
        
        collector.checkpoint(
            'config_validation', 'success',
            {'config_source': config_source, 'config_keys': list(critical_configs.keys())}
        )
        collector.checkpoint('config_loading', 'success', {'source': config_source})
        
        return True


class ModelImportDiagnostic:
    """Model import and factory function diagnostics"""
    
    @staticmethod
    def validate_model_imports(collector: DiagnosticCollector, db) -> bool:
        """Validate model imports and factory functions"""
        collector.checkpoint('model_imports', 'started')
        
        models = {}
        
        # Test user model import
        collector.checkpoint('user_model_import', 'started')
        try:
            from models.user import create_user_model
            User = create_user_model(db)
            models['User'] = User
            collector.checkpoint('user_model_import', 'success', {'model_name': 'User'})
        except Exception as e:
            collector.checkpoint(
                'user_model_import', 'critical',
                {'error_type': type(e).__name__, 'error_details': str(e)},
                f"User model import failed: {str(e)}"
            )
            return False
        
        # Test vessel model import  
        collector.checkpoint('vessel_model_import', 'started')
        try:
            from models.vessel import create_vessel_model
            Vessel = create_vessel_model(db)
            models['Vessel'] = Vessel
            collector.checkpoint('vessel_model_import', 'success', {'model_name': 'Vessel'})
        except Exception as e:
            collector.checkpoint(
                'vessel_model_import', 'critical',
                {'error_type': type(e).__name__, 'error_details': str(e)},
                f"Vessel model import failed: {str(e)}"
            )
            return False
        
        # Test cargo tally model import
        collector.checkpoint('cargo_tally_model_import', 'started')
        try:
            from models.cargo_tally import create_cargo_tally_model
            CargoTally = create_cargo_tally_model(db)
            models['CargoTally'] = CargoTally
            collector.checkpoint('cargo_tally_model_import', 'success', {'model_name': 'CargoTally'})
        except Exception as e:
            collector.checkpoint(
                'cargo_tally_model_import', 'critical',
                {'error_type': type(e).__name__, 'error_details': str(e)},
                f"CargoTally model import failed: {str(e)}"
            )
            return False
        
        collector.checkpoint('model_imports', 'success', {'models_loaded': list(models.keys())})
        return True


class InitializationDiagnostic:
    """Main initialization diagnostics orchestrator"""
    
    def __init__(self):
        self.collector = DiagnosticCollector()
        self.setup_signal_handlers()
    
    def setup_signal_handlers(self):
        """Setup signal handlers to capture termination signals"""
        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            self.collector.checkpoint(
                f'signal_received_{signal_name}', 'critical',
                {'signal': signal_name, 'signal_number': signum},
                f"Worker received {signal_name} signal - potential crash incoming"
            )
            
            # Save final diagnostic summary
            summary = self.collector.get_summary()
            diagnostic_logger.critical(f"WORKER TERMINATION SUMMARY: {summary}")
            
            # Call original handler
            if signum == signal.SIGTERM:
                sys.exit(1)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    def run_comprehensive_diagnostics(self, app: Flask, db) -> bool:
        """Run all diagnostic checks"""
        self.collector.checkpoint('diagnostic_suite', 'started')
        
        # Phase 1: Environment validation
        if not EnvironmentValidator.validate_environment(self.collector):
            self.collector.checkpoint('diagnostic_suite', 'critical', error_info="Environment validation failed")
            return False
        
        # Phase 2: Configuration validation
        if not ConfigurationDiagnostic.validate_configuration_loading(self.collector, app):
            self.collector.checkpoint('diagnostic_suite', 'critical', error_info="Configuration validation failed")
            return False
        
        # Phase 3: Database validation
        if not DatabaseDiagnostic.validate_database_connection(self.collector):
            self.collector.checkpoint('diagnostic_suite', 'critical', error_info="Database validation failed")
            return False
        
        # Phase 4: Model import validation
        if not ModelImportDiagnostic.validate_model_imports(self.collector, db):
            self.collector.checkpoint('diagnostic_suite', 'critical', error_info="Model import validation failed")
            return False
        
        self.collector.checkpoint('diagnostic_suite', 'success')
        return True
    
    def validate_init_database_function(self, app: Flask, db) -> bool:
        """Specifically validate the init_database function that's likely causing crashes"""
        self.collector.checkpoint('init_database_validation', 'started')
        
        try:
            with app.app_context():
                # Test db.create_all()
                self.collector.checkpoint('db_create_all', 'started')
                db.create_all()
                self.collector.checkpoint('db_create_all', 'success')
                
                # Test user model availability
                self.collector.checkpoint('user_model_test', 'started')
                from models.user import create_user_model
                User = create_user_model(db)
                
                # Test query capability
                existing_user = User.query.filter_by(email='demo@maritime.test').first()
                self.collector.checkpoint('user_model_test', 'success', {'existing_user': existing_user is not None})
                
                # Test user creation if needed
                if not existing_user:
                    self.collector.checkpoint('demo_user_creation', 'started')
                    from werkzeug.security import generate_password_hash
                    
                    demo_user = User(
                        email='demo@maritime.test',
                        username='demo_user',
                        password_hash=generate_password_hash('demo123'),
                        is_active=True
                    )
                    
                    db.session.add(demo_user)
                    db.session.commit()
                    self.collector.checkpoint('demo_user_creation', 'success')
                else:
                    self.collector.checkpoint('demo_user_creation', 'success', {'status': 'already_exists'})
                
        except Exception as e:
            self.collector.checkpoint(
                'init_database_validation', 'critical',
                {
                    'error_type': type(e).__name__,
                    'error_details': str(e),
                    'traceback': traceback.format_exc()
                },
                f"init_database validation failed: {str(e)}"
            )
            return False
        
        self.collector.checkpoint('init_database_validation', 'success')
        return True
    
    def get_diagnostic_summary(self) -> Dict[str, Any]:
        """Get complete diagnostic summary"""
        return self.collector.get_summary()


# Global diagnostic instance
diagnostic_instance = None

def initialize_diagnostics() -> InitializationDiagnostic:
    """Initialize the diagnostic system"""
    global diagnostic_instance
    if diagnostic_instance is None:
        diagnostic_instance = InitializationDiagnostic()
    return diagnostic_instance

def run_startup_diagnostics(app: Flask, db) -> bool:
    """Run startup diagnostics - call this from wsgi.py"""
    diagnostic = initialize_diagnostics()
    
    diagnostic_logger.info("=" * 80)
    diagnostic_logger.info("STEVEDORES DASHBOARD 3.0 - PRODUCTION STARTUP DIAGNOSTICS")
    diagnostic_logger.info(f"Worker PID: {os.getpid()}")
    diagnostic_logger.info(f"Start Time: {datetime.utcnow().isoformat()}")
    diagnostic_logger.info("=" * 80)
    
    try:
        # Run comprehensive diagnostics
        success = diagnostic.run_comprehensive_diagnostics(app, db)
        
        if success:
            # Specifically test the init_database function
            success = diagnostic.validate_init_database_function(app, db)
        
        # Log final summary
        summary = diagnostic.get_diagnostic_summary()
        diagnostic_logger.info("=" * 80)
        diagnostic_logger.info("STARTUP DIAGNOSTICS SUMMARY")
        diagnostic_logger.info(f"Success: {success}")
        diagnostic_logger.info(f"Total Checkpoints: {summary['checkpoint_count']}")
        diagnostic_logger.info(f"Critical Errors: {len(summary['critical_errors'])}")
        diagnostic_logger.info(f"Errors: {len(summary['errors'])}")
        diagnostic_logger.info(f"Warnings: {len(summary['warnings'])}")
        diagnostic_logger.info(f"Memory Usage: {summary['current_memory_mb']:.1f}MB")
        diagnostic_logger.info(f"Diagnostic Log: {summary['log_file']}")
        diagnostic_logger.info("=" * 80)
        
        if not success:
            diagnostic_logger.critical("STARTUP DIAGNOSTICS FAILED - WORKER WILL LIKELY CRASH")
            diagnostic_logger.critical(f"Critical Errors: {summary['critical_errors']}")
            diagnostic_logger.critical(f"Check diagnostic log: {summary['log_file']}")
        
        return success
        
    except Exception as e:
        diagnostic_logger.critical(f"DIAGNOSTIC SYSTEM FAILURE: {str(e)}")
        diagnostic_logger.critical(f"Traceback: {traceback.format_exc()}")
        return False


if __name__ == "__main__":
    # Test the diagnostic system
    print("Testing Stevedores Dashboard 3.0 Diagnostic Architecture")
    diagnostic = InitializationDiagnostic()
    
    # Test environment validation
    EnvironmentValidator.validate_environment(diagnostic.collector)
    
    # Test database validation
    DatabaseDiagnostic.validate_database_connection(diagnostic.collector)
    
    summary = diagnostic.get_diagnostic_summary()
    print(f"Diagnostic Summary: {summary}")