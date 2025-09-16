"""
Test Configuration for Production Validation
"""

import os
from datetime import timedelta

class TestConfig:
    """Test configuration for production validation"""
    SECRET_KEY = 'test-secret-key'
    TESTING = True
    DEBUG = False
    
    # Use SQLite for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Disable security for testing
    WTF_CSRF_ENABLED = False
    WTF_CSRF_TIME_LIMIT = None
    SESSION_COOKIE_SECURE = False
    
    # Fast testing settings
    CACHE_TYPE = 'simple'
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=5)

    @staticmethod
    def init_app(app):
        """Initialize test configuration"""
        pass

config = {
    'testing': TestConfig,
    'default': TestConfig
}