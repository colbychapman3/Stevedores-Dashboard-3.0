#!/usr/bin/env python3
"""
Startup Validation Script for Stevedores Dashboard 3.0
Run this before deployment to catch issues that could cause silent failures
"""

import os
import sys
import time
import json
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [STARTUP] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
startup_logger = logging.getLogger('startup_validator')

def validate_environment() -> bool:
    """Validate environment setup"""
    startup_logger.info("🔍 Validating environment setup...")
    
    issues = []
    
    # Check Python version
    if sys.version_info < (3, 12):
        issues.append(f"Python 3.12+ required, found {sys.version_info.major}.{sys.version_info.minor}")
    
    # Check critical environment variables
    critical_vars = ['SECRET_KEY', 'DATABASE_URL']
    for var in critical_vars:
        if not os.environ.get(var):
            issues.append(f"Missing critical environment variable: {var}")
    
    # Check file permissions
    test_dirs = [
        '/tmp/stevedores_uploads',
        'instance/logs',
        'logs'
    ]
    
    for test_dir in test_dirs:
        try:
            os.makedirs(test_dir, exist_ok=True)
            test_file = os.path.join(test_dir, 'test_write')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
        except Exception as e:
            issues.append(f"Cannot write to directory {test_dir}: {e}")
    
    if issues:
        startup_logger.error("❌ Environment validation failed:")
        for issue in issues:
            startup_logger.error(f"   • {issue}")
        return False
    else:
        startup_logger.info("✅ Environment validation passed")
        return True

def validate_dependencies() -> bool:
    """Validate Python dependencies"""
    startup_logger.info("🔍 Validating Python dependencies...")
    
    critical_deps = [
        'flask',
        'flask_sqlalchemy',
        'flask_login',
        'flask_wtf',
        'werkzeug',
        'sqlalchemy'
    ]
    
    optional_deps = [
        'psycopg2',
        'psutil',
        'redis'
    ]
    
    missing_critical = []
    missing_optional = []
    
    for dep in critical_deps:
        try:
            __import__(dep)
        except ImportError:
            missing_critical.append(dep)
    
    for dep in optional_deps:
        try:
            __import__(dep)
        except ImportError:
            missing_optional.append(dep)
    
    if missing_critical:
        startup_logger.error("❌ Critical dependencies missing:")
        for dep in missing_critical:
            startup_logger.error(f"   • {dep}")
        startup_logger.error("💡 Run: pip install -r requirements.txt")
        return False
    
    if missing_optional:
        startup_logger.warning("⚠️  Optional dependencies missing:")
        for dep in missing_optional:
            startup_logger.warning(f"   • {dep}")
        startup_logger.warning("💡 Some features may be limited")
    
    startup_logger.info("✅ Dependency validation passed")
    return True

def validate_configuration() -> bool:
    """Validate configuration files"""
    startup_logger.info("🔍 Validating configuration files...")
    
    config_files = ['render_config.py', 'production_config.py']
    config_available = []
    
    for config_file in config_files:
        if os.path.exists(config_file):
            config_available.append(config_file)
            startup_logger.info(f"✅ Found config file: {config_file}")
            
            # Test import
            try:
                config_module = config_file.replace('.py', '')
                __import__(config_module)
                startup_logger.info(f"✅ Config file imports successfully: {config_file}")
            except Exception as e:
                startup_logger.error(f"❌ Config file import failed: {config_file} - {e}")
                return False
    
    if not config_available:
        startup_logger.error("❌ No configuration files found")
        startup_logger.error("💡 Need either render_config.py or production_config.py")
        return False
    
    startup_logger.info("✅ Configuration validation passed")
    return True

def validate_database_connectivity() -> bool:
    """Validate database connectivity"""
    startup_logger.info("🔍 Validating database connectivity...")
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        startup_logger.error("❌ DATABASE_URL not set")
        return False
    
    try:
        from sqlalchemy import create_engine, text
        
        # Fix postgres:// to postgresql:// if needed
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        # Create engine with timeout
        engine = create_engine(database_url, pool_pre_ping=True)
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            test_result = result.fetchone()
        
        startup_logger.info("✅ Database connectivity validated")
        return True
        
    except Exception as e:
        startup_logger.error(f"❌ Database connectivity failed: {e}")
        startup_logger.error("💡 Check DATABASE_URL and database server status")
        return False

