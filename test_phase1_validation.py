#!/usr/bin/env python3
"""
Stevedores Dashboard 3.0 - Phase 1 Validation Test Suite
Comprehensive tests to validate all Phase 1 fixes and runtime issues resolution.

TESTING OBJECTIVES:
1. Import Chain Testing - Verify all imports resolve correctly
2. Application Startup - Test that Flask app starts without errors  
3. Database Initialization - Verify init_database() function works
4. Configuration Loading - Test that production config loads properly
5. Basic Functionality - Test core endpoints respond

Test Results: PASS/FAIL with detailed reporting
"""

import os
import sys
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import importlib.util
import sqlite3
import subprocess
import time
import requests
from contextlib import contextmanager
import threading
import json


class Phase1ImportChainTests(unittest.TestCase):
    """Test all imports resolve correctly - Critical for runtime"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_results = []
        
    def test_core_flask_imports(self):
        """Test core Flask and extension imports"""
        print("\n🔍 Testing Core Flask Imports...")
        
        try:
            import flask
            import flask_sqlalchemy
            import flask_login
            import flask_wtf
            self.test_results.append("✅ Core Flask imports: PASS")
            print("✅ Core Flask imports: PASS")
        except ImportError as e:
            self.test_results.append(f"❌ Core Flask imports: FAIL - {e}")
            print(f"❌ Core Flask imports: FAIL - {e}")
            self.fail(f"Core Flask imports failed: {e}")
    
    def test_database_imports(self):
        """Test database-related imports"""
        print("\n🔍 Testing Database Imports...")
        
        try:
            import sqlalchemy
            import psycopg2
            from werkzeug.security import generate_password_hash, check_password_hash
            self.test_results.append("✅ Database imports: PASS")
            print("✅ Database imports: PASS")
        except ImportError as e:
            self.test_results.append(f"❌ Database imports: FAIL - {e}")
            print(f"❌ Database imports: FAIL - {e}")
            self.fail(f"Database imports failed: {e}")
    
    def test_models_imports(self):
        """Test model imports using factory functions"""
        print("\n🔍 Testing Model Imports...")
        
        try:
            # Add the project directory to Python path
            project_dir = os.path.dirname(os.path.abspath(__file__))
            if project_dir not in sys.path:
                sys.path.insert(0, project_dir)
            
            # Test model factory imports
            from models.user import create_user_model
            from models.vessel import create_vessel_model
            from models.cargo_tally import create_cargo_tally_model
            
            self.test_results.append("✅ Model imports: PASS")
            print("✅ Model imports: PASS")
        except ImportError as e:
            self.test_results.append(f"❌ Model imports: FAIL - {e}")
            print(f"❌ Model imports: FAIL - {e}")
            self.fail(f"Model imports failed: {e}")
    
    def test_routes_imports(self):
        """Test route blueprint imports"""
        print("\n🔍 Testing Route Blueprint Imports...")
        
        try:
            # Add the project directory to Python path
            project_dir = os.path.dirname(os.path.abspath(__file__))
            if project_dir not in sys.path:
                sys.path.insert(0, project_dir)
            
            from routes.auth import auth_bp
            from routes.wizard import wizard_bp
            from routes.document_processing import document_bp
            from routes.sync_routes import sync_bp
            from routes.offline_dashboard import offline_dashboard_bp
            
            self.test_results.append("✅ Route imports: PASS")
            print("✅ Route imports: PASS")
        except ImportError as e:
            self.test_results.append(f"❌ Route imports: FAIL - {e}")
            print(f"❌ Route imports: FAIL - {e}")
            self.fail(f"Route imports failed: {e}")
    
    def test_utils_imports(self):
        """Test utility imports"""
        print("\n🔍 Testing Utility Imports...")
        
        try:
            # Add the project directory to Python path
            project_dir = os.path.dirname(os.path.abspath(__file__))
            if project_dir not in sys.path:
                sys.path.insert(0, project_dir)
            
            from utils.offline_data_manager import OfflineDataManager
            from utils.sync_manager import SyncManager
            from utils.document_processor import DocumentProcessor
            
            self.test_results.append("✅ Utility imports: PASS")
            print("✅ Utility imports: PASS")
        except ImportError as e:
            self.test_results.append(f"❌ Utility imports: FAIL - {e}")
            print(f"❌ Utility imports: FAIL - {e}")
            self.fail(f"Utility imports failed: {e}")
    
    def test_config_imports(self):
        """Test configuration imports"""
        print("\n🔍 Testing Configuration Imports...")
        
        try:
            # Add the project directory to Python path
            project_dir = os.path.dirname(os.path.abspath(__file__))
            if project_dir not in sys.path:
                sys.path.insert(0, project_dir)
            
            # Test both config modules exist
            try:
                from render_config import config as render_config
                render_available = True
            except ImportError:
                render_available = False
            
            try:
                from production_config import config as prod_config
                prod_available = True
            except ImportError:
                prod_available = False
            
            if render_available or prod_available:
                self.test_results.append("✅ Config imports: PASS")
                print("✅ Config imports: PASS")
            else:
                self.test_results.append("⚠️  Config imports: No config files found (using fallback)")
                print("⚠️  Config imports: No config files found (using fallback)")
                
        except Exception as e:
            self.test_results.append(f"❌ Config imports: FAIL - {e}")
            print(f"❌ Config imports: FAIL - {e}")
            self.fail(f"Config imports failed: {e}")


class Phase1ApplicationStartupTests(unittest.TestCase):
    """Test Flask application startup without errors"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_results = []
        
    def test_app_creation(self):
        """Test Flask app can be created without errors"""
        print("\n🔍 Testing Application Creation...")
        
        try:
            # Add the project directory to Python path
            project_dir = os.path.dirname(os.path.abspath(__file__))
            if project_dir not in sys.path:
                sys.path.insert(0, project_dir)
            
            # Set test environment variables
            os.environ['FLASK_ENV'] = 'testing'
            os.environ['SECRET_KEY'] = 'test-secret-key'
            os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
            
            # Import and create app
            import app as stevedores_app
            app = stevedores_app.app
            
            # Test app was created
            self.assertIsNotNone(app)
            self.assertEqual(app.name, 'app')
            
            self.test_results.append("✅ App creation: PASS")
            print("✅ App creation: PASS")
            
        except Exception as e:
            self.test_results.append(f"❌ App creation: FAIL - {e}")
            print(f"❌ App creation: FAIL - {e}")
            self.fail(f"App creation failed: {e}")
    
    def test_app_config_loading(self):
        """Test app configuration loads correctly"""
        print("\n🔍 Testing Configuration Loading...")
        
        try:
            # Add the project directory to Python path
            project_dir = os.path.dirname(os.path.abspath(__file__))
            if project_dir not in sys.path:
                sys.path.insert(0, project_dir)
            
            # Set test environment variables
            os.environ['FLASK_ENV'] = 'testing'
            os.environ['SECRET_KEY'] = 'test-secret-key'
            os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
            
            # Import app
            import app as stevedores_app
            app = stevedores_app.app
            
            # Check essential config keys exist
            self.assertIn('SECRET_KEY', app.config)
            self.assertIn('SQLALCHEMY_DATABASE_URI', app.config)
            
            # Check SECRET_KEY is not default
            self.assertNotEqual(app.config['SECRET_KEY'], 'dev')
            
            self.test_results.append("✅ Config loading: PASS")
            print("✅ Config loading: PASS")
            
        except Exception as e:
            self.test_results.append(f"❌ Config loading: FAIL - {e}")
            print(f"❌ Config loading: FAIL - {e}")
            self.fail(f"Config loading failed: {e}")
    
    def test_extensions_initialization(self):
        """Test Flask extensions initialize correctly"""
        print("\n🔍 Testing Extensions Initialization...")
        
        try:
            # Add the project directory to Python path
            project_dir = os.path.dirname(os.path.abspath(__file__))
            if project_dir not in sys.path:
                sys.path.insert(0, project_dir)
            
            # Set test environment variables
            os.environ['FLASK_ENV'] = 'testing'
            os.environ['SECRET_KEY'] = 'test-secret-key'
            os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
            
            # Import app
            import app as stevedores_app
            
            # Check extensions exist
            self.assertIsNotNone(stevedores_app.db)
            self.assertIsNotNone(stevedores_app.csrf)
            self.assertIsNotNone(stevedores_app.login_manager)
            
            self.test_results.append("✅ Extensions initialization: PASS")
            print("✅ Extensions initialization: PASS")
            
        except Exception as e:
            self.test_results.append(f"❌ Extensions initialization: FAIL - {e}")
            print(f"❌ Extensions initialization: FAIL - {e}")
            self.fail(f"Extensions initialization failed: {e}")


