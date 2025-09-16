"""
Production Configuration for Stevedores Dashboard 3.0
Optimized for maritime operations with enhanced security and performance
"""

import os
from datetime import timedelta

class ProductionConfig:
    """Production configuration with security and performance optimizations"""
    
    # Basic Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'production-secret-key-change-this'
    DEBUG = False
    TESTING = False
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///stevedores_production.db'
    
    # Engine options - will be set by init_app based on database type
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Security Configuration
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)  # 8-hour work shift
    
    # Performance Configuration
    SEND_FILE_MAX_AGE_DEFAULT = timedelta(days=365)  # Static assets cache
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file upload
    
    # Logging Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    
    # PWA Configuration
    PWA_CACHE_VERSION = '3.0.1'
    PWA_OFFLINE_TIMEOUT = 30  # seconds
    
    # Maritime-specific Configuration
    MAX_VESSELS_PER_USER = 50
    CARGO_TALLY_BATCH_SIZE = 100
    SYNC_RETRY_ATTEMPTS = 3
    DOCUMENT_PROCESSING_TIMEOUT = 30
    
    # Redis Configuration (for production caching)
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_TYPE = 'redis' if os.environ.get('REDIS_URL') else 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Celery Configuration (for background tasks)
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    
    # Email Configuration (for notifications)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    # Push Notification Configuration
    VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY')
    VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY')
    VAPID_CLAIMS = {
        "sub": "mailto:admin@stevedores-dashboard.com"
    }
    
    # Rate Limiting
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'memory://')
    RATELIMIT_DEFAULT = "100 per hour"
    
    # File Upload Configuration
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/tmp/stevedores_uploads')
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'csv', 'xlsx', 'xls'}
    
    # Monitoring Configuration
    SENTRY_DSN = os.environ.get('SENTRY_DSN')
    PROMETHEUS_METRICS = os.environ.get('PROMETHEUS_METRICS', 'false').lower() == 'true'
    
    # Memory Monitoring Configuration
    MEMORY_MONITORING_ENABLED = os.environ.get('MEMORY_MONITORING_ENABLED', 'true').lower() == 'true'
    MEMORY_WARNING_THRESHOLD = float(os.environ.get('MEMORY_WARNING_THRESHOLD', 75.0))
    MEMORY_CRITICAL_THRESHOLD = float(os.environ.get('MEMORY_CRITICAL_THRESHOLD', 85.0))
    MEMORY_EMERGENCY_THRESHOLD = float(os.environ.get('MEMORY_EMERGENCY_THRESHOLD', 95.0))
    MEMORY_CHECK_INTERVAL = int(os.environ.get('MEMORY_CHECK_INTERVAL', 15))
    MEMORY_CONTAINER_LIMIT_MB = int(os.environ.get('MEMORY_LIMIT_MB', 512))
    MEMORY_SAFETY_BUFFER_MB = int(os.environ.get('MEMORY_SAFETY_BUFFER_MB', 64))
    
    # Memory optimization settings
    MEMORY_AGGRESSIVE_GC = os.environ.get('MEMORY_AGGRESSIVE_GC', 'true').lower() == 'true'
    MEMORY_WORKER_RESTART_THRESHOLD = float(os.environ.get('MEMORY_WORKER_RESTART_THRESHOLD', 90.0))
    MEMORY_MAX_REQUESTS_PER_WORKER = int(os.environ.get('MEMORY_MAX_REQUESTS_PER_WORKER', 800))
    
    # Memory alerts and logging
    MEMORY_ALERT_COOLDOWN = int(os.environ.get('MEMORY_ALERT_COOLDOWN', 60))
    MEMORY_DETAILED_LOGGING = os.environ.get('MEMORY_DETAILED_LOGGING', 'true').lower() == 'true'
    
    @staticmethod
    def init_app(app):
        """Initialize application with production settings"""
        
        # Configure database engine options based on database type
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if db_uri and ('postgresql://' in db_uri or 'postgres://' in db_uri):
            # PostgreSQL connection pooling
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
                'pool_recycle': 300,
                'pool_pre_ping': True,
                'pool_size': 10,
                'max_overflow': 20,
            }
        else:
            # SQLite - no pooling options
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
                'pool_pre_ping': True,
            }
        
        # Configure logging
        import logging
        from logging.handlers import RotatingFileHandler
        
        if not app.debug:
            if not os.path.exists('logs'):
                os.mkdir('logs')
            
            file_handler = RotatingFileHandler(
                'logs/stevedores_dashboard.log',
                maxBytes=10240000,  # 10MB
                backupCount=10
            )
            file_handler.setFormatter(logging.Formatter(
                ProductionConfig.LOG_FORMAT
            ))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
            
            app.logger.setLevel(logging.INFO)
            app.logger.info('Stevedores Dashboard 3.0 production startup')


class StagingConfig(ProductionConfig):
    """Staging configuration - production-like but with debugging enabled"""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False  # For local testing
    
    # Less strict rate limiting for staging
    RATELIMIT_DEFAULT = "1000 per hour"


class DevelopmentConfig:
    """Development configuration with debug features"""
    DEBUG = True
    TESTING = False
    SECRET_KEY = 'dev-secret-key'
    
    # SQLite for development
    SQLALCHEMY_DATABASE_URI = 'sqlite:///stevedores_dev.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    
    # Disable security features for development
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    
    # Development-friendly settings
    SEND_FILE_MAX_AGE_DEFAULT = timedelta(seconds=1)
    PWA_CACHE_VERSION = 'dev'
    
    @staticmethod
    def init_app(app):
        """Initialize application for development"""
        app.logger.info('Stevedores Dashboard 3.0 development mode')


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


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'staging': StagingConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}