#!/usr/bin/env python3
"""
Test script to validate all critical runtime fixes for Stevedores Dashboard 3.0
"""
import os
import sys

def test_imports():
    """Test basic imports work"""
    print("🔍 Testing imports...")
    try:
        import flask
        import flask_sqlalchemy
        import flask_login
        import flask_wtf
        print("✅ All Flask dependencies available")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_secret_key_security():
    """Test that SECRET_KEY is properly secured"""
    print("\n🔐 Testing SECRET_KEY security...")
    
    # Test with no SECRET_KEY env var (should fail securely)
    os.environ.pop('SECRET_KEY', None)  # Remove if exists
    
    try:
        # This should raise ValueError due to our security fix
        import importlib
        if 'app' in sys.modules:
            importlib.reload(sys.modules['app'])
        else:
            import app
        print("❌ Security fix failed: app should require SECRET_KEY")
        return False
    except ValueError as e:
        if "SECRET_KEY environment variable is required" in str(e):
            print("✅ Security fix working: SECRET_KEY is required")
            return True
        else:
            print(f"❌ Unexpected error: {e}")
            return False
    except Exception as e:
        print(f"❌ Unexpected error during SECRET_KEY test: {e}")
        return False

def test_app_with_secret_key():
    """Test app loads properly with SECRET_KEY"""
    print("\n🔧 Testing app startup with SECRET_KEY...")
    
    os.environ['SECRET_KEY'] = 'test-secret-key-for-validation'
    
    try:
        import importlib
        if 'app' in sys.modules:
            importlib.reload(sys.modules['app'])
        else:
            import app
        
        print("✅ App imports successfully with SECRET_KEY")
        
        # Test init_database function exists
        if hasattr(app, 'init_database'):
            print("✅ init_database function is available")
        else:
            print("❌ init_database function missing")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Error loading app: {e}")
        return False

def test_debug_endpoint_removed():
    """Test that debug endpoint has been removed"""
    print("\n🛡️  Testing debug endpoint removal...")
    
    try:
        from routes.auth import auth_bp
        
        # Check if debug endpoint is removed from routes
        debug_routes = [rule.rule for rule in auth_bp.url_map.iter_rules() if 'debug' in rule.rule.lower()]
        
        if debug_routes:
            print(f"❌ Debug routes still exist: {debug_routes}")
            return False
        else:
            print("✅ Debug endpoints successfully removed")
            return True
            
    except Exception as e:
        print(f"❌ Error checking debug endpoints: {e}")
        return False

def main():
    """Run all validation tests"""
    print("🚢 Stevedores Dashboard 3.0 - Critical Fixes Validation")
    print("=" * 60)
    
    tests = [
        ("Import Dependencies", test_imports),
        ("SECRET_KEY Security", test_secret_key_security),
        ("App Startup", test_app_with_secret_key),
        ("Debug Endpoint Removal", test_debug_endpoint_removed)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        try:
            if test_func():
                passed += 1
                print(f"✅ PASSED: {test_name}")
            else:
                print(f"❌ FAILED: {test_name}")
        except Exception as e:
            print(f"❌ ERROR in {test_name}: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 TEST RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL CRITICAL FIXES VALIDATED SUCCESSFULLY!")
        print("✅ Application is ready for deployment")
        return True
    else:
        print("⚠️  Some fixes need attention")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)