class Phase1DatabaseTests(unittest.TestCase):
    """Test database initialization and operations"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_results = []
        self.temp_db = None
        
    def tearDown(self):
        """Clean up test database"""
        if self.temp_db and os.path.exists(self.temp_db):
            os.unlink(self.temp_db)
    
    def test_database_initialization(self):
        """Test init_database() function works correctly"""
        print("\n🔍 Testing Database Initialization...")
        
        try:
            # Add the project directory to Python path
            project_dir = os.path.dirname(os.path.abspath(__file__))
            if project_dir not in sys.path:
                sys.path.insert(0, project_dir)
            
            # Create temporary database
            self.temp_db = tempfile.mktemp(suffix='.db')
            
            # Set test environment variables
            os.environ['FLASK_ENV'] = 'testing'
            os.environ['SECRET_KEY'] = 'test-secret-key'
            os.environ['DATABASE_URL'] = f'sqlite:///{self.temp_db}'
            
            # Import app and initialize database
            import app as stevedores_app
            
            # Test database initialization
            success = stevedores_app.init_database()
            self.assertTrue(success)
            
            # Verify database file was created
            self.assertTrue(os.path.exists(self.temp_db))
            
            # Test database connection
            with stevedores_app.app.app_context():
                # Check tables were created by trying to query them
                users = stevedores_app.User.query.all()
                self.assertIsInstance(users, list)
                
                # Check demo user was created
                demo_user = stevedores_app.User.query.filter_by(email='demo@maritime.test').first()
                self.assertIsNotNone(demo_user)
                self.assertEqual(demo_user.username, 'demo_user')
            
            self.test_results.append("✅ Database initialization: PASS")
            print("✅ Database initialization: PASS")
            
        except Exception as e:
            self.test_results.append(f"❌ Database initialization: FAIL - {e}")
            print(f"❌ Database initialization: FAIL - {e}")
            self.fail(f"Database initialization failed: {e}")
    
    def test_model_creation(self):
        """Test model factory functions create valid models"""
        print("\n🔍 Testing Model Creation...")
        
        try:
            # Add the project directory to Python path
            project_dir = os.path.dirname(os.path.abspath(__file__))
            if project_dir not in sys.path:
                sys.path.insert(0, project_dir)
            
            # Create temporary database
            self.temp_db = tempfile.mktemp(suffix='.db')
            
            # Set test environment variables
            os.environ['FLASK_ENV'] = 'testing'
            os.environ['SECRET_KEY'] = 'test-secret-key'
            os.environ['DATABASE_URL'] = f'sqlite:///{self.temp_db}'
            
            # Import app
            import app as stevedores_app
            
            # Test model classes exist and have expected attributes
            User = stevedores_app.User
            Vessel = stevedores_app.Vessel
            CargoTally = stevedores_app.CargoTally
            
            # Check User model
            self.assertTrue(hasattr(User, 'id'))
            self.assertTrue(hasattr(User, 'email'))
            self.assertTrue(hasattr(User, 'username'))
            
            # Check Vessel model
            self.assertTrue(hasattr(Vessel, 'id'))
            self.assertTrue(hasattr(Vessel, 'name'))
            self.assertTrue(hasattr(Vessel, 'status'))
            
            # Check CargoTally model
            self.assertTrue(hasattr(CargoTally, 'id'))
            self.assertTrue(hasattr(CargoTally, 'vessel_id'))
            self.assertTrue(hasattr(CargoTally, 'cargo_count'))
            
            self.test_results.append("✅ Model creation: PASS")
            print("✅ Model creation: PASS")
            
        except Exception as e:
            self.test_results.append(f"❌ Model creation: FAIL - {e}")
            print(f"❌ Model creation: FAIL - {e}")
            self.fail(f"Model creation failed: {e}")


class Phase1EndpointTests(unittest.TestCase):
    """Test basic functionality of core endpoints"""
    
    def setUp(self):
        """Set up test environment with Flask test client"""
        self.test_results = []
        
        # Add the project directory to Python path
        project_dir = os.path.dirname(os.path.abspath(__file__))
        if project_dir not in sys.path:
            sys.path.insert(0, project_dir)
        
        # Set test environment variables
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['SECRET_KEY'] = 'test-secret-key'
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        
        # Import and configure app for testing
        import app as stevedores_app
        self.app = stevedores_app.app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        
        # Create test client
        self.client = self.app.test_client()
        
        # Initialize database
        with self.app.app_context():
            stevedores_app.init_database()
    
    def test_health_endpoint(self):
        """Test health check endpoint responds correctly"""
        print("\n🔍 Testing Health Endpoint...")
        
        try:
            response = self.client.get('/health')
            self.assertEqual(response.status_code, 200)
            
            data = response.get_json()
            self.assertIn('status', data)
            self.assertEqual(data['status'], 'healthy')
            self.assertIn('version', data)
            self.assertIn('offline_ready', data)
            
            self.test_results.append("✅ Health endpoint: PASS")
            print("✅ Health endpoint: PASS")
            
        except Exception as e:
            self.test_results.append(f"❌ Health endpoint: FAIL - {e}")
            print(f"❌ Health endpoint: FAIL - {e}")
            self.fail(f"Health endpoint failed: {e}")
    
    def test_manifest_endpoint(self):
        """Test PWA manifest endpoint responds correctly"""
        print("\n🔍 Testing Manifest Endpoint...")
        
        try:
            response = self.client.get('/manifest.json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content_type, 'application/manifest+json')
            
            data = response.get_json()
            self.assertIn('name', data)
            self.assertIn('short_name', data)
            self.assertIn('icons', data)
            self.assertIsInstance(data['icons'], list)
            
            self.test_results.append("✅ Manifest endpoint: PASS")
            print("✅ Manifest endpoint: PASS")
            
        except Exception as e:
            self.test_results.append(f"❌ Manifest endpoint: FAIL - {e}")
            print(f"❌ Manifest endpoint: FAIL - {e}")
            self.fail(f"Manifest endpoint failed: {e}")
    
    def test_init_database_endpoint(self):
        """Test database initialization endpoint"""
        print("\n🔍 Testing Init Database Endpoint...")
        
        try:
            response = self.client.get('/init-database')
            self.assertEqual(response.status_code, 200)
            
            data = response.get_json()
            self.assertIn('success', data)
            self.assertTrue(data['success'])
            self.assertIn('message', data)
            self.assertIn('login_credentials', data)
            
            self.test_results.append("✅ Init database endpoint: PASS")
            print("✅ Init database endpoint: PASS")
            
        except Exception as e:
            self.test_results.append(f"❌ Init database endpoint: FAIL - {e}")
            print(f"❌ Init database endpoint: FAIL - {e}")
            self.fail(f"Init database endpoint failed: {e}")
    
    def test_index_endpoint(self):
        """Test index page loads correctly"""
        print("\n🔍 Testing Index Endpoint...")
        
        try:
            response = self.client.get('/')
            self.assertIn(response.status_code, [200, 302])  # 302 if redirect to dashboard
            
            self.test_results.append("✅ Index endpoint: PASS")
            print("✅ Index endpoint: PASS")
            
        except Exception as e:
            self.test_results.append(f"❌ Index endpoint: FAIL - {e}")
            print(f"❌ Index endpoint: FAIL - {e}")
            self.fail(f"Index endpoint failed: {e}")
    
    def test_api_vessels_summary(self):
        """Test vessels API endpoint"""
        print("\n🔍 Testing Vessels API Endpoint...")
        
        try:
            response = self.client.get('/api/vessels/summary')
            self.assertEqual(response.status_code, 200)
            
            data = response.get_json()
            self.assertIn('total_vessels', data)
            self.assertIn('active_vessels', data)
            self.assertIn('vessels', data)
            self.assertIn('timestamp', data)
            self.assertIsInstance(data['vessels'], list)
            
            self.test_results.append("✅ Vessels API endpoint: PASS")
            print("✅ Vessels API endpoint: PASS")
            
        except Exception as e:
            self.test_results.append(f"❌ Vessels API endpoint: FAIL - {e}")
            print(f"❌ Vessels API endpoint: FAIL - {e}")
            self.fail(f"Vessels API endpoint failed: {e}")


class Phase1SecurityTests(unittest.TestCase):
    """Test security configurations are active"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_results = []
        
        # Add the project directory to Python path
        project_dir = os.path.dirname(os.path.abspath(__file__))
        if project_dir not in sys.path:
            sys.path.insert(0, project_dir)
        
        # Set test environment variables
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['SECRET_KEY'] = 'test-secret-key'
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        
        # Import and configure app for testing
        import app as stevedores_app
        self.app = stevedores_app.app
        self.app.config['TESTING'] = True
        
        # Create test client
        self.client = self.app.test_client()
    
    def test_csrf_protection_active(self):
        """Test CSRF protection is configured"""
        print("\n🔍 Testing CSRF Protection...")
        
        try:
            # Import app
            import app as stevedores_app
            
            # Check CSRF is configured
            self.assertIsNotNone(stevedores_app.csrf)
            
            # Check CSRF config exists
            self.assertIn('WTF_CSRF_TIME_LIMIT', self.app.config)
            
            self.test_results.append("✅ CSRF protection: PASS")
            print("✅ CSRF protection: PASS")
            
        except Exception as e:
            self.test_results.append(f"❌ CSRF protection: FAIL - {e}")
            print(f"❌ CSRF protection: FAIL - {e}")
            self.fail(f"CSRF protection failed: {e}")
    
    def test_login_manager_configured(self):
        """Test login manager is properly configured"""
        print("\n🔍 Testing Login Manager...")
        
        try:
            # Import app
            import app as stevedores_app
            
            # Check login manager exists
            self.assertIsNotNone(stevedores_app.login_manager)
            
            # Check login view is set
            self.assertEqual(stevedores_app.login_manager.login_view, 'auth.login')
            
            self.test_results.append("✅ Login manager: PASS")
            print("✅ Login manager: PASS")
            
        except Exception as e:
            self.test_results.append(f"❌ Login manager: FAIL - {e}")
            print(f"❌ Login manager: FAIL - {e}")
            self.fail(f"Login manager failed: {e}")
    
    def test_password_hashing(self):
        """Test password hashing works correctly"""
        print("\n🔍 Testing Password Hashing...")
        
        try:
            from werkzeug.security import generate_password_hash, check_password_hash
            
            # Test password hashing
            password = "test_password123"
            hashed = generate_password_hash(password)
            
            # Check hash was generated
            self.assertIsNotNone(hashed)
            self.assertNotEqual(hashed, password)
            
            # Check verification works
            self.assertTrue(check_password_hash(hashed, password))
            self.assertFalse(check_password_hash(hashed, "wrong_password"))
            
            self.test_results.append("✅ Password hashing: PASS")
            print("✅ Password hashing: PASS")
            
        except Exception as e:
            self.test_results.append(f"❌ Password hashing: FAIL - {e}")
            print(f"❌ Password hashing: FAIL - {e}")
            self.fail(f"Password hashing failed: {e}")


