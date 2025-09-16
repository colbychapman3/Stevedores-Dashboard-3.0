#!/usr/bin/env python3
"""
Simple CSP Configuration Test
Tests that the Flask-Talisman CSP configuration is properly formatted
to avoid the "TypeError: can only join an iterable" error.
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from utils.security_middleware import SecurityMiddleware
    from flask_talisman import Talisman
    IMPORTS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Import error: {e}")
    IMPORTS_AVAILABLE = False


class TestCSPConfigurationFix(unittest.TestCase):
    """Test that CSP configuration is properly formatted"""
    
    def setUp(self):
        """Set up test environment"""
        if not IMPORTS_AVAILABLE:
            self.skipTest("Required imports not available")
    
    def test_csp_policy_format_production(self):
        """Test production CSP policy formatting"""
        middleware = SecurityMiddleware()
        
        config = {
            'is_production': True,
            'strict_csp': True,
            'force_https': True,
            'enable_hsts': True
        }
        
        csp_policy = middleware._build_csp_policy(config)
        
        print("\n🔍 Testing Production CSP Policy Format:")
        print(f"CSP Policy: {csp_policy}")
        
        # Validate structure
        self.assertIsInstance(csp_policy, dict, "CSP policy must be a dictionary")
        
        # Check each directive
        for directive, value in csp_policy.items():
            print(f"  {directive}: {value} ({type(value).__name__})")
            
            if directive == 'upgrade-insecure-requests':
                self.assertIsInstance(value, bool, f"'{directive}' should be boolean")
            else:
                # All other directives should be lists of strings
                self.assertIsInstance(value, list, f"'{directive}' should be a list")
                for item in value:
                    self.assertIsInstance(item, str, f"All items in '{directive}' should be strings, got {type(item)}")
        
        # Key security directives should be present
        self.assertIn('default-src', csp_policy, "Should have default-src directive")
        self.assertIn('script-src', csp_policy, "Should have script-src directive")
        self.assertIn('style-src', csp_policy, "Should have style-src directive")
        
        # Check specific formatting that caused original TypeError
        self.assertEqual(csp_policy['default-src'], ["'self'"], "default-src should be a list")
        self.assertIsInstance(csp_policy['script-src'], list, "script-src should be a list")
        
        print("✅ Production CSP policy format is correct")
    
    def test_csp_policy_format_development(self):
        """Test development CSP policy formatting"""
        middleware = SecurityMiddleware()
        
        config = {
            'is_production': False,
            'strict_csp': False,
            'force_https': False,
            'enable_hsts': False
        }
        
        csp_policy = middleware._build_csp_policy(config)
        
        print("\n🔍 Testing Development CSP Policy Format:")
        print(f"CSP Policy: {csp_policy}")
        
        # Validate structure
        self.assertIsInstance(csp_policy, dict, "CSP policy must be a dictionary")
        
        # Check each directive format
        for directive, value in csp_policy.items():
            print(f"  {directive}: {value} ({type(value).__name__})")
            self.assertIsInstance(value, list, f"'{directive}' should be a list")
            for item in value:
                self.assertIsInstance(item, str, f"All items in '{directive}' should be strings")
        
        print("✅ Development CSP policy format is correct")
    
    def test_original_error_scenario(self):
        """Test the specific scenario that caused the original TypeError"""
        middleware = SecurityMiddleware()
        
        # This was the problematic configuration pattern
        config = {'strict_csp': True, 'is_production': True, 'force_https': True}
        csp_policy = middleware._build_csp_policy(config)
        
        # The original error occurred when Talisman tried to join CSP directive values
        # Let's simulate what Talisman would do internally
        try:
            for directive, value in csp_policy.items():
                if directive != 'upgrade-insecure-requests':
                    # Talisman joins directive values - this should not fail now
                    if isinstance(value, list):
                        joined_value = ' '.join(value)
                        self.assertIsInstance(joined_value, str, f"Should be able to join {directive} values")
                    else:
                        self.fail(f"Directive {directive} should be a list, got {type(value)}")
            
            print("✅ CSP policy can be properly joined (TypeError fix confirmed)")
            
        except TypeError as e:
            if "can only join an iterable" in str(e):
                self.fail(f"CSP TypeError still present: {e}")
            else:
                raise
    
    @patch('utils.security_middleware.Talisman')
    def test_talisman_initialization_with_fixed_csp(self, mock_talisman):
        """Test that Talisman can be initialized with our fixed CSP configuration"""
        # Mock successful Talisman initialization
        mock_talisman_instance = Mock()
        mock_talisman.return_value = mock_talisman_instance
        
        middleware = SecurityMiddleware()
        mock_app = Mock()
        mock_app.config = {'DEBUG': False, 'TESTING': False}
        
        # This should not raise TypeError anymore
        middleware.init_app(mock_app)
        
        # Check that Talisman was called
        self.assertTrue(mock_talisman.called, "Talisman should be initialized")
        
        # Get the arguments passed to Talisman
        call_args = mock_talisman.call_args
        if call_args:
            kwargs = call_args[1] if len(call_args) > 1 else {}
            csp_policy = kwargs.get('content_security_policy', {})
            
            # Verify CSP policy format
            if csp_policy:
                for directive, value in csp_policy.items():
                    if directive != 'upgrade-insecure-requests':
                        self.assertIsInstance(value, list, f"Directive {directive} should be a list")
        
        print("✅ Talisman initialization with fixed CSP successful")
    
    def test_permissions_policy_format(self):
        """Test Permissions Policy formatting"""
        middleware = SecurityMiddleware()
        
        config = {'strict_csp': True, 'is_production': True}
        permissions_policy = middleware._build_permissions_policy(config)
        
        print(f"\n🔍 Testing Permissions Policy: {permissions_policy}")
        
        self.assertIsInstance(permissions_policy, dict, "Permissions policy should be a dictionary")
        
        for policy, value in permissions_policy.items():
            self.assertIsInstance(value, str, f"Permission '{policy}' should have string value")
            # Common permission policy formats
            self.assertTrue(
                value in ['()', '(self)', '(self "https://example.com")'] or value.startswith('('),
                f"Permission '{policy}' value '{value}' should be properly formatted"
            )
        
        print("✅ Permissions Policy format is correct")


def main():
    """Run the CSP configuration tests"""
    print("🔒 Testing Flask-Talisman CSP Configuration Fix")
    print("=" * 60)
    
    if not IMPORTS_AVAILABLE:
        print("❌ Required modules not available. Install dependencies:")
        print("   pip install flask flask-talisman")
        return False
    
    # Run tests
    unittest.main(verbosity=2, exit=False)
    
    print("\n" + "=" * 60)
    print("🔒 CSP Configuration Test Results:")
    print("✅ All tests completed. Check output above for results.")
    print("=" * 60)
    
    return True


if __name__ == '__main__':
    success = main()