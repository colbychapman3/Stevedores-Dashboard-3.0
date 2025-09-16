#!/usr/bin/env python3
"""
Test Security Middleware Fixes
Validates that the Flask-Talisman CSP configuration errors are resolved
and enterprise security features are working correctly.
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime, timedelta

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import Flask app and security components
from app import app
from utils.security_middleware import (
    SecurityMiddleware, SecurityViolationTracker, 
    init_security_middleware, get_security_middleware,
    security_health_check, requires_security_clearance
)

class TestSecurityMiddleware(unittest.TestCase):
    """Test suite for security middleware functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['DEBUG'] = False
        self.app.config['SECRET_KEY'] = 'test-secret-key'
        self.client = self.app.test_client()
        
        # Create application context
        self.app_context = self.app.app_context()
        self.app_context.push()
    
    def tearDown(self):
        """Clean up after tests"""
        self.app_context.pop()
    
    def test_security_middleware_initialization(self):
        """Test that security middleware initializes without errors"""
        # Test middleware initialization
        middleware = SecurityMiddleware()
        
        # Mock Flask app with test configuration
        mock_app = Mock()
        mock_app.config = {
            'DEBUG': False,
            'TESTING': True,
            'SECRET_KEY': 'test-key'
        }
        
        # Test initialization doesn't raise TypeError
        try:
            middleware.init_app(mock_app)
            self.assertTrue(True, "SecurityMiddleware initialized without TypeError")
        except TypeError as e:
            if "can only join an iterable" in str(e):
                self.fail(f"CSP TypeError still present: {e}")
            else:
                raise
    
    def test_csp_policy_formatting(self):
        """Test that CSP policy is properly formatted to avoid TypeError"""
        middleware = SecurityMiddleware()
        
        # Test production configuration
        prod_config = {
            'is_production': True,
            'strict_csp': True,
            'force_https': True,
            'enable_hsts': True
        }
        
        csp_policy = middleware._build_csp_policy(prod_config)
        
        # Validate CSP policy structure
        self.assertIsInstance(csp_policy, dict, "CSP policy should be a dictionary")
        
        # Check that all directive values are properly formatted
        for directive, value in csp_policy.items():
            if directive == 'upgrade-insecure-requests':
                self.assertIsInstance(value, bool, f"'{directive}' should be boolean")
            else:
                self.assertIsInstance(value, list, f"'{directive}' should be a list")
                # Ensure all items in list are strings
                for item in value:
                    self.assertIsInstance(item, str, f"All items in '{directive}' should be strings")
    
    def test_development_vs_production_csp(self):
        """Test different CSP policies for development vs production"""
        middleware = SecurityMiddleware()
        
        # Development configuration
        dev_config = {
            'is_production': False,
            'strict_csp': False,
            'force_https': False,
            'enable_hsts': False
        }
        
        dev_csp = middleware._build_csp_policy(dev_config)
        
        # Production configuration
        prod_config = {
            'is_production': True,
            'strict_csp': True,
            'force_https': True,
            'enable_hsts': True
        }
        
        prod_csp = middleware._build_csp_policy(prod_config)
        
        # Development should be more permissive
        self.assertIn("*", dev_csp.get('font-src', []), "Development CSP should allow all fonts")
        self.assertNotIn("*", prod_csp.get('font-src', []), "Production CSP should restrict fonts")
        
        # Production should have frame-ancestors restriction
        self.assertIn('frame-ancestors', prod_csp, "Production CSP should have frame-ancestors")
        self.assertEqual(prod_csp['frame-ancestors'], ["'none'"], "Production should deny framing")
    
    def test_violation_tracker(self):
        """Test security violation tracking functionality"""
        tracker = SecurityViolationTracker()
        
        # Record test violations
        tracker.record_violation('test_violation', 'Test details', {
            'remote_addr': '192.168.1.1',
            'user_agent': 'TestAgent/1.0',
            'url': '/test'
        })
        
        # Check violation was recorded
        violations = tracker.get_recent_violations()
        self.assertEqual(len(violations), 1, "Should have one violation recorded")
        self.assertEqual(violations[0]['type'], 'test_violation', "Violation type should match")
        
        # Test violation statistics
        stats = tracker.get_violation_stats()
        self.assertEqual(stats['total'], 1, "Total violations should be 1")
        self.assertIn('test_violation', stats['types'], "Violation type should be in stats")
    
    @patch('utils.security_middleware.Talisman')
    def test_talisman_fallback_handling(self, mock_talisman):
        """Test graceful fallback when Talisman initialization fails"""
        # Mock Talisman to raise TypeError (simulating CSP configuration error)
        mock_talisman.side_effect = TypeError("can only join an iterable")
        
        middleware = SecurityMiddleware()
        mock_app = Mock()
        mock_app.config = {'DEBUG': False, 'TESTING': True}
        
        # Should not raise exception, should use fallback
        middleware.init_app(mock_app)
        
        # Should still be considered initialized (with fallback)
        self.assertTrue(middleware.is_initialized, "Middleware should initialize with fallback")
    
    def test_permissions_policy_configuration(self):
        """Test Permissions Policy (Feature Policy) configuration"""
        middleware = SecurityMiddleware()
        
        # Production configuration
        prod_config = {'strict_csp': True, 'is_production': True}
        prod_permissions = middleware._build_permissions_policy(prod_config)
        
        # Should deny most permissions in production
        self.assertEqual(prod_permissions['geolocation'], '()', "Production should deny geolocation")
        self.assertEqual(prod_permissions['camera'], '()', "Production should deny camera")
        
        # Development configuration
        dev_config = {'strict_csp': False, 'is_production': False}
        dev_permissions = middleware._build_permissions_policy(dev_config)
        
        # Should be more permissive in development
        self.assertEqual(dev_permissions['geolocation'], '(self)', "Development should allow self geolocation")
    
    def test_nonce_generation(self):
        """Test CSP nonce generation functionality"""
        middleware = SecurityMiddleware()
        
        # Test nonce generation
        nonce1 = middleware._generate_security_nonce()
        nonce2 = middleware._generate_security_nonce()
        
        self.assertIsInstance(nonce1, str, "Nonce should be a string")
        self.assertGreater(len(nonce1), 10, "Nonce should be reasonably long")
        self.assertNotEqual(nonce1, nonce2, "Nonces should be unique")
    
    def test_security_clearance_decorator(self):
        """Test security clearance decorator functionality"""
        
        @requires_security_clearance(level='test')
        def test_endpoint():
            return {'success': True}
        
        # Test with working middleware
        with self.app.test_request_context('/test'):
            # Initialize security middleware for test
            init_security_middleware(self.app)
            
            # Should work with properly initialized middleware
            result = test_endpoint()
            self.assertEqual(result, {'success': True}, "Decorated function should work")
    
    def test_health_check_integration(self):
        """Test security health check functionality"""
        # Initialize security middleware
        init_security_middleware(self.app)
        
        # Test health check
        health_status = security_health_check()
        
        self.assertIsInstance(health_status, dict, "Health check should return dictionary")
        self.assertIn('middleware_initialized', health_status, "Should include initialization status")
        self.assertIn('environment', health_status, "Should include environment information")
    
    def test_security_recommendations(self):
        """Test security recommendation generation"""
        middleware = SecurityMiddleware()
        middleware.security_config = {
            'force_https': False,
            'strict_csp': False,
            'is_production': True
        }
        
        recommendations = middleware._generate_security_recommendations()
        
        self.assertIsInstance(recommendations, list, "Recommendations should be a list")
        self.assertGreater(len(recommendations), 0, "Should have recommendations for insecure config")
    
    def test_csp_violation_endpoint(self):
        """Test CSP violation reporting endpoint"""
        # Initialize security middleware
        init_security_middleware(self.app)
        
        # Test CSP violation report endpoint
        violation_data = {
            'violated-directive': 'script-src',
            'blocked-uri': 'https://evil.com/script.js',
            'document-uri': 'https://example.com/page'
        }
        
        response = self.client.post('/security/csp-report', 
                                  data=json.dumps(violation_data),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 204, "CSP violation report should return 204")