def generate_test_report(all_results):
    """Generate comprehensive test report"""
    print("\n" + "="*80)
    print("📋 STEVEDORES DASHBOARD 3.0 - PHASE 1 VALIDATION REPORT")
    print("="*80)
    
    total_tests = len(all_results)
    passed_tests = len([r for r in all_results if "PASS" in r])
    failed_tests = len([r for r in all_results if "FAIL" in r])
    warnings = len([r for r in all_results if "⚠️" in r])
    
    print(f"\n📊 TEST SUMMARY:")
    print(f"   Total Tests: {total_tests}")
    print(f"   ✅ Passed: {passed_tests}")
    print(f"   ❌ Failed: {failed_tests}")
    print(f"   ⚠️  Warnings: {warnings}")
    
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    print(f"   📈 Success Rate: {success_rate:.1f}%")
    
    print(f"\n📋 DETAILED RESULTS:")
    for result in all_results:
        print(f"   {result}")
    
    print(f"\n🎯 PHASE 1 STATUS:")
    if failed_tests == 0:
        print("   ✅ PHASE 1 VALIDATION: COMPLETE")
        print("   🚀 Application is ready for Phase 2 security fixes")
        status = "READY"
    elif failed_tests < 3:
        print("   ⚠️  PHASE 1 VALIDATION: MOSTLY COMPLETE")  
        print("   🔧 Minor issues need resolution before Phase 2")
        status = "NEEDS_MINOR_FIXES"
    else:
        print("   ❌ PHASE 1 VALIDATION: INCOMPLETE")
        print("   🛠️  Critical issues must be resolved before Phase 2")
        status = "NEEDS_MAJOR_FIXES"
    
    print("="*80)
    
    return {
        'total_tests': total_tests,
        'passed': passed_tests,
        'failed': failed_tests,
        'warnings': warnings,
        'success_rate': success_rate,
        'status': status,
        'results': all_results
    }


