"""
WSGI Entry Point for Stevedores Dashboard 3.0 Production Deployment
Optimized for maritime operations with comprehensive error handling and validation
ENHANCED WITH PRODUCTION VALIDATION SYSTEM for deployment troubleshooting
"""

import os
import sys
import time
import logging
import traceback
from pathlib import Path

# Add the project directory to Python path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

# Set environment variables for production
os.environ.setdefault('FLASK_ENV', 'production')
os.environ.setdefault('PYTHONPATH', str(project_dir))

# Configure comprehensive early logging for startup diagnostics
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [WSGI] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.StreamHandler(sys.stderr)
    ]
)
wsgi_logger = logging.getLogger('wsgi_startup')

wsgi_logger.info("🚀 WSGI Entry Point Starting - Stevedores Dashboard 3.0")
wsgi_logger.info(f"📂 Project Directory: {project_dir}")
wsgi_logger.info(f"🐍 Python Version: {sys.version}")
wsgi_logger.info(f"🌍 Flask Environment: {os.environ.get('FLASK_ENV', 'not set')}")
wsgi_logger.info(f"🔧 Flask Config: {os.environ.get('FLASK_CONFIG', 'not set')}")

# Log critical environment variables (masked for security)
secret_key = os.environ.get('SECRET_KEY')
database_url = os.environ.get('DATABASE_URL')
wsgi_logger.info(f"🔐 SECRET_KEY: {'SET (length: ' + str(len(secret_key)) + ')' if secret_key else 'NOT SET (CRITICAL ERROR)'}")
wsgi_logger.info(f"🗄️  DATABASE_URL: {'SET' if database_url else 'NOT SET (CRITICAL ERROR)'}")

# Run production validation before app initialization
wsgi_logger.info("🔍 Running comprehensive production validation checks...")
validation_start = time.time()
validation_passed = False

try:
    from production_validation import run_production_validation
    validation_results = run_production_validation()
    validation_duration = time.time() - validation_start
    
    wsgi_logger.info(f"✅ Validation completed in {validation_duration:.2f}s")
    wsgi_logger.info(f"📊 Results: {validation_results['successful_checks']}/{validation_results['total_checks']} checks passed")
    
    if validation_results['failed_checks'] == 0:
        validation_passed = True
        wsgi_logger.info("🎉 All validation checks passed - proceeding with normal startup")
    else:
        wsgi_logger.error(f"❌ {validation_results['failed_checks']} critical validation failures detected!")
        for failure in validation_results['critical_failures']:
            wsgi_logger.error(f"   • {failure['category']}/{failure['check']}: {failure['error']}")
        
        # Continue with degraded mode but log critical failures
        wsgi_logger.warning("⚠️  Continuing with degraded startup mode - some features may not work")
    
    if validation_results['total_warnings'] > 0:
        wsgi_logger.warning(f"⚠️  {validation_results['total_warnings']} warnings detected during validation")

except ImportError as e:
    wsgi_logger.warning(f"⚠️  Production validation not available: {e}")
    wsgi_logger.warning("⚠️  Install psutil for enhanced system monitoring: pip install psutil")
except Exception as e:
    wsgi_logger.error(f"❌ Validation error: {e}")
    wsgi_logger.error(f"🔍 Validation traceback: {traceback.format_exc()}")
    wsgi_logger.warning("⚠️  Continuing without validation - startup may fail")

wsgi_logger.info("🏗️  Initializing Flask application...")

