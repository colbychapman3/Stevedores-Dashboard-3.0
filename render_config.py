"""
Render + Supabase + Upstash Configuration
Optimized for maritime operations deployment
"""

import os
from datetime import timedelta

class RenderConfig:
    """Production configuration for Render deployment"""
    
    # Basic Flask settings
    # SECURITY FIX: Require SECRET_KEY - no hardcoded fallback for production
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable is required for production deployment")
    DEBUG = False
    TESTING = False
    
    # Supabase PostgreSQL connection
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 3600,
        'pool_size': 10,
        'max_overflow': 20,
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upstash Redis connection
    REDIS_URL = os.environ.get('REDIS_URL')
    
    # Security settings
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    
    # Performance settings
    SEND_FILE_MAX_AGE_DEFAULT = timedelta(days=365)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # PWA settings
    PWA_CACHE_VERSION = '3.0.1'
    PWA_OFFLINE_TIMEOUT = 30
    
    # Maritime-specific settings
    MAX_VESSELS_PER_USER = 50
    CARGO_TALLY_BATCH_SIZE = 100
    SYNC_RETRY_ATTEMPTS = 3
    DOCUMENT_PROCESSING_TIMEOUT = 30
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL')
    RATELIMIT_DEFAULT = "100 per hour"
    
    # File uploads
    UPLOAD_FOLDER = '/tmp/stevedores_uploads'
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'csv', 'xlsx', 'xls'}
    
    @staticmethod
    def init_app(app):
        """Initialize app for Render deployment"""
        import logging
        
        # Configure logging for Render
        gunicorn_logger = logging.getLogger('gunicorn.error')
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level)
        
        app.logger.info('🚢 Stevedores Dashboard 3.0 starting on Render')
        app.logger.info(f'⚓ PWA Cache Version: {app.config.get("PWA_CACHE_VERSION")}')

# Testing configuration
class TestingConfig:
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    SECRET_KEY = 'test-secret-key'
    
    # In-memory database for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # SQLite-specific engine options (no pool settings)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }
    
    # Disable security for testing
    WTF_CSRF_ENABLED = False
    WTF_CSRF_TIME_LIMIT = None
    
    # Fast testing settings
    CACHE_TYPE = 'simple'
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=5)
    
    @staticmethod
    def init_app(app):
        """Initialize app for testing"""
        pass

# Configuration mapping
config = {
    'render': RenderConfig,
    'production': RenderConfig,
    'testing': TestingConfig,
    'default': RenderConfig
}