def main():
    """Run all Phase 1 validation tests"""
    print("🚀 Starting Stevedores Dashboard 3.0 Phase 1 Validation...")
    print("="*80)
    
    # Collect all test results
    all_results = []
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        Phase1ImportChainTests,
        Phase1ApplicationStartupTests, 
        Phase1DatabaseTests,
        Phase1EndpointTests,
        Phase1SecurityTests
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests with custom result collection
    class ResultCollector(unittest.TextTestRunner):
        def __init__(self):
            super().__init__(verbosity=2)
            self.results = []
    
    # Run each test class individually to collect results
    for test_class in test_classes:
        print(f"\n🔍 Running {test_class.__name__}...")
        
        # Create test suite for this class
        suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
        
        # Run tests
        runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        # Create test instance to get results
        test_instance = test_class()
        test_instance.setUp()
        
        # Run individual test methods to collect results
        for test_method in [method for method in dir(test_instance) if method.startswith('test_')]:
            try:
                getattr(test_instance, test_method)()
                if hasattr(test_instance, 'test_results'):
                    all_results.extend(test_instance.test_results)
            except Exception as e:
                all_results.append(f"❌ {test_method}: FAIL - {e}")
    
    # Generate final report
    report = generate_test_report(all_results)
    
    # Save report to file
    report_file = 'phase1_validation_report.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📁 Report saved to: {report_file}")
    
    # Return status for CI/CD
    return 0 if report['status'] == 'READY' else 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)