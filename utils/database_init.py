"""
Robust Database Initialization for Stevedores Dashboard 3.0
Production-ready database setup with comprehensive error handling

Replaces the duplicate init_database functions in app.py with a single,
robust implementation that provides actionable error messages for
production debugging and prevents worker crashes.
"""

import logging
import sys
from typing import Dict, Any, Tuple
from werkzeug.security import generate_password_hash

# Import our comprehensive diagnostics
from .database_diagnostics import run_database_diagnostics, DatabaseDiagnosticError


logger = logging.getLogger(__name__)


class DatabaseInitializationError(Exception):
    """Custom exception for database initialization failures"""
    def __init__(self, message: str, diagnostic_results: Dict = None, suggestions: list = None):
        self.message = message
        self.diagnostic_results = diagnostic_results or {}
        self.suggestions = suggestions or []
        super().__init__(message)


def init_database_with_diagnostics(app, db=None) -> Tuple[bool, Dict[str, Any]]:
    """
    Initialize database with comprehensive diagnostics and error reporting.
    
    This function replaces the duplicate init_database functions with a single,
    robust implementation that:
    1. Runs comprehensive pre-connection diagnostics
    2. Provides detailed error messages for production debugging
    3. Prevents worker crashes with graceful error handling
    4. Creates demo users for testing
    
    Args:
        app: Flask application instance
        db: SQLAlchemy database instance (optional, will import if not provided)
    
    Returns:
        Tuple[bool, Dict]: (success, diagnostic_results)
    """
    logger.info("🚀 Starting robust database initialization with diagnostics...")
    
    try:
        # Get database URL from app config
        database_url = app.config.get('SQLALCHEMY_DATABASE_URI')
        if not database_url:
            raise DatabaseInitializationError(
                "No database URL configured",
                suggestions=[
                    "Set SQLALCHEMY_DATABASE_URI in app config",
                    "Check DATABASE_URL environment variable",
                    "Verify configuration loading in app.py"
                ]
            )
        
        logger.info(f"📊 Running comprehensive database diagnostics for: {database_url.split('@')[0]}@...")
        
        # Run comprehensive diagnostics
        with app.app_context():
            diagnostic_data = run_database_diagnostics(database_url, app.app_context())
            diagnostic_results = diagnostic_data['diagnostics']
            diagnostic_summary = diagnostic_data['summary']
        
        # Check if diagnostics passed
        if diagnostic_summary['overall_status'] != 'healthy':
            error_msg = f"Database diagnostics failed ({diagnostic_summary['success_rate']}% passed)"
            
            if diagnostic_summary['critical_issues']:
                error_msg += f": {diagnostic_summary['critical_issues'][0]['message']}"
            
            raise DatabaseInitializationError(
                error_msg,
                diagnostic_results=diagnostic_data,
                suggestions=diagnostic_summary.get('recommendations', [])
            )
        
        logger.info(f"✅ Database diagnostics passed ({diagnostic_summary['checks_passed']}/{diagnostic_summary['total_checks']})")
        
        # Import database models if not provided
        if db is None:
            try:
                from app import db
            except ImportError:
                raise DatabaseInitializationError(
                    "Could not import database instance",
                    suggestions=[
                        "Ensure app.py is properly configured",
                        "Check SQLAlchemy initialization in app",
                        "Verify circular import issues are resolved"
                    ]
                )
        
        # Initialize database tables
        logger.info("🛠️  Creating database tables...")
        
        with app.app_context():
            # Create all tables
            db.create_all()
            logger.info("✅ Database tables created successfully")
            
            # Import models for demo data creation
            try:
                from app import User
            except ImportError:
                logger.warning("⚠️  Could not import User model - skipping demo user creation")
                return True, diagnostic_data
            
            # Create demo user if it doesn't exist
            demo_user = User.query.filter_by(email='demo@maritime.test').first()
            
            if not demo_user:
                logger.info("👤 Creating demo user...")
                demo_user = User(
                    email='demo@maritime.test',
                    username='demo_user',
                    password_hash=generate_password_hash('demo123'),
                    is_active=True
                )
                db.session.add(demo_user)
                db.session.commit()
                logger.info("✅ Demo user created: demo@maritime.test / demo123")
            else:
                logger.info("ℹ️  Demo user already exists")
            
            # Verify demo user was created/exists
            final_user_check = User.query.filter_by(email='demo@maritime.test').first()
            if not final_user_check:
                logger.error("❌ Demo user verification failed")
                raise DatabaseInitializationError(
                    "Demo user was not found after creation",
                    suggestions=[
                        "Check database write permissions",
                        "Verify transaction commit succeeded",
                        "Check User model is properly configured"
                    ]
                )
        
        logger.info("✨ Database initialization completed successfully")
        return True, diagnostic_data
        
    except DatabaseInitializationError:
        # Re-raise our custom errors
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected database initialization error: {e}")
        raise DatabaseInitializationError(
            f"Unexpected database initialization error: {str(e)}",
            suggestions=[
                "Check application logs for detailed error information",
                "Verify database server is accessible and running",
                "Check application configuration and environment variables"
            ]
        )


