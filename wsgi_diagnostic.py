"""
WSGI Entry Point for Stevedores Dashboard 3.0 Production Deployment
ENHANCED WITH COMPREHENSIVE DIAGNOSTIC ARCHITECTURE for crash analysis
"""

import os
import sys
import logging
import time
from pathlib import Path

# Add the project directory to Python path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

# Set environment variables for production
os.environ.setdefault('FLASK_ENV', 'production')
os.environ.setdefault('PYTHONPATH', str(project_dir))

# Enhanced logging setup for production diagnostics
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s:%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
wsgi_logger = logging.getLogger('stevedores.wsgi')

wsgi_logger.info("🚢 WSGI: Stevedores Dashboard 3.0 starting...")
wsgi_logger.info(f"🔧 WSGI: Worker PID: {os.getpid()}")
wsgi_logger.info(f"📊 WSGI: Python version: {sys.version}")

try:
    # Import diagnostic system first
    wsgi_logger.info("🔍 WSGI: Importing diagnostic architecture...")
    from diagnostic_architecture import run_startup_diagnostics, initialize_diagnostics
    
    # Initialize diagnostics before any other imports
    diagnostic = initialize_diagnostics()
    wsgi_logger.info("✅ WSGI: Diagnostic system initialized")
    
    # Import app components
    wsgi_logger.info("📦 WSGI: Importing app, db, and init_database...")
    from app import app, init_database, db
    wsgi_logger.info("✅ WSGI: App components imported successfully")
    
    # INTELLIGENT CONFIG DETECTION: Try render_config first, then production_config
    config_loaded = False
    config_name = os.environ.get('FLASK_CONFIG', 'render')
    
    wsgi_logger.info(f"🔧 WSGI: Loading configuration: {config_name}")
    
    # Try render_config first (for Render deployments)
    if not config_loaded:
        try:
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
                wsgi_logger.info(f"✅ WSGI: Loaded render_config: render (fallback)")
        except ImportError:
            wsgi_logger.info("⚠️  WSGI: render_config not available, trying production_config")
    
    # Fallback to production_config if render_config not available
    if not config_loaded:
        try:
            from production_config import config
            fallback_name = 'production' if config_name in ['render', 'production'] else config_name
            if fallback_name in config:
                app.config.from_object(config[fallback_name])
                config[fallback_name].init_app(app)
                config_loaded = True
                wsgi_logger.info(f"✅ WSGI: Loaded production_config: {fallback_name}")
        except ImportError:
            wsgi_logger.error("❌ WSGI: Neither render_config nor production_config available")
            
    if not config_loaded:
        raise ImportError("No valid configuration module found")
    
    # RUN COMPREHENSIVE STARTUP DIAGNOSTICS
    wsgi_logger.info("🔍 WSGI: Running comprehensive startup diagnostics...")
    
    with app.app_context():
        # Run diagnostic suite before database initialization
        diagnostic_success = run_startup_diagnostics(app, db)
        
        if not diagnostic_success:
            wsgi_logger.critical("❌ WSGI: Startup diagnostics FAILED - terminating worker to prevent crash")
            wsgi_logger.critical("📋 WSGI: Check diagnostic logs for detailed failure analysis")
            sys.exit(1)
        
        wsgi_logger.info("✅ WSGI: Startup diagnostics PASSED")
        
        # Initialize database with diagnostic monitoring
        wsgi_logger.info("🗄️  WSGI: Initializing database...")
        database_init_start = time.time()
        
        if not init_database():
            wsgi_logger.critical("❌ WSGI: Database initialization failed - check logs")
            wsgi_logger.critical("⏱️  WSGI: Database init took {:.2f}s before failure".format(time.time() - database_init_start))
            sys.exit(1)
        
        database_init_duration = time.time() - database_init_start
        wsgi_logger.info(f"✅ WSGI: Database initialized successfully in {database_init_duration:.2f}s")
    
    # Production logging
    if not app.debug:
        gunicorn_logger = logging.getLogger('gunicorn.error')
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level)
    
    app.logger.info('🚢 Stevedores Dashboard 3.0 production server starting...')
    app.logger.info(f'📊 Configuration: {config_name}')
    app.logger.info(f'🔧 PWA Cache Version: {app.config.get("PWA_CACHE_VERSION", "unknown")}')
    app.logger.info('⚓ Maritime operations system ready for deployment')
    
except Exception as e:
    wsgi_logger.critical(f"❌ WSGI startup failed: {e}")
    import traceback
    wsgi_logger.critical(f"🔍 WSGI traceback: {traceback.format_exc()}")
    sys.exit(1)

# WSGI application
application = app

if __name__ == "__main__":
    # For development server
    app.run(host='0.0.0.0', port=5000, debug=False)