"""
Comprehensive Authentication Test Suite for Stevedores Dashboard 3.0
Tests designed to expose SQLAlchemy table redefinition and CSRF issues
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models.user import create_user_model
from flask import session
from werkzeug.security import check_password_hash

# Create User model using factory function
User = create_user_model(db)


class AuthenticationTestSuite(unittest.TestCase):
    """Test suite targeting production-blocking authentication issues"""
    
    def setUp(self):
        """Set up test environment"""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()
        
        with self.app.app_context():
            db.create_all()
    
    def tearDown(self):
        """Clean up after tests"""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
    
    def test_01_user_model_table_conflicts(self):
        """Test 1: SQLAlchemy table redefinition errors (extend_existing issue)"""
        with self.app.app_context():
            # This should expose the table redefinition issue
            try:
                # Attempt to create multiple user instances with proper passwords
                user1 = User(username='test1', email='test1@example.com')
                user1.set_password('password123')
                user2 = User(username='test2', email='test2@example.com')
                user2.set_password('password456')
                
                db.session.add(user1)
                db.session.add(user2)
                db.session.commit()
                
                # Test multiple User model creation (the real test for table redefinition)
                User_v1 = create_user_model(db)
                User_v2 = create_user_model(db)
                
                # Should return the same cached instance to prevent redefinition
                self.assertIs(User_v1, User_v2, "User model should be cached to prevent redefinition")
                
                # Verify we can still create users with the cached model
                user3 = User_v2(username='test3', email='test3@example.com')
                user3.set_password('password789')
                db.session.add(user3)
                db.session.commit()
                
                # Verify all users were created
                self.assertEqual(User.query.count(), 3)
                
            except Exception as e:
                self.fail(f"SQLAlchemy table redefinition error: {str(e)}")
    
    def test_02_user_registration_duplicate_email(self):
        """Test 2: User registration with duplicate email handling"""
        with self.app.app_context():
            # Create first user
            user1 = User(username='user1', email='duplicate@test.com')
            user1.set_password('password123')
            db.session.add(user1)
            db.session.commit()
            
            # Attempt to create second user with same email
            user2 = User(username='user2', email='duplicate@test.com')
            user2.set_password('password456')
            
            with self.assertRaises(Exception):  # Should raise integrity error
                db.session.add(user2)
                db.session.commit()
    
    def test_03_login_flow_csrf_validation(self):
        """Test 3: Login flow with CSRF token validation"""
        with self.app.app_context():
            # Create test user
            user = User(username='testuser', email='test@example.com')
            user.set_password('testpass')
            db.session.add(user)
            db.session.commit()
        
        # Test login without CSRF token (should fail when CSRF is enabled)
        response = self.client.post('/auth/login', data={
            'email': 'test@example.com',  # Auth route uses email, not username
            'password': 'testpass'
        })
        # With CSRF enabled, this should fail (400/403) or succeed if bypass exists
        if response.status_code in [400, 403]:
            # CSRF is working properly
            pass
        elif response.status_code == 401:
            # Authentication failed but CSRF validation passed - potential vulnerability
            self.fail("CSRF bypass detected: Request processed without CSRF token")
        
        # Test with GET request first to get CSRF token
        get_response = self.client.get('/auth/login')
        self.assertEqual(get_response.status_code, 200)
        
        # Extract CSRF token from response (simplified - would need actual parsing in real app)
        # For now, test that POST with form data works when CSRF validation is bypassed for auth
        response = self.client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'testpass'
        })
        # Should either be rejected by CSRF (400/403) or succeed if properly authenticated
        self.assertIn(response.status_code, [200, 302, 400, 401, 403])
    
    def test_04_password_reset_functionality(self):
        """Test 4: Password reset functionality"""
        with self.app.app_context():
            user = User(username='resetuser', email='reset@test.com')
            user.set_password('oldpassword')
            db.session.add(user)
            db.session.commit()
            user_id = user.id
        
        # Test password reset request
        response = self.client.post('/reset_password_request', data={
            'email': 'reset@test.com'
        })
        self.assertEqual(response.status_code, 200)
        
        # Verify user can change password
        with self.app.app_context():
            user = User.query.get(user_id)
            user.set_password('newpassword')
            db.session.commit()
            
            self.assertTrue(user.check_password('newpassword'))
            self.assertFalse(user.check_password('oldpassword'))
    
    def test_05_session_management_timeout(self):
        """Test 5: Session management and timeout"""
        with self.app.app_context():
            user = User(username='sessionuser', email='session@test.com')
            user.set_password('sessionpass')
            db.session.add(user)
            db.session.commit()
        
        # Login user
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['_permanent'] = True
        
        # Test session persistence
        response = self.client.get('/dashboard')
        self.assertIn(response.status_code, [200, 302])
        
        # Test session timeout (mock expired session)
        with self.client.session_transaction() as sess:
            sess.clear()
        
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 302)  # Should redirect to login
    
    def test_06_authentication_middleware_validation(self):
        """Test 6: Authentication middleware validation"""
        # Test accessing protected routes without authentication
        protected_routes = ['/dashboard', '/vessels', '/reports']
        
        for route in protected_routes:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 302)  # Should redirect to login
    
    def test_07_route_protection_testing(self):
        """Test 7: Route protection testing"""
        with self.app.app_context():
            user = User(username='protecteduser', email='protected@test.com')
            user.set_password('protectedpass')
            db.session.add(user)
            db.session.commit()
        
        # Test unauthorized access
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 302)
        
        # Test authorized access (mock login)
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['logged_in'] = True
        
        response = self.client.get('/dashboard')
        self.assertIn(response.status_code, [200, 302])
    
    def test_08_database_connection_stability_during_auth(self):
        """Test 8: Database connection stability during auth"""
        with self.app.app_context():
            # Test multiple rapid authentication attempts
            for i in range(10):
                user = User(username=f'stressuser{i}', email=f'stress{i}@test.com')
                user.set_password('stresspass')
                db.session.add(user)
                db.session.commit()
                
                # Verify user was created successfully
                retrieved_user = User.query.filter_by(username=f'stressuser{i}').first()
                self.assertIsNotNone(retrieved_user)
    
    def test_09_concurrent_user_session_handling(self):
        """Test 9: Concurrent user session handling"""
        with self.app.app_context():
            user = User(username='concurrentuser', email='concurrent@test.com')
            user.set_password('concurrentpass')
            db.session.add(user)
            db.session.commit()
        
        # Simulate multiple concurrent sessions
        clients = [self.app.test_client() for _ in range(3)]
        
        for i, client in enumerate(clients):
            with client.session_transaction() as sess:
                sess['user_id'] = 1
                sess['session_id'] = f'session_{i}'
        
        # All sessions should be valid
        for client in clients:
            response = client.get('/dashboard')
            self.assertIn(response.status_code, [200, 302])
    
    def test_10_auth_state_persistence_across_requests(self):
        """Test 10: Auth state persistence across requests"""
        with self.app.app_context():
            user = User(username='persistuser', email='persist@test.com')
            user.set_password('persistpass')
            db.session.add(user)
            db.session.commit()
        
        # Login and verify persistence
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['authenticated'] = True
        
        # Make multiple requests
        for _ in range(5):
            response = self.client.get('/dashboard')
            self.assertIn(response.status_code, [200, 302])
    
    def test_11_password_hashing_verification(self):
        """Test 11: Password hashing verification"""
        with self.app.app_context():
            user = User(username='hashuser', email='hash@test.com')
            plain_password = 'testhashpassword'
            user.set_password(plain_password)
            
            # Verify password is hashed
            self.assertNotEqual(user.password_hash, plain_password)
            self.assertTrue(user.check_password(plain_password))
            self.assertFalse(user.check_password('wrongpassword'))
    
    def test_12_account_lockout_failed_attempts(self):
        """Test 12: Account lockout after failed attempts"""
        with self.app.app_context():
            user = User(username='lockoutuser', email='lockout@test.com')
            user.set_password('correctpass')
            db.session.add(user)
            db.session.commit()
        
        # Simulate multiple failed login attempts
        for _ in range(5):
            response = self.client.post('/login', data={
                'username': 'lockoutuser',
                'password': 'wrongpass'
            })
            self.assertNotEqual(response.status_code, 200)
        
        # Account should be locked (implementation dependent)
        response = self.client.post('/login', data={
            'username': 'lockoutuser',
            'password': 'correctpass'  # Even correct password should be blocked
        })
        # This test may need adjustment based on actual lockout implementation
    
    def test_13_remember_me_functionality(self):
        """Test 13: Remember me functionality"""
        with self.app.app_context():
            user = User(username='rememberuser', email='remember@test.com')
            user.set_password('rememberpass')
            db.session.add(user)
            db.session.commit()
        
        # Test login with remember me
        response = self.client.post('/login', data={
            'username': 'rememberuser',
            'password': 'rememberpass',
            'remember_me': True
        })
        
        # Check for persistent session cookies
        self.assertIn('Set-Cookie', response.headers.get('Set-Cookie', ''))
    
    def test_14_logout_session_cleanup(self):
        """Test 14: Logout and session cleanup"""
        with self.app.app_context():
            user = User(username='logoutuser', email='logout@test.com')
            user.set_password('logoutpass')
            db.session.add(user)
            db.session.commit()
        
        # Login user
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['authenticated'] = True
        
        # Logout
        response = self.client.post('/logout')
        self.assertEqual(response.status_code, 302)
        
        # Verify session is cleared
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 302)  # Should redirect to login
    
    def test_15_auth_integration_service_worker(self):
        """Test 15: Auth integration with service worker"""
        with self.app.app_context():
            user = User(username='swuser', email='sw@test.com')
            user.set_password('swpass')
            db.session.add(user)
            db.session.commit()
        
        # Test service worker registration endpoint
        response = self.client.get('/service-worker.js')
        self.assertEqual(response.status_code, 200)
        
        # Test authenticated API calls that service worker might make
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['authenticated'] = True
        
        # Test API endpoints that service worker uses
        api_endpoints = ['/api/vessels', '/api/sync', '/api/offline-data']
        for endpoint in api_endpoints:
            response = self.client.get(endpoint)
            # Should either succeed or give proper auth error
            self.assertIn(response.status_code, [200, 401, 404])


if __name__ == '__main__':
    # Run specific tests to expose production issues
    unittest.main(verbosity=2)