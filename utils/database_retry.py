"""
Database Connection Retry Logic for Stevedores Dashboard 3.0
Robust connection handling for maritime operations with unreliable network
"""

import logging
import time
import functools
from typing import Any, Callable, Optional
from sqlalchemy.exc import (
    OperationalError, 
    DisconnectionError, 
    TimeoutError as SQLTimeoutError,
    StatementError,
    DatabaseError
)
from sqlalchemy.pool import QueuePool


logger = logging.getLogger(__name__)


class DatabaseRetryConfig:
    """Configuration for database retry logic"""
    
    # Retry parameters
    MAX_RETRIES = 3
    INITIAL_DELAY = 1.0  # seconds
    MAX_DELAY = 30.0     # seconds
    BACKOFF_MULTIPLIER = 2.0
    
    # Connection timeout parameters
    CONNECTION_TIMEOUT = 30  # seconds
    QUERY_TIMEOUT = 60      # seconds
    
    # Pool configuration
    POOL_SIZE = 10
    MAX_OVERFLOW = 20
    POOL_RECYCLE = 300      # 5 minutes
    POOL_PRE_PING = True
    
    # Retryable exceptions
    RETRYABLE_EXCEPTIONS = (
        OperationalError,
        DisconnectionError,
        SQLTimeoutError,
        ConnectionResetError,
        ConnectionAbortedError,
        OSError,  # Network errors
    )


def with_database_retry(
    max_retries: int = DatabaseRetryConfig.MAX_RETRIES,
    initial_delay: float = DatabaseRetryConfig.INITIAL_DELAY,
    max_delay: float = DatabaseRetryConfig.MAX_DELAY,
    backoff_multiplier: float = DatabaseRetryConfig.BACKOFF_MULTIPLIER,
    retryable_exceptions: tuple = DatabaseRetryConfig.RETRYABLE_EXCEPTIONS
):
    """
    Decorator to add retry logic to database operations
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)  
        backoff_multiplier: Multiplier for exponential backoff
        retryable_exceptions: Tuple of exceptions that should trigger retry
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Database operation failed after {max_retries} retries: {e}")
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(initial_delay * (backoff_multiplier ** attempt), max_delay)
                    
                    logger.warning(
                        f"Database operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    
                    time.sleep(delay)
                    
                except Exception as e:
                    # Non-retryable exceptions
                    logger.error(f"Database operation failed with non-retryable error: {e}")
                    raise
            
            # This should never be reached, but just in case
            raise last_exception or Exception("Unknown database retry error")
        
        return wrapper
    return decorator


class DatabaseConnectionManager:
    """Manages database connections with retry logic and health monitoring"""
    
    def __init__(self, app=None):
        self.app = app
        self.db = None
        self._connection_failures = 0
        self._last_failure_time = None
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the database manager with the Flask app"""
        self.app = app
        
        # Get the database instance - import here to avoid circular imports
        try:
            from app import db
            self.db = db
        except ImportError:
            # Fallback: get from app extensions
            self.db = app.extensions.get('sqlalchemy')
        
        if not self.db:
            logger.warning("SQLAlchemy extension not found")
            return
        
        # Configure engine options for reliability
        self._configure_engine_options()
        
        # Set up health monitoring (only if engine is available)
        if hasattr(self.db, 'engine'):
            self._setup_health_monitoring()
        else:
            logger.warning("Database engine not yet available, skipping health monitoring setup")
    
    def _configure_engine_options(self):
        """Configure SQLAlchemy engine options for robust connections"""
        if not self.app:
            return
        
        db_uri = self.app.config.get('SQLALCHEMY_DATABASE_URI', '')
        
        # Base engine options
        engine_options = {
            'pool_pre_ping': DatabaseRetryConfig.POOL_PRE_PING,
            'pool_recycle': DatabaseRetryConfig.POOL_RECYCLE,
        }
        
        # PostgreSQL-specific options
        if 'postgresql://' in db_uri or 'postgres://' in db_uri:
            engine_options.update({
                'pool_size': DatabaseRetryConfig.POOL_SIZE,
                'max_overflow': DatabaseRetryConfig.MAX_OVERFLOW,
                'poolclass': QueuePool,
                'connect_args': {
                    'connect_timeout': DatabaseRetryConfig.CONNECTION_TIMEOUT,
                    'server_side_cursors': True,
                    'options': '-c statement_timeout=60000',  # 60 second query timeout
                }
            })
        elif 'sqlite' in db_uri:
            # SQLite-specific options (no pooling)
            engine_options.update({
                'connect_args': {
                    'timeout': DatabaseRetryConfig.CONNECTION_TIMEOUT,
                    'check_same_thread': False,  # Allow SQLite usage across threads
                }
            })
        else:
            # Generic database options
            engine_options['connect_args'] = {
                'timeout': DatabaseRetryConfig.CONNECTION_TIMEOUT,
            }
        
        # Update app config only if not already set
        if not self.app.config.get('SQLALCHEMY_ENGINE_OPTIONS'):
            self.app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options
            logger.info(f"Database engine configured with retry-optimized options: {engine_options}")
        else:
            logger.info("Database engine options already configured, skipping")
    
    def _setup_health_monitoring(self):
        """Set up database health monitoring"""
        if not self.db:
            return
        
        # Add event listeners for connection events
        from sqlalchemy import event
        
        @event.listens_for(self.db.engine, 'connect')
        def receive_connect(dbapi_connection, connection_record):
            logger.debug("Database connection established")
            self._connection_failures = 0
            self._last_failure_time = None
        
        @event.listens_for(self.db.engine, 'disconnect')
        def receive_disconnect(dbapi_connection, connection_record):
            logger.warning("Database connection lost")
            self._connection_failures += 1
            self._last_failure_time = time.time()
    
    @with_database_retry()
    def execute_with_retry(self, operation: Callable, *args, **kwargs) -> Any:
        """Execute a database operation with retry logic"""
        return operation(*args, **kwargs)
    
    @with_database_retry()
    def test_connection(self) -> bool:
        """Test database connectivity with retry logic"""
        if not self.db:
            raise Exception("Database not initialized")
        
        try:
            # Simple connectivity test
            with self.db.engine.connect() as conn:
                result = conn.execute("SELECT 1")
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database connectivity test failed: {e}")
            raise
    
    def get_connection_health(self) -> dict:
        """Get database connection health status"""
        health_info = {
            'healthy': True,
            'connection_failures': self._connection_failures,
            'last_failure_time': self._last_failure_time,
            'engine_pool_size': None,
            'active_connections': None,
            'checked_in_connections': None,
        }
        
        try:
            if self.db and hasattr(self.db.engine, 'pool'):
                pool = self.db.engine.pool
                health_info.update({
                    'engine_pool_size': pool.size(),
                    'active_connections': pool.checkedout(),
                    'checked_in_connections': pool.checkedin(),
                })
        except Exception as e:
            logger.warning(f"Could not get pool statistics: {e}")
            health_info['healthy'] = False
        
        return health_info
    
    def force_reconnect(self):
        """Force reconnection to database"""
        if not self.db:
            return False
        
        try:
            # Dispose of current connection pool
            self.db.engine.dispose()
            logger.info("Database connection pool disposed and will be recreated")
            
            # Test new connection
            return self.test_connection()
            
        except Exception as e:
            logger.error(f"Failed to force database reconnect: {e}")
            return False