def validate_app_import() -> bool:
    """Validate that the app can be imported without errors"""
    startup_logger.info("🔍 Validating app import...")
    
    try:
        # Set required environment variables if not set
        if not os.environ.get('SECRET_KEY'):
            os.environ['SECRET_KEY'] = 'test-secret-key-for-validation'
            startup_logger.warning("⚠️  Using temporary SECRET_KEY for validation")
        
        if not os.environ.get('DATABASE_URL'):
            os.environ['DATABASE_URL'] = 'sqlite:///validation_test.db'
            startup_logger.warning("⚠️  Using temporary DATABASE_URL for validation")
        
        # Try importing the app
        startup_logger.info("📦 Importing app module...")
        from app import app
        startup_logger.info("✅ App import successful")
        
        # Test basic app functionality
        with app.test_request_context():
            startup_logger.info("✅ App context working")
        
        startup_logger.info("✅ App validation passed")
        return True
        
    except Exception as e:
        startup_logger.error(f"❌ App import/validation failed: {e}")
        import traceback
        startup_logger.error(f"🔍 Traceback: {traceback.format_exc()}")
        return False

def run_comprehensive_validation() -> dict:
    """Run all validation checks"""
    startup_logger.info("🚀 Starting comprehensive startup validation...")
    
    validation_start = time.time()
    results = {}
    
    # Run validation checks
    validation_checks = [
        ("environment", validate_environment),
        ("dependencies", validate_dependencies),
        ("configuration", validate_configuration),
        ("database", validate_database_connectivity),
        ("app_import", validate_app_import)
    ]
    
    for check_name, check_func in validation_checks:
        startup_logger.info(f"🔍 Running {check_name} validation...")
        start_time = time.time()
        
        try:
            success = check_func()
            duration = time.time() - start_time
            
            results[check_name] = {
                'success': success,
                'duration': round(duration, 3),
                'error': None
            }
            
        except Exception as e:
            duration = time.time() - start_time
            results[check_name] = {
                'success': False,
                'duration': round(duration, 3),
                'error': str(e)
            }
            startup_logger.error(f"❌ {check_name} validation exception: {e}")
    
    # Calculate summary
    total_duration = time.time() - validation_start
    successful_checks = len([r for r in results.values() if r['success']])
    total_checks = len(results)
    
    summary = {
        'timestamp': time.time(),
        'total_duration': round(total_duration, 2),
        'total_checks': total_checks,
        'successful_checks': successful_checks,
        'failed_checks': total_checks - successful_checks,
        'success_rate': round((successful_checks / total_checks) * 100, 1) if total_checks > 0 else 0,
        'overall_success': successful_checks == total_checks,
        'results': results
    }
    
    # Log summary
    if summary['overall_success']:
        startup_logger.info(f"🎉 All validation checks passed! ({successful_checks}/{total_checks}) in {total_duration:.2f}s")
        startup_logger.info("✅ Application is ready for deployment")
    else:
        startup_logger.error(f"❌ Validation failed! ({summary['failed_checks']}/{total_checks} failed)")
        for check_name, result in results.items():
            if not result['success']:
                startup_logger.error(f"   • {check_name}: {result.get('error', 'Failed')}")
        startup_logger.error("💡 Fix the above issues before deployment")
    
    return summary

def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Startup Validation for Stevedores Dashboard 3.0')
    parser.add_argument('--output', '-o', help='Output file for validation results (JSON)')
    parser.add_argument('--quiet', '-q', action='store_true', help='Suppress non-error output')
    parser.add_argument('--exit-on-failure', action='store_true', help='Exit with error code if validation fails')
    args = parser.parse_args()
    
    if args.quiet:
        logging.getLogger('startup_validator').setLevel(logging.ERROR)
    
    # Run validation
    results = run_comprehensive_validation()
    
    # Save results if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        startup_logger.info(f"📄 Results saved to: {args.output}")
    
    # Exit with appropriate code
    if args.exit_on_failure and not results['overall_success']:
        sys.exit(1)
    
    sys.exit(0 if results['overall_success'] else 1)

if __name__ == '__main__':
    main()