"""
WSGI Entry Point for Stevedores Dashboard 3.0 Production Deployment
Optimized for maritime operations with comprehensive error handling
"""

import os
import sys
from pathlib import Path

# Add the project directory to Python path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

# Set environment variables for production
os.environ.setdefault('FLASK_ENV', 'production')
os.environ.setdefault('PYTHONPATH', str(project_dir))

try:
    from app import app, init_database
    
    # INTELLIGENT CONFIG DETECTION: Try render_config first, then production_config
    config_loaded = False
    config_name = os.environ.get('FLASK_CONFIG', 'render')
    
    # Try render_config first (for Render deployments)
    if not config_loaded:
        try:
            from render_config import config
            if config_name in config:
                app.config.from_object(config[config_name])
                config[config_name].init_app(app)
                config_loaded = True
                print(f"✅ WSGI: Loaded render_config: {config_name}")
            else:
                # Fallback to 'render' if specific config not found
                app.config.from_object(config['render'])
                config['render'].init_app(app) 
                config_loaded = True
                print(f"✅ WSGI: Loaded render_config: render (fallback)")
        except ImportError:
            print("⚠️  WSGI: render_config not available, trying production_config")
    
    # Fallback to production_config if render_config not available
    if not config_loaded:
        try:
            from production_config import config
            fallback_name = 'production' if config_name in ['render', 'production'] else config_name
            if fallback_name in config:
                app.config.from_object(config[fallback_name])
                config[fallback_name].init_app(app)
                config_loaded = True
                print(f"✅ WSGI: Loaded production_config: {fallback_name}")
        except ImportError:
            print("❌ WSGI: Neither render_config nor production_config available")
            
    if not config_loaded:
        raise ImportError("No valid configuration module found")
    
    # Initialize database in production
    with app.app_context():
        if not init_database():
            print("⚠️  Database initialization failed - check logs")
            sys.exit(1)
    
    # Production logging
    if not app.debug:
        import logging
        gunicorn_logger = logging.getLogger('gunicorn.error')
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level)
    
    app.logger.info('🚢 Stevedores Dashboard 3.0 production server starting...')
    app.logger.info(f'📊 Configuration: {config_name}')
    app.logger.info(f'🔧 PWA Cache Version: {app.config.get("PWA_CACHE_VERSION", "unknown")}')
    app.logger.info('⚓ Maritime operations system ready for deployment')
    
except Exception as e:
    print(f"❌ WSGI startup failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# WSGI application
application = app

if __name__ == "__main__":
    # For development server
    app.run(host='0.0.0.0', port=5000, debug=False)