# Global database manager instance
db_manager = None


def init_database_retry(app):
    """Initialize database retry logic for the Flask app"""
    global db_manager
    db_manager = DatabaseConnectionManager()
    db_manager.init_app(app)
    return db_manager


# Utility functions for common database operations with retry
@with_database_retry()
def safe_db_session_commit(db_session):
    """Safely commit a database session with retry logic"""
    try:
        db_session.commit()
        logger.debug("Database session committed successfully")
    except Exception as e:
        db_session.rollback()
        logger.error(f"Database session commit failed, rolled back: {e}")
        raise


@with_database_retry()
def safe_db_query(query_func, *args, **kwargs):
    """Execute a database query with retry logic"""
    return query_func(*args, **kwargs)


@with_database_retry()
def safe_db_bulk_operation(operation_func, *args, **kwargs):
    """Execute a bulk database operation with retry logic"""
    return operation_func(*args, **kwargs)


# Health check endpoint function
def database_health_check():
    """Perform comprehensive database health check"""
    health_status = {
        'status': 'unknown',
        'timestamp': time.time(),
        'connection_test': False,
        'retry_manager': False,
        'details': {}
    }
    
    try:
        # Check if db_manager is available
        if db_manager is None:
            health_status['status'] = 'unhealthy'
            health_status['error'] = 'Database manager not initialized'
            return health_status
        
        # Test basic connectivity
        health_status['connection_test'] = db_manager.test_connection()
        
        # Get connection health details
        health_status['details'] = db_manager.get_connection_health()
        
        # Test retry manager
        health_status['retry_manager'] = True
        
        # Overall status
        if health_status['connection_test'] and health_status['retry_manager']:
            health_status['status'] = 'healthy'
        else:
            health_status['status'] = 'degraded'
            
    except Exception as e:
        health_status['status'] = 'unhealthy'
        health_status['error'] = str(e)
        logger.error(f"Database health check failed: {e}")
    
    return health_status