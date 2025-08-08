#!/usr/bin/env python3
"""
Test app startup to identify 502 error issues
"""

def test_imports():
    """Test critical imports"""
    try:
        print("Testing Flask imports...")
        from flask import Flask
        print("✅ Flask import successful")
        
        print("Testing SQLAlchemy imports...")
        from flask_sqlalchemy import SQLAlchemy
        print("✅ SQLAlchemy import successful")
        
        print("Testing model imports...")
        from models.vessel import create_vessel_model
        from models.user import create_user_model
        print("✅ Model imports successful")
        
        print("Testing configuration imports...")
        try:
            from render_config import config
            print("✅ Render config import successful")
        except ImportError:
            print("⚠️  Render config not available (fallback mode)")
        
        return True
        
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_app_creation():
    """Test basic app creation"""
    try:
        print("\nTesting app creation...")
        from app import app
        print("✅ App creation successful")
        
        with app.app_context():
            print("✅ App context successful")
            
        return True
        
    except Exception as e:
        print(f"❌ App creation error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("🧪 Stevedores Dashboard Startup Test\n")
    
    if test_imports():
        if test_app_creation():
            print("\n🎉 Startup test passed - App should deploy successfully")
        else:
            print("\n💥 App creation failed - 502 error likely")
    else:
        print("\n💥 Import test failed - 502 error likely")