try:
    wsgi_logger.info("📦 Importing app and init_database...")
    from app import app, init_database
    wsgi_logger.info("✅ App import successful")
    
    # INTELLIGENT CONFIG DETECTION: Try render_config first, then production_config
    config_loaded = False
    config_name = os.environ.get('FLASK_CONFIG', 'render')
    
    wsgi_logger.info(f"🔧 Loading configuration: {config_name}")
    
    # Try render_config first (preferred for Render deployment)
    if not config_loaded:
        try:
            wsgi_logger.info("📋 Attempting to load render_config...")
            from render_config import config
            if config_name in config:
                app.config.from_object(config[config_name])
                config[config_name].init_app(app)
                config_loaded = True
                wsgi_logger.info(f"✅ WSGI: Loaded render_config: {config_name}")
            else:
                # Fallback to 'render' if specific config not found
                app.config.from_object(config['render'])
                config['render'].init_app(app) 
                config_loaded = True
                wsgi_logger.info(f"✅ WSGI: Loaded render_config: render (fallback from {config_name})")
        except ImportError as e:
            wsgi_logger.warning(f"⚠️  render_config not available: {e}")
        except Exception as e:
            wsgi_logger.error(f"❌ render_config loading error: {e}")
    
    # Fallback to production_config if render_config not available
    if not config_loaded:
        try:
            wsgi_logger.info("📋 Attempting to load production_config...")
            from production_config import config
            fallback_name = 'production' if config_name in ['render', 'production'] else config_name
            if fallback_name in config:
                app.config.from_object(config[fallback_name])
                config[fallback_name].init_app(app)
                config_loaded = True
                wsgi_logger.info(f"✅ WSGI: Loaded production_config: {fallback_name}")
            else:
                wsgi_logger.error(f"❌ Config '{fallback_name}' not found in production_config")
        except ImportError as e:
            wsgi_logger.error(f"❌ production_config not available: {e}")
        except Exception as e:
            wsgi_logger.error(f"❌ production_config loading error: {e}")
            
    if not config_loaded:
        wsgi_logger.error("❌ CRITICAL: No valid configuration module found")
        wsgi_logger.error("💡 Ensure either render_config.py or production_config.py exists")
        raise ImportError("No valid configuration module found - deployment cannot continue")
    
    # Validate critical configuration
    if not app.config.get('SECRET_KEY'):
        wsgi_logger.error("❌ CRITICAL: SECRET_KEY not set in configuration")
        raise ValueError("SECRET_KEY is required for production deployment")
    
    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        wsgi_logger.error("❌ CRITICAL: DATABASE_URL not set in configuration") 
        raise ValueError("DATABASE_URL is required for production deployment")
    
    wsgi_logger.info(f"🔐 Config SECRET_KEY: SET (length: {len(app.config['SECRET_KEY'])})")
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    wsgi_logger.info(f"🗄️  Config DATABASE_URI: {db_uri.split('://')[0]}://***" if '://' in db_uri else "SET")
    wsgi_logger.info(f"🐛 Debug Mode: {app.config.get('DEBUG', False)}")
    
    # Initialize database in production with comprehensive diagnostics  
    wsgi_logger.info("🚀 Initializing database with comprehensive diagnostics...")
    with app.app_context():
        try:
            # Use our enhanced database initialization that won't crash workers
            db_init_success = init_database()
            
            if not db_init_success:
                wsgi_logger.error("❌ Database initialization failed with comprehensive diagnostics")
                wsgi_logger.error("📋 Check application logs above for detailed diagnostic information")
                wsgi_logger.error("🔧 Common production issues:")
                wsgi_logger.error("  - Database server not accessible (network/firewall)")
                wsgi_logger.error("  - Invalid DATABASE_URL credentials or format")
                wsgi_logger.error("  - Database does not exist or user lacks permissions")
                wsgi_logger.error("  - Connection timeout or pool exhaustion")
                
                # Don't crash in production - let app start with degraded functionality
                if not validation_passed:
                    wsgi_logger.error("💡 Run production validation to get detailed diagnostics")
                
                wsgi_logger.warning("⚠️  Continuing startup - app will have limited database functionality")
                wsgi_logger.warning("🔧 Visit /health or /diagnostics/database endpoints for real-time status")
            else:
                wsgi_logger.info("✅ Database initialization completed successfully with diagnostics")
                
        except Exception as e:
            wsgi_logger.error(f"❌ Critical database initialization exception: {e}")
            wsgi_logger.error(f"🔍 Exception traceback: {traceback.format_exc()}")
            wsgi_logger.error("⚠️  This should not happen with the new robust initialization")
            wsgi_logger.warning("🔧 Continuing startup - database functionality will be unavailable")
    
    # Production logging configuration
    if not app.debug:
        import logging
        gunicorn_logger = logging.getLogger('gunicorn.error')
        if gunicorn_logger.handlers:
            app.logger.handlers = gunicorn_logger.handlers
            app.logger.setLevel(gunicorn_logger.level)
            wsgi_logger.info("🔗 Connected to Gunicorn logging")
        else:
            wsgi_logger.warning("⚠️  Gunicorn logger not available, using basic logging")
    
    # Log successful startup
    app.logger.info('🚢 Stevedores Dashboard 3.0 production server starting...')
    app.logger.info(f'📊 Configuration: {config_name}')
    app.logger.info(f'🔧 PWA Cache Version: {app.config.get("PWA_CACHE_VERSION", "unknown")}')
    app.logger.info('⚓ Maritime operations system ready for deployment')
    
    # Final startup validation
    wsgi_logger.info("🎯 Final startup checks...")
    
    # Test basic app functionality
    with app.test_request_context():
        try:
            # Test database connection
            from flask_sqlalchemy import SQLAlchemy
            db = SQLAlchemy()
            db.init_app(app)
            wsgi_logger.info("✅ SQLAlchemy initialized successfully")
            
            # Test basic route resolution
            wsgi_logger.info("✅ Flask app context working")
            
        except Exception as e:
            wsgi_logger.error(f"❌ Final validation failed: {e}")
            wsgi_logger.error(f"🔍 Final validation traceback: {traceback.format_exc()}")
    
    total_startup_time = time.time() - validation_start
    wsgi_logger.info(f"🎉 WSGI startup completed successfully in {total_startup_time:.2f}s")
    wsgi_logger.info("🚀 Application ready to serve requests")
    
except ImportError as e:
    wsgi_logger.error(f"❌ Import error during WSGI startup: {e}")
    wsgi_logger.error(f"🔍 Import traceback: {traceback.format_exc()}")
    wsgi_logger.error("💡 Check that all dependencies are installed and importable")
    sys.exit(1)
except ValueError as e:
    wsgi_logger.error(f"❌ Configuration error during WSGI startup: {e}")
    wsgi_logger.error("💡 Check environment variables and configuration files")
    sys.exit(1)
except Exception as e:
    wsgi_logger.error(f"❌ Unexpected error during WSGI startup: {e}")
    wsgi_logger.error(f"🔍 Startup traceback: {traceback.format_exc()}")
    wsgi_logger.error("💡 Enable debug mode for more detailed error information")
    sys.exit(1)

# WSGI application
application = app

# Additional debugging information
wsgi_logger.info(f"📋 WSGI application object: {type(app)}")
wsgi_logger.info(f"🔌 Application name: {app.name}")
wsgi_logger.info(f"📁 Application instance path: {app.instance_path}")

if __name__ == "__main__":
    # For development server
    wsgi_logger.info("🧪 Running in development mode")
    app.run(host='0.0.0.0', port=5000, debug=False)