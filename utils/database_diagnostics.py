"""
Comprehensive Database Diagnostics for Stevedores Dashboard 3.0
Production-ready database connection validation and error reporting

Provides detailed diagnostics for:
- Pre-connection validation (URL format, credentials, network)
- Connection timeout and retry logic with exponential backoff
- Database existence verification
- Schema compatibility checks
- Table creation verification
- Demo data insertion validation
- Connection pool health monitoring

Designed to prevent worker crashes and provide actionable error messages
for production debugging in maritime operations environments.
"""

import os
import re
import time
import socket
import logging
import sqlalchemy
from typing import Dict, List, Tuple, Optional, Any
from urllib.parse import urlparse
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import OperationalError, DatabaseError, TimeoutError
from werkzeug.security import generate_password_hash

# Optional psycopg2 import - may not be available in all environments
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


logger = logging.getLogger(__name__)


class DatabaseDiagnosticError(Exception):
    """Custom exception for database diagnostic failures"""
    def __init__(self, error_type: str, message: str, details: Dict = None):
        self.error_type = error_type
        self.message = message
        self.details = details or {}
        super().__init__(f"{error_type}: {message}")


class DatabaseDiagnostics:
    """Comprehensive database diagnostics and validation system"""
    
    def __init__(self, database_url: str, app_context=None):
        self.database_url = database_url
        self.app_context = app_context
        self.parsed_url = None
        self.engine = None
        self.diagnostic_results = {
            'url_validation': {'passed': False, 'details': {}},
            'network_connectivity': {'passed': False, 'details': {}},
            'database_connection': {'passed': False, 'details': {}},
            'authentication': {'passed': False, 'details': {}},
            'database_existence': {'passed': False, 'details': {}},
            'schema_compatibility': {'passed': False, 'details': {}},
            'table_operations': {'passed': False, 'details': {}},
            'demo_data_creation': {'passed': False, 'details': {}},
            'connection_pool_health': {'passed': False, 'details': {}}
        }
    
    def run_comprehensive_diagnostics(self) -> Dict[str, Any]:
        """Run all database diagnostics and return detailed results"""
        logger.info("🔍 Starting comprehensive database diagnostics...")
        
        try:
            # Step 1: Validate database URL format
            self._validate_database_url()
            
            # Step 2: Test network connectivity
            self._test_network_connectivity()
            
            # Step 3: Test database connection with retries
            self._test_database_connection_with_retries()
            
            # Step 4: Validate authentication
            self._validate_authentication()
            
            # Step 5: Verify database exists or can be created
            self._verify_database_existence()
            
            # Step 6: Check schema compatibility
            self._check_schema_compatibility()
            
            # Step 7: Test table operations
            self._test_table_operations()
            
            # Step 8: Test demo data creation
            self._test_demo_data_creation()
            
            # Step 9: Monitor connection pool health
            self._monitor_connection_pool_health()
            
            logger.info("✅ Database diagnostics completed successfully")
            
        except DatabaseDiagnosticError as e:
            logger.error(f"❌ Database diagnostic failed: {e}")
            self.diagnostic_results['error'] = {
                'type': e.error_type,
                'message': e.message,
                'details': e.details
            }
        except Exception as e:
            logger.error(f"❌ Unexpected diagnostic error: {e}")
            self.diagnostic_results['error'] = {
                'type': 'UNEXPECTED_ERROR',
                'message': str(e),
                'details': {'exception_type': type(e).__name__}
            }
        
        return self.diagnostic_results
    
    def _validate_database_url(self):
        """Validate database URL format and extract components"""
        logger.info("🔗 Validating database URL format...")
        
        if not self.database_url:
            raise DatabaseDiagnosticError(
                'URL_VALIDATION_FAILED',
                'Database URL is empty or None',
                {'provided_url': self.database_url}
            )
        
        try:
            self.parsed_url = urlparse(self.database_url)
            
            # Validate required components
            if not self.parsed_url.scheme:
                raise DatabaseDiagnosticError(
                    'URL_VALIDATION_FAILED',
                    'Database URL missing scheme (postgresql://, sqlite://, etc.)',
                    {'url': self.database_url}
                )
            
            # Validate PostgreSQL URLs
            if self.parsed_url.scheme in ['postgresql', 'postgres']:
                if not self.parsed_url.hostname:
                    raise DatabaseDiagnosticError(
                        'URL_VALIDATION_FAILED',
                        'PostgreSQL URL missing hostname',
                        {'url': self.database_url}
                    )
                if not self.parsed_url.username:
                    raise DatabaseDiagnosticError(
                        'URL_VALIDATION_FAILED',
                        'PostgreSQL URL missing username',
                        {'url': self.database_url}
                    )
                if not self.parsed_url.password:
                    logger.warning("PostgreSQL URL missing password - this may cause authentication failures")
            
            # Log URL details (without sensitive info)
            url_details = {
                'scheme': self.parsed_url.scheme,
                'hostname': self.parsed_url.hostname,
                'port': self.parsed_url.port,
                'database': self.parsed_url.path.lstrip('/') if self.parsed_url.path else None,
                'username': self.parsed_url.username,
                'has_password': bool(self.parsed_url.password)
            }
            
            self.diagnostic_results['url_validation'] = {
                'passed': True,
                'details': url_details
            }
            
            logger.info(f"✅ Database URL validated: {url_details['scheme']}://{url_details['hostname']}:{url_details['port']}/{url_details['database']}")
            
        except Exception as e:
            raise DatabaseDiagnosticError(
                'URL_VALIDATION_FAILED',
                f'Invalid database URL format: {str(e)}',
                {'url': self.database_url, 'parse_error': str(e)}
            )
    
    def _test_network_connectivity(self):
        """Test network connectivity to database host"""
        if self.parsed_url.scheme == 'sqlite':
            logger.info("📁 SQLite database - skipping network connectivity test")
            self.diagnostic_results['network_connectivity'] = {
                'passed': True,
                'details': {'type': 'sqlite', 'message': 'Network connectivity not required for SQLite'}
            }
            return
        
        logger.info(f"🌐 Testing network connectivity to {self.parsed_url.hostname}:{self.parsed_url.port or 5432}...")
        
        host = self.parsed_url.hostname
        port = self.parsed_url.port or 5432
        timeout = 10
        
        try:
            start_time = time.time()
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            connection_time = time.time() - start_time
            
            self.diagnostic_results['network_connectivity'] = {
                'passed': True,
                'details': {
                    'host': host,
                    'port': port,
                    'connection_time_ms': round(connection_time * 1000, 2),
                    'timeout': timeout
                }
            }
            
            logger.info(f"✅ Network connectivity successful ({connection_time*1000:.2f}ms)")
            
        except socket.timeout:
            raise DatabaseDiagnosticError(
                'NETWORK_CONNECTIVITY_FAILED',
                f'Connection timeout after {timeout} seconds',
                {'host': host, 'port': port, 'timeout': timeout}
            )
        except socket.gaierror as e:
            raise DatabaseDiagnosticError(
                'NETWORK_CONNECTIVITY_FAILED',
                f'DNS resolution failed: {str(e)}',
                {'host': host, 'port': port, 'dns_error': str(e)}
            )
        except ConnectionRefusedError:
            raise DatabaseDiagnosticError(
                'NETWORK_CONNECTIVITY_FAILED',
                f'Connection refused by {host}:{port}',
                {'host': host, 'port': port, 'error': 'Connection refused'}
            )
        except Exception as e:
            raise DatabaseDiagnosticError(
                'NETWORK_CONNECTIVITY_FAILED',
                f'Network connectivity test failed: {str(e)}',
                {'host': host, 'port': port, 'error': str(e)}
            )
    
    def _test_database_connection_with_retries(self):
        """Test database connection with exponential backoff retries"""
        logger.info("🔌 Testing database connection with retry logic...")
        
        max_retries = 3
        initial_delay = 1.0
        max_delay = 10.0
        backoff_multiplier = 2.0
        
        connection_details = {
            'attempts': 0,
            'total_time': 0,
            'errors': []
        }
        
        start_total_time = time.time()
        
        for attempt in range(max_retries + 1):
            connection_details['attempts'] = attempt + 1
            
            try:
                logger.info(f"🔌 Connection attempt {attempt + 1}/{max_retries + 1}...")
                start_time = time.time()
                
                # Create engine with production-ready settings
                engine_options = {
                    'pool_pre_ping': True,
                    'connect_args': {'connect_timeout': 30}
                }
                
                if self.parsed_url.scheme in ['postgresql', 'postgres']:
                    engine_options.update({
                        'pool_size': 5,
                        'max_overflow': 10,
                        'pool_recycle': 300
                    })
                
                self.engine = create_engine(self.database_url, **engine_options)
                
                # Test connection
                with self.engine.connect() as conn:
                    result = conn.execute(text("SELECT 1"))
                    test_value = result.scalar()
                    
                    if test_value != 1:
                        raise DatabaseDiagnosticError(
                            'CONNECTION_TEST_FAILED',
                            'Database connection test query returned unexpected result',
                            {'expected': 1, 'actual': test_value}
                        )
                
                connection_time = time.time() - start_time
                total_time = time.time() - start_total_time
                
                self.diagnostic_results['database_connection'] = {
                    'passed': True,
                    'details': {
                        'attempts': connection_details['attempts'],
                        'connection_time_ms': round(connection_time * 1000, 2),
                        'total_time_ms': round(total_time * 1000, 2),
                        'engine_options': engine_options
                    }
                }
                
                logger.info(f"✅ Database connection successful on attempt {attempt + 1} ({connection_time*1000:.2f}ms)")
                return
                
            except Exception as e:
                connection_time = time.time() - start_time
                error_details = {
                    'attempt': attempt + 1,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'connection_time_ms': round(connection_time * 1000, 2)
                }
                connection_details['errors'].append(error_details)
                
                logger.warning(f"⚠️  Connection attempt {attempt + 1} failed: {str(e)}")
                
                if attempt == max_retries:
                    # Final attempt failed
                    connection_details['total_time'] = time.time() - start_total_time
                    
                    # Classify error type for better debugging
                    error_classification = self._classify_connection_error(e)
                    
                    raise DatabaseDiagnosticError(
                        error_classification['type'],
                        error_classification['message'],
                        {
                            'connection_attempts': connection_details,
                            'classification': error_classification,
                            'original_error': str(e)
                        }
                    )
                else:
                    # Wait before retry with exponential backoff
                    delay = min(initial_delay * (backoff_multiplier ** attempt), max_delay)
                    logger.info(f"⏳ Retrying in {delay:.1f} seconds...")
                    time.sleep(delay)
    
    def _classify_connection_error(self, error: Exception) -> Dict[str, str]:
        """Classify connection errors for better debugging guidance"""
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        if 'authentication failed' in error_str or 'password authentication failed' in error_str:
            return {
                'type': 'AUTHENTICATION_FAILED',
                'message': 'Database authentication failed - check username and password',
                'guidance': 'Verify DATABASE_URL credentials are correct'
            }
        elif 'database' in error_str and 'does not exist' in error_str:
            return {
                'type': 'DATABASE_NOT_FOUND',
                'message': 'Target database does not exist',
                'guidance': 'Create the database or check DATABASE_URL database name'
            }
        elif 'connection refused' in error_str:
            return {
                'type': 'CONNECTION_REFUSED',
                'message': 'Database server refused connection',
                'guidance': 'Check if database server is running and accessible'
            }
        elif 'timeout' in error_str or isinstance(error, TimeoutError):
            return {
                'type': 'CONNECTION_TIMEOUT',
                'message': 'Database connection timed out',
                'guidance': 'Check network connectivity and database server load'
            }
        elif 'permission denied' in error_str:
            return {
                'type': 'PERMISSION_DENIED',
                'message': 'Database access permission denied',
                'guidance': 'Check user permissions and database access rights'
            }
        else:
            return {
                'type': 'CONNECTION_FAILED',
                'message': f'Database connection failed: {error_type}',
                'guidance': 'Check database server status and connection parameters'
            }
    
    def _validate_authentication(self):
        """Validate database authentication and permissions"""
        if self.parsed_url.scheme == 'sqlite':
            logger.info("📁 SQLite database - skipping authentication validation")
            self.diagnostic_results['authentication'] = {
                'passed': True,
                'details': {'type': 'sqlite', 'message': 'Authentication not required for SQLite'}
            }
            return
        
        logger.info("🔐 Validating database authentication and permissions...")
        
        try:
            with self.engine.connect() as conn:
                # Test basic permissions
                result = conn.execute(text("SELECT current_user, current_database()"))
                user_info = result.fetchone()
                
                # Test table creation permission (if we can create a temporary table)
                test_table_name = f"_diagnostic_test_{int(time.time())}"
                try:
                    conn.execute(text(f"CREATE TEMPORARY TABLE {test_table_name} (id INTEGER)"))
                    conn.execute(text(f"DROP TABLE {test_table_name}"))
                    can_create_tables = True
                except Exception:
                    can_create_tables = False
                
                self.diagnostic_results['authentication'] = {
                    'passed': True,
                    'details': {
                        'current_user': str(user_info[0]) if user_info else 'unknown',
                        'current_database': str(user_info[1]) if user_info and len(user_info) > 1 else 'unknown',
                        'can_create_tables': can_create_tables,
                        'username_from_url': self.parsed_url.username
                    }
                }
                
                logger.info(f"✅ Authentication successful as user: {user_info[0] if user_info else 'unknown'}")
                
                if not can_create_tables:
                    logger.warning("⚠️  User may not have table creation permissions")
                
        except Exception as e:
            raise DatabaseDiagnosticError(
                'AUTHENTICATION_FAILED',
                f'Database authentication validation failed: {str(e)}',
                {'error': str(e), 'username': self.parsed_url.username}
            )
    
    def _verify_database_existence(self):
        """Verify target database exists or can be accessed"""
        logger.info("🗄️  Verifying database existence and accessibility...")
        
        try:
            with self.engine.connect() as conn:
                if self.parsed_url.scheme == 'sqlite':
                    # For SQLite, check if file exists or can be created
                    db_path = self.parsed_url.path
                    exists = os.path.exists(db_path) if db_path != ':memory:' else True
                    
                    self.diagnostic_results['database_existence'] = {
                        'passed': True,
                        'details': {
                            'type': 'sqlite',
                            'path': db_path,
                            'exists': exists,
                            'in_memory': db_path == ':memory:'
                        }
                    }
                else:
                    # For PostgreSQL, get database info
                    result = conn.execute(text("""
                        SELECT current_database(), 
                               pg_size_pretty(pg_database_size(current_database())),
                               version()
                    """))
                    db_info = result.fetchone()
                    
                    self.diagnostic_results['database_existence'] = {
                        'passed': True,
                        'details': {
                            'type': 'postgresql',
                            'database_name': str(db_info[0]),
                            'size': str(db_info[1]),
                            'version': str(db_info[2]).split(' ')[0:2]  # PostgreSQL version only
                        }
                    }
                
                logger.info("✅ Database existence verified")
                
        except Exception as e:
            raise DatabaseDiagnosticError(
                'DATABASE_ACCESS_FAILED',
                f'Could not verify database existence: {str(e)}',
                {'error': str(e)}
            )
    
    def _check_schema_compatibility(self):
        """Check database schema compatibility and existing tables"""
        logger.info("📋 Checking schema compatibility and existing tables...")
        
        try:
            inspector = inspect(self.engine)
            existing_tables = inspector.get_table_names()
            
            # Expected tables for Stevedores Dashboard
            expected_tables = ['user', 'vessel', 'cargo_tally']
            existing_expected = [table for table in expected_tables if table in existing_tables]
            missing_tables = [table for table in expected_tables if table not in existing_tables]
            
            schema_info = {
                'total_existing_tables': len(existing_tables),
                'existing_tables': existing_tables,
                'expected_tables': expected_tables,
                'existing_expected_tables': existing_expected,
                'missing_tables': missing_tables,
                'schema_exists': len(existing_expected) > 0
            }
            
            # Check table structure for existing tables
            table_structures = {}
            for table in existing_expected:
                try:
                    columns = inspector.get_columns(table)
                    table_structures[table] = {
                        'columns': [col['name'] for col in columns],
                        'column_count': len(columns)
                    }
                except Exception as e:
                    table_structures[table] = {'error': str(e)}
            
            schema_info['table_structures'] = table_structures
            
            self.diagnostic_results['schema_compatibility'] = {
                'passed': True,
                'details': schema_info
            }
            
            if missing_tables:
                logger.info(f"ℹ️  Missing tables will be created: {missing_tables}")
            if existing_expected:
                logger.info(f"✅ Found existing tables: {existing_expected}")
            
        except Exception as e:
            # Schema check failure is not critical - tables can be created
            logger.warning(f"⚠️  Schema compatibility check failed: {str(e)}")
            self.diagnostic_results['schema_compatibility'] = {
                'passed': False,
                'details': {
                    'error': str(e),
                    'message': 'Schema check failed but tables can still be created'
                }
            }
    
    def _test_table_operations(self):
        """Test table creation, insertion, and query operations"""
        logger.info("🛠️  Testing table creation and basic operations...")
        
        if not self.app_context:
            logger.warning("⚠️  No app context provided - skipping table operations test")
            self.diagnostic_results['table_operations'] = {
                'passed': False,
                'details': {'message': 'No app context provided for SQLAlchemy operations'}
            }
            return
        
        try:
            with self.app_context:
                from app import db, User, Vessel, CargoTally
                
                # Create all tables
                start_time = time.time()
                db.create_all()
                creation_time = time.time() - start_time
                
                # Verify tables were created
                inspector = inspect(db.engine)
                created_tables = inspector.get_table_names()
                
                self.diagnostic_results['table_operations'] = {
                    'passed': True,
                    'details': {
                        'creation_time_ms': round(creation_time * 1000, 2),
                        'tables_created': created_tables,
                        'expected_tables': ['user', 'vessel', 'cargo_tally'],
                        'all_tables_created': all(table in created_tables for table in ['user', 'vessel', 'cargo_tally'])
                    }
                }
                
                logger.info(f"✅ Table operations successful ({creation_time*1000:.2f}ms)")
                
        except Exception as e:
            raise DatabaseDiagnosticError(
                'TABLE_OPERATIONS_FAILED',
                f'Table operations failed: {str(e)}',
                {'error': str(e)}
            )
    
    def _test_demo_data_creation(self):
        """Test demo data insertion to verify full database functionality"""
        logger.info("👤 Testing demo data creation and insertion...")
        
        if not self.app_context:
            logger.warning("⚠️  No app context provided - skipping demo data test")
            self.diagnostic_results['demo_data_creation'] = {
                'passed': False,
                'details': {'message': 'No app context provided for demo data creation'}
            }
            return
        
        try:
            with self.app_context:
                from app import db, User
                
                # Check if demo user already exists
                existing_demo = User.query.filter_by(email='demo@maritime.test').first()
                
                if existing_demo:
                    logger.info("ℹ️  Demo user already exists - skipping creation")
                    user_created = False
                else:
                    # Create demo user
                    start_time = time.time()
                    demo_user = User(
                        email='demo@maritime.test',
                        username='demo_user',
                        password_hash=generate_password_hash('demo123'),
                        is_active=True
                    )
                    db.session.add(demo_user)
                    db.session.commit()
                    creation_time = time.time() - start_time
                    user_created = True
                
                # Verify demo user exists
                demo_user = User.query.filter_by(email='demo@maritime.test').first()
                if not demo_user:
                    raise DatabaseDiagnosticError(
                        'DEMO_DATA_VERIFICATION_FAILED',
                        'Demo user was not found after creation',
                        {}
                    )
                
                self.diagnostic_results['demo_data_creation'] = {
                    'passed': True,
                    'details': {
                        'demo_user_created': user_created,
                        'demo_user_exists': True,
                        'demo_user_email': 'demo@maritime.test',
                        'creation_time_ms': round(creation_time * 1000, 2) if user_created else 0
                    }
                }
                
                logger.info(f"✅ Demo data {'created' if user_created else 'verified'} successfully")
                
        except Exception as e:
            raise DatabaseDiagnosticError(
                'DEMO_DATA_CREATION_FAILED',
                f'Demo data creation failed: {str(e)}',
                {'error': str(e)}
            )
    
    def _monitor_connection_pool_health(self):
        """Monitor database connection pool health and performance"""
        logger.info("🏊 Monitoring connection pool health...")
        
        try:
            pool_info = {
                'pool_available': False,
                'engine_info': {}
            }
            
            if self.engine and hasattr(self.engine, 'pool'):
                pool = self.engine.pool
                pool_info.update({
                    'pool_available': True,
                    'pool_size': pool.size(),
                    'checked_out_connections': pool.checkedout(),
                    'checked_in_connections': pool.checkedin(),
                    'pool_class': pool.__class__.__name__
                })
                
                # Test pool performance
                start_time = time.time()
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                pool_response_time = time.time() - start_time
                
                pool_info['pool_response_time_ms'] = round(pool_response_time * 1000, 2)
            
            # Get engine information
            if self.engine:
                pool_info['engine_info'] = {
                    'engine_class': self.engine.__class__.__name__,
                    'driver': str(self.engine.driver) if hasattr(self.engine, 'driver') else 'unknown',
                    'url_scheme': self.parsed_url.scheme
                }
            
            self.diagnostic_results['connection_pool_health'] = {
                'passed': True,
                'details': pool_info
            }
            
            logger.info("✅ Connection pool health monitoring completed")
            
        except Exception as e:
            # Connection pool monitoring failure is not critical
            logger.warning(f"⚠️  Connection pool monitoring failed: {str(e)}")
            self.diagnostic_results['connection_pool_health'] = {
                'passed': False,
                'details': {
                    'error': str(e),
                    'message': 'Connection pool monitoring failed but database is functional'
                }
            }
    
    def get_diagnostic_summary(self) -> Dict[str, Any]:
        """Get a summary of diagnostic results with actionable recommendations"""
        passed_checks = sum(1 for result in self.diagnostic_results.values() 
                          if isinstance(result, dict) and result.get('passed', False))
        total_checks = len([k for k in self.diagnostic_results.keys() if k != 'error'])
        
        summary = {
            'overall_status': 'healthy' if passed_checks == total_checks and 'error' not in self.diagnostic_results else 'failed',
            'checks_passed': passed_checks,
            'total_checks': total_checks,
            'success_rate': round((passed_checks / total_checks) * 100, 1) if total_checks > 0 else 0,
            'critical_issues': [],
            'warnings': [],
            'recommendations': []
        }
        
        # Analyze results for issues and recommendations
        if 'error' in self.diagnostic_results:
            error = self.diagnostic_results['error']
            summary['critical_issues'].append({
                'type': error['type'],
                'message': error['message'],
                'category': 'database_connection'
            })
            
            # Add specific recommendations based on error type
            if error['type'] == 'AUTHENTICATION_FAILED':
                summary['recommendations'].extend([
                    'Verify DATABASE_URL contains correct username and password',
                    'Check database user permissions and access rights',
                    'Confirm database server is accepting connections'
                ])
            elif error['type'] == 'NETWORK_CONNECTIVITY_FAILED':
                summary['recommendations'].extend([
                    'Check network connectivity to database host',
                    'Verify database server is running and accessible',
                    'Check firewall rules and security groups'
                ])
            elif error['type'] == 'DATABASE_NOT_FOUND':
                summary['recommendations'].extend([
                    'Create the target database on the server',
                    'Verify DATABASE_URL database name is correct',
                    'Check database user has access to the specified database'
                ])
        
        # Check for warnings in successful tests
        for check_name, result in self.diagnostic_results.items():
            if isinstance(result, dict) and not result.get('passed', True):
                summary['warnings'].append({
                    'check': check_name,
                    'message': result.get('details', {}).get('message', 'Check failed')
                })
        
        return summary


def run_database_diagnostics(database_url: str, app_context=None) -> Dict[str, Any]:
    """Convenience function to run comprehensive database diagnostics"""
    diagnostics = DatabaseDiagnostics(database_url, app_context)
    results = diagnostics.run_comprehensive_diagnostics()
    summary = diagnostics.get_diagnostic_summary()
    
    return {
        'diagnostics': results,
        'summary': summary,
        'timestamp': time.time()
    }
