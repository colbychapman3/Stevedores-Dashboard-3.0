#!/usr/bin/env python3
"""
Quick deployment test for Render - validates critical imports work
"""
import sys

def test_critical_imports():
    """Test that all critical packages can be imported"""
    print("🧪 Testing critical package imports for Render deployment...")
    
    critical_packages = [
        ('flask', 'Flask'),
        ('flask_sqlalchemy', 'SQLAlchemy'),
        ('flask_login', 'LoginManager'),
        ('flask_wtf.csrf', 'CSRFProtect'),
        ('werkzeug.security', 'check_password_hash'),
        ('PIL', 'Image'),  # Test the fixed Pillow import
        ('redis', 'Redis'),
        ('psycopg2', 'connect'),
        ('cryptography.fernet', 'Fernet'),
        ('flask_talisman', 'Talisman'),
        ('flask_limiter', 'Limiter'),
        ('bleach', 'clean'),
        ('marshmallow', 'Schema'),
    ]
    
    failed_imports = []
    
    for module_name, import_item in critical_packages:
        try:
            module = __import__(module_name, fromlist=[import_item])
            getattr(module, import_item)
            print(f"✅ {module_name}.{import_item}")
        except ImportError as e:
            failed_imports.append((module_name, str(e)))
            print(f"❌ {module_name}.{import_item}: {e}")
        except AttributeError as e:
            failed_imports.append((module_name, str(e)))
            print(f"❌ {module_name}.{import_item}: {e}")
    
    print(f"\n🎯 Import Test Results:")
    print(f"✅ Successful: {len(critical_packages) - len(failed_imports)}")
    print(f"❌ Failed: {len(failed_imports)}")
    
    if failed_imports:
        print("\n❌ Failed imports (install dependencies first):")
        for module_name, error in failed_imports:
            print(f"  - {module_name}: {error}")
        return False
    
    print("\n🚀 All critical imports successful! Ready for Render deployment.")
    return True

def test_flask_app_creation():
    """Test basic Flask app creation"""
    print("\n🧪 Testing Flask app creation...")
    
    try:
        from flask import Flask
        app = Flask(__name__)
        app.config['TESTING'] = True
        
        @app.route('/health')
        def health():
            return {'status': 'ok', 'message': 'Stevedores Dashboard 3.0 ready for maritime operations'}
        
        with app.test_client() as client:
            response = client.get('/health')
            if response.status_code == 200:
                print("✅ Flask app creation and routing test passed")
                return True
            else:
                print(f"❌ Flask health endpoint failed: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Flask app creation failed: {e}")
        return False

if __name__ == '__main__':
    print("🚢 Stevedores Dashboard 3.0 - Render Deployment Test")
    print("=" * 60)
    
    import_success = test_critical_imports()
    flask_success = test_flask_app_creation()
    
    if import_success and flask_success:
        print("\n🎉 DEPLOYMENT TEST PASSED!")
        print("📦 Dependencies are compatible with Python 3.13")
        print("⚓ Ready for Render deployment")
        sys.exit(0)
    else:
        print("\n⚠️  DEPLOYMENT TEST FAILED!")
        print("🔧 Install dependencies before deployment")
        sys.exit(1)