class TestSecurityEndpoints(unittest.TestCase):
    """Test security monitoring endpoints"""
    
    def setUp(self):
        """Set up test environment"""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['DEBUG'] = False
        self.app.config['SECRET_KEY'] = 'test-secret-key'
        self.app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
        self.client = self.app.test_client()
        
        # Create application context
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Initialize security middleware
        init_security_middleware(self.app)
    
    def tearDown(self):
        """Clean up after tests"""
        self.app_context.pop()
    
    def test_health_endpoint_includes_security(self):
        """Test that /health endpoint includes security status"""
        response = self.client.get('/health')
        self.assertIn(response.status_code, [200, 503], "Health endpoint should be accessible")
        
        if response.status_code == 200:
            data = json.loads(response.data)
            self.assertIn('security_status', data, "Health check should include security status")
    
    def test_csp_report_endpoint_exists(self):
        """Test that CSP violation reporting endpoint exists"""
        # Test that the endpoint accepts POST requests
        response = self.client.post('/security/csp-report', 
                                  data='{}',
                                  content_type='application/json')
        
        # Should not return 404 (endpoint exists)
        self.assertNotEqual(response.status_code, 404, "CSP report endpoint should exist")


def run_security_validation_tests():
    """Run comprehensive security validation tests"""
    print("🔒 Running Security Middleware Validation Tests")
    print("=" * 60)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_suite.addTest(unittest.makeSuite(TestSecurityMiddleware))
    test_suite.addTest(unittest.makeSuite(TestSecurityEndpoints))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print results summary
    print("\n" + "=" * 60)
    print("🔒 Security Validation Results:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\n❌ Test Failures:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print("\n⚠️  Test Errors:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.split('Exception:')[-1].strip()}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    
    if success:
        print("\n✅ All security tests passed! CSP TypeError fix validated.")
    else:
        print("\n❌ Some security tests failed. Review implementation.")
    
    print("=" * 60)
    
    return success


if __name__ == '__main__':
    success = run_security_validation_tests()
    sys.exit(0 if success else 1)