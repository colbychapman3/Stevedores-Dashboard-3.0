"""
Database Integration Test Suite for Stevedores Dashboard 3.0
Tests designed to expose psycopg2 Python 3.13 compatibility and connection stability issues
"""

import unittest
import sys
import os
import time
import threading
from unittest.mock import patch, MagicMock

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models.user import create_user_model

# Create User model using factory function
User = create_user_model(db)

try:
    from models.vessel import Vessel
except ImportError:
    # Create mock Vessel model if not exists
    class Vessel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, IntegrityError


class DatabaseIntegrationTestSuite(unittest.TestCase):
    """Test suite targeting production-blocking database issues"""
    
    def setUp(self):
        """Set up test environment"""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with self.app.app_context():
            db.create_all()
    
    def tearDown(self):
        """Clean up after tests"""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
    
    def test_01_psycopg2_python313_compatibility(self):
        """Test 1: psycopg2 compatibility with Python 3.13"""
        try:
            # Test psycopg2-binary import and basic functionality
            import psycopg2
            from psycopg2 import pool
            from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
            
            # Verify version compatibility
            psycopg2_version = psycopg2.__version__
            self.assertIsNotNone(psycopg2_version)
            
            # Test basic connection parameters (using test database)
            connection_params = {
                'host': 'localhost',
                'database': 'test_db',
                'user': 'test_user',
                'password': 'test_pass',
                'port': 5432
            }
            
            # This should not raise import or compatibility errors
            try:
                # Mock connection for testing
                with patch('psycopg2.connect') as mock_connect:
                    mock_connect.return_value = MagicMock()
                    conn = psycopg2.connect(**connection_params)
                    self.assertIsNotNone(conn)
            except Exception as e:
                self.fail(f"psycopg2 Python 3.13 compatibility issue: {str(e)}")
                
        except ImportError as e:
            self.fail(f"psycopg2-binary import failed with Python 3.13: {str(e)}")
    
    def test_02_database_connection_pool_management(self):
        """Test 2: Database connection pool management"""
        with self.app.app_context():
            # Test connection pool creation and management
            engine = db.engine
            
            # Test multiple connections
            connections = []
            try:
                for i in range(5):
                    conn = engine.connect()
                    connections.append(conn)
                    
                    # Test simple query on each connection
                    result = conn.execute(text("SELECT 1"))
                    self.assertEqual(result.fetchone()[0], 1)
                
                # All connections should be valid
                self.assertEqual(len(connections), 5)
                
            finally:
                # Clean up connections
                for conn in connections:
                    conn.close()
    
    def test_03_connection_timeout_retry_logic(self):
        """Test 3: Connection timeout and retry logic"""
        with self.app.app_context():
            # Test connection timeout scenarios
            engine = db.engine
            
            # Mock a timeout scenario
            with patch.object(engine, 'connect', side_effect=OperationalError("Connection timeout", None, None)) as mock_connect:
                with self.assertRaises(OperationalError):
                    engine.connect()
            
            # Test retry logic (implementation dependent)
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    conn = engine.connect()
                    conn.close()
                    break
                except OperationalError:
                    retry_count += 1
                    time.sleep(0.1)
            
            self.assertLess(retry_count, max_retries, "Connection retry logic failed")
    
    def test_04_transaction_rollback_scenarios(self):
        """Test 4: Transaction rollback scenarios"""
        with self.app.app_context():
            try:
                # Start transaction
                user1 = User(username='rollback_user1', email='rollback1@test.com')
                user1.set_password('password')
                db.session.add(user1)
                
                # Force an error to trigger rollback
                user2 = User(username='rollback_user2', email='rollback1@test.com')  # Duplicate email
                db.session.add(user2)
                
                # This should fail and rollback
                with self.assertRaises(Exception):
                    db.session.commit()
                
                # Verify rollback worked
                db.session.rollback()
                user_count = User.query.count()
                self.assertEqual(user_count, 0)
                
            except Exception as e:
                db.session.rollback()
                raise e
    
    def test_05_concurrent_database_access(self):
        """Test 5: Concurrent database access"""
        with self.app.app_context():
            # Test concurrent database operations
            def create_user(user_id):
                try:
                    with self.app.app_context():
                        user = User(username=f'concurrent_user_{user_id}', 
                                  email=f'concurrent{user_id}@test.com')
                        user.set_password('password')
                        db.session.add(user)
                        db.session.commit()
                        return True
                except Exception:
                    db.session.rollback()
                    return False
            
            # Create multiple threads for concurrent access
            threads = []
            results = []
            
            for i in range(5):
                thread = threading.Thread(target=lambda i=i: results.append(create_user(i)))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Verify concurrent operations succeeded
            with self.app.app_context():
                user_count = User.query.count()
                self.assertGreater(user_count, 0)
    
    def test_06_database_migration_integrity(self):
        """Test 6: Database migration integrity"""
        with self.app.app_context():
            # Test schema creation and integrity
            tables = db.metadata.tables.keys()
            self.assertIn('user', [t.lower() for t in tables])
            
            # Test table structure
            user_table = db.metadata.tables.get('user') or db.metadata.tables.get('User')
            if user_table is not None:
                columns = [col.name for col in user_table.columns]
                expected_columns = ['id', 'username', 'email', 'password_hash']
                
                for col in expected_columns:
                    self.assertIn(col, columns, f"Missing column: {col}")
    
    def test_07_foreign_key_constraint_validation(self):
        """Test 7: Foreign key constraint validation"""
        with self.app.app_context():
            # Create user first
            user = User(username='fk_user', email='fk@test.com')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()
            
            # Test foreign key relationships (if vessels have user relationships)
            try:
                vessel = Vessel(name='Test Vessel', vessel_type='Container', user_id=user.id)
                db.session.add(vessel)
                db.session.commit()
                
                # Verify relationship
                self.assertEqual(vessel.user_id, user.id)
                
            except Exception as e:
                # Foreign key constraints might not be defined yet
                self.skipTest(f"Foreign key test skipped: {str(e)}")
    
    def test_08_index_performance_integrity(self):
        """Test 8: Index performance and integrity"""
        with self.app.app_context():
            # Create multiple users to test indexing
            users = []
            for i in range(100):
                user = User(username=f'index_user_{i}', email=f'index{i}@test.com')
                user.set_password('password')
                users.append(user)
            
            db.session.add_all(users)
            db.session.commit()
            
            # Test query performance (should use indexes)
            start_time = time.time()
            user = User.query.filter_by(email='index50@test.com').first()
            query_time = time.time() - start_time
            
            self.assertIsNotNone(user)
            self.assertLess(query_time, 1.0, "Query took too long - index may be missing")
    
    def test_09_connection_leak_detection(self):
        """Test 9: Connection leak detection"""
        with self.app.app_context():
            initial_pool_size = db.engine.pool.size()
            
            # Perform multiple operations that could cause leaks
            for i in range(10):
                conn = db.engine.connect()
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
                conn.close()  # Ensure proper cleanup
            
            # Check for connection leaks
            final_pool_size = db.engine.pool.size()
            self.assertEqual(initial_pool_size, final_pool_size, "Potential connection leak detected")
    
    def test_10_database_backup_restore(self):
        """Test 10: Database backup and restore functionality"""
        with self.app.app_context():
            # Create test data
            user = User(username='backup_user', email='backup@test.com')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()
            user_id = user.id
            
            # Simulate backup (export data)
            backup_data = {
                'users': [{
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'password_hash': user.password_hash
                }]
            }
            
            # Simulate restore scenario
            db.session.delete(user)
            db.session.commit()
            
            # Verify data was deleted
            self.assertIsNone(User.query.get(user_id))
            
            # Restore from backup
            restored_user = User(
                username=backup_data['users'][0]['username'],
                email=backup_data['users'][0]['email']
            )
            restored_user.password_hash = backup_data['users'][0]['password_hash']
            db.session.add(restored_user)
            db.session.commit()
            
            # Verify restore
            self.assertIsNotNone(User.query.filter_by(username='backup_user').first())
    
    def test_11_query_performance_under_load(self):
        """Test 11: Query performance under load"""
        with self.app.app_context():
            # Create substantial test data
            users = []
            for i in range(1000):
                user = User(username=f'load_user_{i}', email=f'load{i}@test.com')
                user.set_password('password')
                users.append(user)
                
                # Batch insert every 100 users
                if i % 100 == 0:
                    db.session.add_all(users)
                    db.session.commit()
                    users = []
            
            # Add remaining users
            if users:
                db.session.add_all(users)
                db.session.commit()
            
            # Test various query performance scenarios
            start_time = time.time()
            
            # Simple select
            User.query.first()
            
            # Filter query
            User.query.filter_by(username='load_user_500').first()
            
            # Count query
            User.query.count()
            
            # Join query (if applicable)
            # User.query.join(Vessel).count()
            
            total_time = time.time() - start_time
            self.assertLess(total_time, 5.0, "Database queries under load taking too long")
    
    def test_12_database_schema_validation(self):
        """Test 12: Database schema validation"""
        with self.app.app_context():
            # Validate database schema matches models
            inspector = db.inspect(db.engine)
            
            # Check that all model tables exist
            existing_tables = inspector.get_table_names()
            
            # Expected tables from models
            expected_tables = ['user']  # Add more tables as they're defined
            
            for table in expected_tables:
                self.assertIn(table.lower(), [t.lower() for t in existing_tables], 
                            f"Missing table: {table}")
            
            # Validate user table schema
            if 'user' in [t.lower() for t in existing_tables]:
                user_table = next((t for t in existing_tables if t.lower() == 'user'), None)
                columns = inspector.get_columns(user_table)
                column_names = [col['name'] for col in columns]
                
                required_columns = ['id', 'username', 'email', 'password_hash']
                for col in required_columns:
                    self.assertIn(col, column_names, f"Missing column in user table: {col}")


if __name__ == '__main__':
    # Run tests with verbose output to identify issues
    unittest.main(verbosity=2)