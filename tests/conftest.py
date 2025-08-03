"""
Test configuration and shared fixtures for error scenario testing
"""

import pytest
import tempfile
import shutil
import os
from pathlib import Path


@pytest.fixture(scope="session")
def test_data_dir():
    """Create temporary directory for test data"""
    temp_dir = tempfile.mkdtemp(prefix="stevedores_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="session") 
def test_config():
    """Test configuration settings"""
    return {
        'database_url': 'sqlite:///:memory:',
        'redis_url': 'redis://localhost:6379/15',  # Test database
        'max_workers': 3,
        'timeout': 10,
        'retry_attempts': 2
    }


@pytest.fixture(autouse=True)
def setup_test_environment(test_config):
    """Setup test environment before each test"""
    # Set test environment variables
    os.environ['STEVEDORES_ENV'] = 'test'
    os.environ['DATABASE_URL'] = test_config['database_url']
    os.environ['REDIS_URL'] = test_config['redis_url']
    
    yield
    
    # Cleanup after test
    test_env_vars = ['STEVEDORES_ENV', 'DATABASE_URL', 'REDIS_URL']
    for var in test_env_vars:
        os.environ.pop(var, None)


@pytest.fixture
def error_scenario_config():
    """Configuration specific to error scenario testing"""
    return {
        'network_timeout': 5,
        'db_timeout': 3,
        'memory_threshold': 80,
        'max_concurrent_users': 50,
        'worker_restart_delay': 1,
        'max_restart_attempts': 3
    }