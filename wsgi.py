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
    from production_config import config
    
    # Configure for production
    config_name = os.environ.get('FLASK_CONFIG', 'production')
    app.config.from_object(config[config_name])
    
    # Initialize production configuration
    config[config_name].init_app(app)
    
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