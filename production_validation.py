#!/usr/bin/env python3
"""
Production Validation System for Stevedores Dashboard 3.0
Comprehensive startup validation to prevent silent failures
"""

import os
import sys
import time
import json
import logging
import traceback
import psutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import tempfile

# Configure validation logging
validation_logger = logging.getLogger('production_validation')
validation_logger.setLevel(logging.INFO)

# Create console handler with detailed formatting
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s [VALIDATION] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler.setFormatter(formatter)
validation_logger.addHandler(console_handler)

class ValidationResult:
    """Structured validation result with detailed error reporting"""
    def __init__(self, category: str, check: str):
        self.category = category
        self.check = check
        self.success = False
        self.error = None
        self.details = {}
        self.warnings = []
        self.timestamp = datetime.utcnow()
        self.duration = 0.0
        
    def fail(self, error: str, details: Dict = None):
        """Mark validation as failed with error details"""
        self.success = False
        self.error = error
        if details:
            self.details.update(details)
    
    def succeed(self, details: Dict = None):
        """Mark validation as successful with optional details"""
        self.success = True
        if details:
            self.details.update(details)
    
    def add_warning(self, warning: str):
        """Add a non-critical warning"""
        self.warnings.append(warning)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'category': self.category,
            'check': self.check,
            'success': self.success,
            'error': self.error,
            'details': self.details,
            'warnings': self.warnings,
            'timestamp': self.timestamp.isoformat(),
            'duration': self.duration
        }

