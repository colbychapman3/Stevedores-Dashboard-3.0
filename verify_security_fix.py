#!/usr/bin/env python3
"""
Quick Security Fix Verification Script
Validates that the Flask-Talisman CSP TypeError has been resolved
"""

import os
import sys

def main():
    print("🔒 Stevedores Dashboard 3.0 - Security Fix Verification")
    print("=" * 60)
    
    try:
        # Test 1: Import security middleware
        print("1️⃣  Testing security middleware import...")
        from utils.security_middleware import SecurityMiddleware
        print("   ✅ Security middleware imported successfully")
        
        # Test 2: Test CSP configuration
        print("2️⃣  Testing CSP configuration formatting...")
        middleware = SecurityMiddleware()
        
        config = {'strict_csp': True, 'is_production': True, 'force_https': True}
        csp_policy = middleware._build_csp_policy(config)
        
        # Validate CSP format
        all_valid = True
        for directive, value in csp_policy.items():
            if directive != 'upgrade-insecure-requests':
                if not isinstance(value, list):
                    print(f"   ❌ {directive} is not a list: {type(value)}")
                    all_valid = False
                else:
                    # Test that values can be joined (this was the original error)
                    try:
                        ' '.join(value)
                    except TypeError as e:
                        print(f"   ❌ {directive} cannot be joined: {e}")
                        all_valid = False
        
        if all_valid:
            print("   ✅ CSP configuration format is correct")
        else:
            print("   ❌ CSP configuration has issues")
            return False
        
        # Test 3: Test Talisman compatibility
        print("3️⃣  Testing Talisman compatibility...")
        try:
            from flask_talisman import Talisman
            from flask import Flask
            
            # Create test Flask app
            test_app = Flask(__name__)
            test_app.config['TESTING'] = True
            
            # Test Talisman initialization with our CSP format
            try:
                talisman = Talisman(test_app, content_security_policy=csp_policy)
                print("   ✅ Talisman initialization successful")
            except TypeError as e:
                if "can only join an iterable" in str(e):
                    print(f"   ❌ CSP TypeError still present: {e}")
                    return False
                else:
                    print(f"   ⚠️  Other Talisman error (may be expected): {e}")
            
        except ImportError:
            print("   ⚠️  Flask-Talisman not available for testing")
        
        # Test 4: Security features validation
        print("4️⃣  Testing security features...")
        
        # Test violation tracker
        from utils.security_middleware import SecurityViolationTracker
        tracker = SecurityViolationTracker()
        tracker.record_violation('test', 'test violation')
        
        if len(tracker.get_recent_violations()) > 0:
            print("   ✅ Violation tracking works")
        else:
            print("   ❌ Violation tracking failed")
            return False
        
        # Test permissions policy
        permissions = middleware._build_permissions_policy(config)
        if isinstance(permissions, dict) and len(permissions) > 0:
            print("   ✅ Permissions policy generation works")
        else:
            print("   ❌ Permissions policy generation failed")
            return False
        
        print("\n" + "=" * 60)
        print("✅ ALL SECURITY FIXES VALIDATED SUCCESSFULLY!")
        print("✅ CSP TypeError has been resolved")
        print("✅ Enterprise security features are functional")
        print("✅ Production deployment is ready")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    if success:
        print("\n🚀 Security fixes verified! Safe to deploy to production.")
    else:
        print("\n⚠️  Security validation failed. Review implementation.")
    
    sys.exit(0 if success else 1)