def safe_init_database(app, db=None) -> bool:
    """
    Safe wrapper for database initialization that prevents worker crashes.
    
    This function catches all exceptions and provides detailed logging
    without crashing the worker process. Suitable for production use.
    
    Args:
        app: Flask application instance
        db: SQLAlchemy database instance (optional)
    
    Returns:
        bool: True if initialization successful, False otherwise
    """
    try:
        success, diagnostic_data = init_database_with_diagnostics(app, db)
        
        if success:
            logger.info("✅ Safe database initialization completed successfully")
            return True
        else:
            logger.error("❌ Safe database initialization failed but did not crash")
            return False
            
    except DatabaseInitializationError as e:
        logger.error(f"❌ Database initialization failed: {e.message}")
        
        # Log diagnostic results if available
        if e.diagnostic_results:
            summary = e.diagnostic_results.get('summary', {})
            logger.error(f"Diagnostic summary: {summary.get('success_rate', 0)}% passed")
            
            if summary.get('critical_issues'):
                for issue in summary['critical_issues']:
                    logger.error(f"Critical issue: {issue['message']}")
        
        # Log suggestions
        if e.suggestions:
            logger.error("Suggested solutions:")
            for suggestion in e.suggestions:
                logger.error(f"  - {suggestion}")
        
        return False
        
    except Exception as e:
        logger.error(f"❌ Unexpected error in safe database initialization: {e}")
        logger.error("This error has been caught to prevent worker crash")
        return False


def get_database_status(app, db=None) -> Dict[str, Any]:
    """
    Get current database status without attempting initialization.
    
    Args:
        app: Flask application instance  
        db: SQLAlchemy database instance (optional)
    
    Returns:
        Dict: Database status information
    """
    try:
        database_url = app.config.get('SQLALCHEMY_DATABASE_URI')
        if not database_url:
            return {
                'status': 'not_configured',
                'message': 'No database URL configured',
                'healthy': False
            }
        
        # Run diagnostics without initialization
        with app.app_context():
            diagnostic_data = run_database_diagnostics(database_url)
            diagnostic_summary = diagnostic_data['summary']
        
        return {
            'status': diagnostic_summary['overall_status'],
            'message': f"Database diagnostics: {diagnostic_summary['success_rate']}% passed",
            'healthy': diagnostic_summary['overall_status'] == 'healthy',
            'details': diagnostic_summary,
            'timestamp': diagnostic_data['timestamp']
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Database status check failed: {str(e)}',
            'healthy': False,
            'error': str(e)
        }


# Convenience function for backward compatibility
def init_database(app, db=None) -> bool:
    """
    Backward compatible database initialization function.
    
    This function maintains compatibility with existing code while
    providing the enhanced diagnostics and error handling.
    
    Args:
        app: Flask application instance
        db: SQLAlchemy database instance (optional)
    
    Returns:
        bool: True if initialization successful, False otherwise
    """
    return safe_init_database(app, db)