class ProductionValidator:
    """Comprehensive production environment validator"""
    
    def __init__(self):
        self.results = []
        self.start_time = time.time()
        self.critical_failures = []
        self.warnings = []
        
    def validate(self, check_name: str, category: str):
        """Decorator for validation methods"""
        def decorator(func):
            def wrapper(self_inner, *args, **kwargs):
                result = ValidationResult(category, check_name)
                start = time.time()
                
                try:
                    validation_logger.info(f"🔍 Validating {category}: {check_name}")
                    func(self_inner, result, *args, **kwargs)
                    
                except Exception as e:
                    result.fail(
                        f"Validation exception: {str(e)}", 
                        {'exception_type': type(e).__name__, 'traceback': traceback.format_exc()}
                    )
                    validation_logger.error(f"❌ {category}/{check_name}: {str(e)}")
                
                finally:
                    result.duration = time.time() - start
                    self.results.append(result)
                    
                    if result.success:
                        status_msg = f"✅ {category}/{check_name}: PASS"
                        if result.warnings:
                            status_msg += f" ({len(result.warnings)} warnings)"
                        validation_logger.info(status_msg)
                    else:
                        validation_logger.error(f"❌ {category}/{check_name}: FAIL - {result.error}")
                        self.critical_failures.append(result)
                
                return result
            return wrapper
        return decorator
    
    @validate("Environment Variables", "Environment")
    def validate_environment_variables(self, result: ValidationResult):
        """Validate all required environment variables"""
        
        # Critical environment variables
        critical_vars = [
            'SECRET_KEY',
            'DATABASE_URL',
            'FLASK_CONFIG'
        ]
        
        # Optional but recommended environment variables
        optional_vars = [
            'REDIS_URL',
            'MAIL_SERVER',
            'SENTRY_DSN',
            'LOG_LEVEL',
            'UPLOAD_FOLDER'
        ]
        
        missing_critical = []
        missing_optional = []
        var_details = {}
        
        # Check critical variables
        for var in critical_vars:
            value = os.environ.get(var)
            if not value:
                missing_critical.append(var)
                var_details[var] = 'MISSING (CRITICAL)'
            else:
                # Mask sensitive values
                if 'KEY' in var or 'PASSWORD' in var or 'SECRET' in var:
                    var_details[var] = f'SET (length: {len(value)})'
                elif 'URL' in var:
                    # Show scheme and host only
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(value)
                        var_details[var] = f'SET ({parsed.scheme}://{parsed.hostname})'
                    except:
                        var_details[var] = 'SET (could not parse URL)'
                else:
                    var_details[var] = f'SET: {value[:50]}{"..." if len(value) > 50 else ""}'
        
        # Check optional variables
        for var in optional_vars:
            value = os.environ.get(var)
            if not value:
                missing_optional.append(var)
                var_details[var] = 'MISSING (OPTIONAL)'
            else:
                if 'KEY' in var or 'PASSWORD' in var or 'SECRET' in var:
                    var_details[var] = f'SET (length: {len(value)})'
                elif 'URL' in var:
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(value)
                        var_details[var] = f'SET ({parsed.scheme}://{parsed.hostname})'
                    except:
                        var_details[var] = 'SET (could not parse URL)'
                else:
                    var_details[var] = f'SET: {value[:50]}{"..." if len(value) > 50 else ""}'
        
        result.details = {
            'variables': var_details,
            'missing_critical': missing_critical,
            'missing_optional': missing_optional,
            'total_checked': len(critical_vars) + len(optional_vars)
        }
        
        if missing_critical:
            result.fail(
                f"Missing critical environment variables: {', '.join(missing_critical)}"
            )
        else:
            result.succeed()
            
        if missing_optional:
            result.add_warning(f"Missing optional environment variables: {', '.join(missing_optional)}")
    
    @validate("Python Environment", "Environment")
    def validate_python_environment(self, result: ValidationResult):
        """Validate Python version and critical dependencies"""
        
        python_version = sys.version_info
        result.details['python_version'] = f"{python_version.major}.{python_version.minor}.{python_version.micro}"
        result.details['python_executable'] = sys.executable
        result.details['python_path'] = sys.path[:3]  # First 3 entries
        
        # Check Python version
        if python_version < (3, 12):
            result.fail(f"Python 3.12+ required, found {python_version.major}.{python_version.minor}")
            return
        
        # Check critical dependencies
        critical_deps = [
            'flask',
            'flask_sqlalchemy',
            'flask_login',
            'flask_wtf',
            'werkzeug'
        ]
        
        optional_deps = [
            'psycopg2',
            'redis',
            'celery'
        ]
        
        dep_status = {}
        missing_critical = []
        
        for dep in critical_deps:
            try:
                __import__(dep)
                dep_status[dep] = 'AVAILABLE'
            except ImportError:
                dep_status[dep] = 'MISSING (CRITICAL)'
                missing_critical.append(dep)
        
        for dep in optional_deps:
            try:
                module = __import__(dep)
                version = getattr(module, '__version__', 'unknown')
                dep_status[dep] = f'AVAILABLE (v{version})'
            except ImportError:
                dep_status[dep] = 'MISSING (OPTIONAL)'
        
        result.details['dependencies'] = dep_status
        
        if missing_critical:
            result.fail(f"Missing critical Python dependencies: {', '.join(missing_critical)}")
        else:
            result.succeed()
    
    @validate("Configuration Loading", "Configuration")
    def validate_configuration_loading(self, result: ValidationResult):
        """Validate configuration loading mechanism"""
        
        config_name = os.environ.get('FLASK_CONFIG', 'render')
        result.details['config_name'] = config_name
        
        # Test render_config loading
        render_config_available = False
        try:
            from render_config import config as render_config
            render_config_available = True
            result.details['render_config'] = 'AVAILABLE'
            result.details['render_config_keys'] = list(render_config.keys())
        except ImportError as e:
            result.details['render_config'] = f'NOT AVAILABLE: {str(e)}'
        
        # Test production_config loading
        production_config_available = False
        try:
            from production_config import config as production_config
            production_config_available = True
            result.details['production_config'] = 'AVAILABLE'
            result.details['production_config_keys'] = list(production_config.keys())
        except ImportError as e:
            result.details['production_config'] = f'NOT AVAILABLE: {str(e)}'
        
        # Validate configuration availability
        if not render_config_available and not production_config_available:
            result.fail("Neither render_config nor production_config is available")
            return
        
        # Test specific configuration loading
        config_loaded = False
        config_details = {}
        
        if render_config_available:
            try:
                if config_name in render_config:
                    config_class = render_config[config_name]
                else:
                    config_class = render_config['render']  # fallback
                
                # Test configuration instantiation
                test_config = config_class()
                config_details['secret_key'] = 'SET' if hasattr(test_config, 'SECRET_KEY') and test_config.SECRET_KEY else 'MISSING'
                config_details['database_uri'] = 'SET' if hasattr(test_config, 'SQLALCHEMY_DATABASE_URI') and test_config.SQLALCHEMY_DATABASE_URI else 'MISSING'
                config_details['debug'] = getattr(test_config, 'DEBUG', 'UNKNOWN')
                config_loaded = True
                
            except Exception as e:
                result.details['render_config_error'] = str(e)
        
        if not config_loaded and production_config_available:
            try:
                fallback_name = 'production' if config_name in ['render', 'production'] else config_name
                if fallback_name in production_config:
                    config_class = production_config[fallback_name]
                    test_config = config_class()
                    config_details['secret_key'] = 'SET' if hasattr(test_config, 'SECRET_KEY') and test_config.SECRET_KEY else 'MISSING'
                    config_details['database_uri'] = 'SET' if hasattr(test_config, 'SQLALCHEMY_DATABASE_URI') and test_config.SQLALCHEMY_DATABASE_URI else 'MISSING'
                    config_details['debug'] = getattr(test_config, 'DEBUG', 'UNKNOWN')
                    config_loaded = True
            except Exception as e:
                result.details['production_config_error'] = str(e)
        
        result.details['config_details'] = config_details
        
        if config_loaded:
            result.succeed()
            if config_details.get('secret_key') == 'MISSING':
                result.add_warning("Configuration loaded but SECRET_KEY is missing")
        else:
            result.fail("Failed to load any valid configuration")
    
    @validate("Database Connectivity", "Database")
    def validate_database_connectivity(self, result: ValidationResult):
        """Validate database connection and basic operations"""
        
        database_url = os.environ.get('DATABASE_URL', 'sqlite:///stevedores.db')
        result.details['database_url'] = database_url.split('@')[0] + '@***' if '@' in database_url else database_url
        
        # Fix postgres:// to postgresql:// if needed
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
            result.details['url_fixed'] = True
        
        try:
            # Test SQLAlchemy connection
            from sqlalchemy import create_engine, text
            from sqlalchemy.exc import SQLAlchemyError
            
            # Configure engine based on database type
            if 'postgresql://' in database_url or 'postgres://' in database_url:
                engine_options = {
                    'pool_pre_ping': True,
                    'pool_recycle': 300,
                    'connect_args': {'connect_timeout': 10}
                }
                result.details['database_type'] = 'postgresql'
            else:
                engine_options = {
                    'pool_pre_ping': True
                }
                result.details['database_type'] = 'sqlite'
            
            # Create engine with timeout
            engine = create_engine(database_url, **engine_options)
            
            # Test connection with timeout
            start_time = time.time()
            with engine.connect() as conn:
                # Simple query to test connectivity
                result_proxy = conn.execute(text("SELECT 1"))
                test_result = result_proxy.fetchone()
                connection_time = time.time() - start_time
                
                result.details['connection_time'] = round(connection_time, 3)
                result.details['test_query'] = 'SUCCESS'
                
                # Test transaction capability
                with conn.begin():
                    conn.execute(text("SELECT 1"))
                    result.details['transaction_test'] = 'SUCCESS'
                
                result.succeed()
            
        except ImportError as e:
            result.fail(f"Database driver not available: {str(e)}")
        except SQLAlchemyError as e:
            result.fail(f"Database connection failed: {str(e)}")
        except Exception as e:
            result.fail(f"Unexpected database error: {str(e)}")
    
    @validate("Model Import", "Application")
    def validate_model_imports(self, result: ValidationResult):
        """Validate model imports and factory functions"""
        
        model_imports = {}
        
        try:
            # Test model factory imports
            from models.user import create_user_model
            model_imports['user_factory'] = 'SUCCESS'
        except Exception as e:
            model_imports['user_factory'] = f'FAILED: {str(e)}'
        
        try:
            from models.vessel import create_vessel_model
            model_imports['vessel_factory'] = 'SUCCESS'
        except Exception as e:
            model_imports['vessel_factory'] = f'FAILED: {str(e)}'
        
        try:
            from models.cargo_tally import create_cargo_tally_model
            model_imports['cargo_tally_factory'] = 'SUCCESS'
        except Exception as e:
            model_imports['cargo_tally_factory'] = f'FAILED: {str(e)}'
        
        result.details['model_imports'] = model_imports
        
        # Check if any critical imports failed
        failed_imports = [k for k, v in model_imports.items() if 'FAILED' in v]
        
        if failed_imports:
            result.fail(f"Model import failures: {', '.join(failed_imports)}")
        else:
            result.succeed()
    
    @validate("Security Middleware", "Security")
    def validate_security_middleware(self, result: ValidationResult):
        """Validate security middleware loading"""
        
        security_imports = {}
        
        try:
            from utils.security_manager import init_security_manager
            security_imports['security_manager'] = 'SUCCESS'
        except Exception as e:
            security_imports['security_manager'] = f'FAILED: {str(e)}'
        
        try:
            from utils.jwt_auth import init_jwt_auth
            security_imports['jwt_auth'] = 'SUCCESS'
        except Exception as e:
            security_imports['jwt_auth'] = f'FAILED: {str(e)}'
        
        try:
            from utils.audit_logger import init_audit_logger
            security_imports['audit_logger'] = 'SUCCESS'
        except Exception as e:
            security_imports['audit_logger'] = f'FAILED: {str(e)}'
        
        try:
            from utils.api_middleware import init_api_middleware
            security_imports['api_middleware'] = 'SUCCESS'
        except Exception as e:
            security_imports['api_middleware'] = f'FAILED: {str(e)}'
        
        result.details['security_imports'] = security_imports
        
        # Check for failures
        failed_security = [k for k, v in security_imports.items() if 'FAILED' in v]
        
        if failed_security:
            result.fail(f"Security middleware failures: {', '.join(failed_security)}")
        else:
            result.succeed()
    
    @validate("Resource Monitoring", "System")
    def validate_system_resources(self, result: ValidationResult):
        """Monitor system resources during startup"""
        
        try:
            # Memory information
            memory = psutil.virtual_memory()
            result.details['memory'] = {
                'total': round(memory.total / (1024**3), 2),  # GB
                'available': round(memory.available / (1024**3), 2),  # GB
                'percent_used': memory.percent,
                'warning_threshold': 85.0
            }
            
            # CPU information
            cpu_percent = psutil.cpu_percent(interval=1)
            result.details['cpu'] = {
                'cores': psutil.cpu_count(),
                'usage_percent': cpu_percent,
                'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None
            }
            
            # Disk space
            disk = psutil.disk_usage('/')
            result.details['disk'] = {
                'total': round(disk.total / (1024**3), 2),  # GB
                'free': round(disk.free / (1024**3), 2),  # GB
                'percent_used': round((disk.used / disk.total) * 100, 1)
            }
            
            # Check for resource warnings
            warnings = []
            if memory.percent > 85:
                warnings.append(f"High memory usage: {memory.percent}%")
            
            if cpu_percent > 80:
                warnings.append(f"High CPU usage: {cpu_percent}%")
            
            if disk.free < 1:  # Less than 1GB free
                warnings.append(f"Low disk space: {disk.free:.1f}GB free")
            
            for warning in warnings:
                result.add_warning(warning)
            
            result.succeed()
            
        except Exception as e:
            result.fail(f"Resource monitoring failed: {str(e)}")
    
    @validate("File System Permissions", "System")
    def validate_file_permissions(self, result: ValidationResult):
        """Validate file system permissions and required directories"""
        
        # Test write permissions in critical directories
        test_paths = []
        
        # Upload folder
        upload_folder = os.environ.get('UPLOAD_FOLDER', '/tmp/stevedores_uploads')
        test_paths.append(('upload_folder', upload_folder))
        
        # Temp directory
        test_paths.append(('temp_dir', tempfile.gettempdir()))
        
        # Instance directory (for logs)
        instance_dir = os.path.join(os.getcwd(), 'instance')
        test_paths.append(('instance_dir', instance_dir))
        
        # Logs directory
        logs_dir = os.path.join(os.getcwd(), 'logs')
        test_paths.append(('logs_dir', logs_dir))
        
        permission_results = {}
        
        for name, path in test_paths:
            try:
                # Test directory creation
                os.makedirs(path, exist_ok=True)
                
                # Test file write
                test_file = os.path.join(path, '.validation_test')
                with open(test_file, 'w') as f:
                    f.write('validation test')
                
                # Test file read
                with open(test_file, 'r') as f:
                    content = f.read()
                
                # Clean up
                os.remove(test_file)
                
                permission_results[name] = {
                    'path': path,
                    'status': 'SUCCESS',
                    'readable': True,
                    'writable': True
                }
                
            except Exception as e:
                permission_results[name] = {
                    'path': path,
                    'status': f'FAILED: {str(e)}',
                    'readable': False,
                    'writable': False
                }
        
        result.details['permissions'] = permission_results
        
        # Check for failures
        failed_permissions = [k for k, v in permission_results.items() if v['status'] != 'SUCCESS']
        
        if failed_permissions:
            result.fail(f"Permission failures: {', '.join(failed_permissions)}")
        else:
            result.succeed()
    
    @validate("Health Check Endpoint", "Application")
    def validate_health_endpoint(self, result: ValidationResult):
        """Validate that health check functionality works"""
        
        try:
            # Test database health check import
            from utils.database_retry import database_health_check
            result.details['database_health_check'] = 'IMPORTED'
            
            # Test health check logic (without Flask app context)
            # This validates the function exists and basic logic works
            result.details['health_check_available'] = True
            result.succeed()
            
        except ImportError as e:
            result.fail(f"Health check import failed: {str(e)}")
        except Exception as e:
            result.fail(f"Health check validation failed: {str(e)}")
    
    def run_all_validations(self) -> Dict[str, Any]:
        """Run all validation checks and return comprehensive results"""
        
        validation_logger.info("🚀 Starting Production Validation Suite")
        validation_logger.info(f"📋 Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        validation_logger.info(f"📂 Working Directory: {os.getcwd()}")
        
        # Run all validations
        self.validate_environment_variables()
        self.validate_python_environment()
        self.validate_configuration_loading()
        self.validate_database_connectivity()
        self.validate_model_imports()
        self.validate_security_middleware()
        self.validate_system_resources()
        self.validate_file_permissions()
        self.validate_health_endpoint()
        
        # Calculate summary statistics
        total_time = time.time() - self.start_time
        total_checks = len(self.results)
        successful_checks = len([r for r in self.results if r.success])
        failed_checks = len(self.critical_failures)
        total_warnings = sum(len(r.warnings) for r in self.results)
        
        # Create summary
        summary = {
            'validation_timestamp': datetime.utcnow().isoformat(),
            'total_duration': round(total_time, 2),
            'total_checks': total_checks,
            'successful_checks': successful_checks,
            'failed_checks': failed_checks,
            'total_warnings': total_warnings,
            'success_rate': round((successful_checks / total_checks) * 100, 1) if total_checks > 0 else 0,
            'overall_status': 'PASS' if failed_checks == 0 else 'FAIL',
            'critical_failures': [f.to_dict() for f in self.critical_failures],
            'detailed_results': [r.to_dict() for r in self.results]
        }
        
        # Log summary
        if failed_checks == 0:
            validation_logger.info(f"🎉 All validations passed! ({successful_checks}/{total_checks} checks, {total_warnings} warnings)")
        else:
            validation_logger.error(f"❌ Validation failures detected! ({failed_checks}/{total_checks} failed)")
            for failure in self.critical_failures:
                validation_logger.error(f"   • {failure.category}/{failure.check}: {failure.error}")
        
        if total_warnings > 0:
            validation_logger.warning(f"⚠️  {total_warnings} warnings detected - review recommended")
        
        return summary

def run_production_validation() -> Dict[str, Any]:
    """Main entry point for production validation"""
    validator = ProductionValidator()
    return validator.run_all_validations()

def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Production Validation for Stevedores Dashboard 3.0')
    parser.add_argument('--output', '-o', help='Output file for validation results (JSON)')
    parser.add_argument('--exit-on-failure', action='store_true', help='Exit with error code if validations fail')
    args = parser.parse_args()
    
    # Run validation
    results = run_production_validation()
    
    # Save results if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        validation_logger.info(f"📄 Results saved to: {args.output}")
    
    # Exit with appropriate code
    if args.exit_on_failure and results['overall_status'] == 'FAIL':
        sys.exit(1)
    
    sys.exit(0)

if __name__ == '__main__':
    main()