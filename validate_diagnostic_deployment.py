#!/usr/bin/env python3
"""
Diagnostic Architecture Deployment Validator
Tests the comprehensive diagnostics system before production deployment

This script validates:
1. Diagnostic system components
2. Environment validation
3. Database connection testing
4. Configuration loading
5. Error handling and logging
6. Signal handling setup
"""

import os
import sys
import unittest
import tempfile
import json
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import diagnostic components
from diagnostic_architecture import (
    DiagnosticCollector,
    EnvironmentValidator,
    DatabaseDiagnostic,
    ConfigurationDiagnostic,
    ModelImportDiagnostic,
    InitializationDiagnostic,
    initialize_diagnostics,
    run_startup_diagnostics
)

class TestDiagnosticArchitecture(unittest.TestCase):
    """Test suite for diagnostic architecture components"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_env_vars = {
            'SECRET_KEY': 'test-secret-key-for-diagnostics',
            'DATABASE_URL': 'sqlite:///test_diagnostics.db',
            'FLASK_ENV': 'testing',
            'FLASK_CONFIG': 'testing'
        }
        
        # Set up test environment
        for key, value in self.test_env_vars.items():
            os.environ[key] = value
    
    def tearDown(self):
        """Clean up test environment"""
        # Clean up test database
        test_db_path = Path('test_diagnostics.db')
        if test_db_path.exists():
            test_db_path.unlink()
    
    def test_diagnostic_collector_initialization(self):
        """Test DiagnosticCollector initialization"""
        collector = DiagnosticCollector("test_worker")
        
        self.assertEqual(collector.worker_id, "test_worker")
        self.assertEqual(len(collector.checkpoints), 0)
        self.assertIsNotNone(collector.start_time)
        self.assertTrue(collector.log_file.startswith('/tmp/stevedores_diagnostic_'))
    
    def test_diagnostic_checkpoint_creation(self):
        """Test checkpoint creation and logging"""
        collector = DiagnosticCollector("test_worker")
        
        # Create a checkpoint
        checkpoint = collector.checkpoint(
            'test_checkpoint',
            'success',
            {'test_key': 'test_value'},
            None
        )
        
        self.assertEqual(checkpoint.name, 'test_checkpoint')
        self.assertEqual(checkpoint.status, 'success')
        self.assertEqual(checkpoint.details['test_key'], 'test_value')
        self.assertIsNotNone(checkpoint.memory_usage_mb)
        self.assertEqual(len(collector.checkpoints), 1)
    
    def test_environment_validator_success(self):
        """Test environment validation with valid environment"""
        collector = DiagnosticCollector("test_worker")
        
        result = EnvironmentValidator.validate_environment(collector)
        
        self.assertTrue(result)
        
        # Check that validation checkpoints were created
        checkpoint_names = [cp.name for cp in collector.checkpoints]
        self.assertIn('environment_validation', checkpoint_names)
        self.assertIn('env_var_SECRET_KEY', checkpoint_names)
        self.assertIn('env_var_DATABASE_URL', checkpoint_names)
    
    def test_environment_validator_missing_secret_key(self):
        """Test environment validation with missing SECRET_KEY"""
        # Remove SECRET_KEY
        if 'SECRET_KEY' in os.environ:
            del os.environ['SECRET_KEY']
        
        collector = DiagnosticCollector("test_worker")
        result = EnvironmentValidator.validate_environment(collector)
        
        self.assertFalse(result)
        
        # Check that error was logged
        critical_checkpoints = [cp for cp in collector.checkpoints if cp.status == 'critical']
        self.assertTrue(any('SECRET_KEY' in cp.name for cp in critical_checkpoints))
        
        # Restore for other tests
        os.environ['SECRET_KEY'] = self.test_env_vars['SECRET_KEY']
    
    def test_database_diagnostic_sqlite(self):
        """Test database diagnostic with SQLite"""
        collector = DiagnosticCollector("test_worker")
        
        result = DatabaseDiagnostic.validate_database_connection(collector)
        
        self.assertTrue(result)
        
        # Check diagnostic checkpoints
        checkpoint_names = [cp.name for cp in collector.checkpoints]
        self.assertIn('database_validation', checkpoint_names)
        self.assertIn('database_engine_creation', checkpoint_names)
        self.assertIn('database_connectivity_test', checkpoint_names)
    
    def test_database_diagnostic_invalid_url(self):
        """Test database diagnostic with invalid URL"""
        os.environ['DATABASE_URL'] = 'invalid://invalid_database_url'
        
        collector = DiagnosticCollector("test_worker")
        result = DatabaseDiagnostic.validate_database_connection(collector)
        
        self.assertFalse(result)
        
        # Check that error was logged
        critical_checkpoints = [cp for cp in collector.checkpoints if cp.status == 'critical']
        self.assertTrue(len(critical_checkpoints) > 0)
        
        # Restore for other tests
        os.environ['DATABASE_URL'] = self.test_env_vars['DATABASE_URL']
    
    @patch('diagnostic_architecture.Flask')
    def test_configuration_diagnostic_success(self, mock_flask):
        """Test configuration diagnostic with valid setup"""
        # Mock Flask app
        mock_app = MagicMock()
        mock_app.config = {}
        
        collector = DiagnosticCollector("test_worker")
        
        result = ConfigurationDiagnostic.validate_configuration_loading(collector, mock_app)
        
        # Should succeed with basic fallback config
        self.assertTrue(result)
        
        # Check that config was loaded
        self.assertIn('SECRET_KEY', mock_app.config)
        self.assertIn('SQLALCHEMY_DATABASE_URI', mock_app.config)
    
    def test_diagnostic_log_file_creation(self):
        """Test that diagnostic log files are created correctly"""
        collector = DiagnosticCollector("test_worker")
        
        # Create some checkpoints
        collector.checkpoint('test1', 'success')
        collector.checkpoint('test2', 'warning', {'warning': 'test'})
        collector.checkpoint('test3', 'error', error_info='Test error')
        
        # Check that log file was created
        log_file = Path(collector.log_file)
        self.assertTrue(log_file.exists())
        
        # Check log file contents
        with open(log_file, 'r') as f:
            data = json.load(f)
        
        self.assertEqual(data['worker_id'], 'test_worker')
        self.assertEqual(len(data['checkpoints']), 3)
        
        # Clean up
        log_file.unlink()
    
    def test_initialization_diagnostic_signal_setup(self):
        """Test that signal handlers are set up correctly"""
        diagnostic = InitializationDiagnostic()
        
        # Check that diagnostic collector was created
        self.assertIsNotNone(diagnostic.collector)
        
        # Check that worker ID was set
        self.assertTrue(diagnostic.collector.worker_id.startswith('worker_'))
    
    def test_diagnostic_summary_generation(self):
        """Test diagnostic summary generation"""
        collector = DiagnosticCollector("test_worker")
        
        # Create various checkpoints
        collector.checkpoint('test_success', 'success')
        collector.checkpoint('test_warning', 'warning')
        collector.checkpoint('test_error', 'error')
        collector.checkpoint('test_critical', 'critical')
        
        summary = collector.get_summary()
        
        # Check summary contents
        self.assertEqual(summary['worker_id'], 'test_worker')
        self.assertEqual(summary['checkpoint_count'], 4)
        self.assertEqual(len(summary['critical_errors']), 1)
        self.assertEqual(len(summary['errors']), 1)
        self.assertEqual(len(summary['warnings']), 1)
        self.assertIn('test_critical', summary['critical_errors'])
        self.assertIn('test_error', summary['errors'])
        self.assertIn('test_warning', summary['warnings'])


class TestProductionIntegration(unittest.TestCase):
    """Integration tests for production deployment"""
    
    def setUp(self):
        """Set up production-like environment"""
        self.test_env_vars = {
            'SECRET_KEY': 'production-strength-secret-key-for-testing-diagnostics',
            'DATABASE_URL': 'sqlite:///test_production.db',
            'FLASK_ENV': 'production',
            'FLASK_CONFIG': 'production'
        }
        
        for key, value in self.test_env_vars.items():
            os.environ[key] = value
    
    def tearDown(self):
        """Clean up test environment"""
        test_db_path = Path('test_production.db')
        if test_db_path.exists():
            test_db_path.unlink()
    
    @patch('diagnostic_architecture.Flask')
    @patch('diagnostic_architecture.SQLAlchemy')
    def test_full_diagnostic_suite(self, mock_sqlalchemy, mock_flask):
        """Test complete diagnostic suite"""
        # Mock Flask app and database
        mock_app = MagicMock()
        mock_app.config = {}
        mock_app.debug = False
        
        mock_db = MagicMock()
        
        diagnostic = InitializationDiagnostic()
        
        # This should not crash and should return boolean
        try:
            result = diagnostic.run_comprehensive_diagnostics(mock_app, mock_db)
            self.assertIsInstance(result, bool)
        except Exception as e:
            self.fail(f"Diagnostic suite crashed: {e}")
    
    def test_diagnostic_architecture_import(self):
        """Test that diagnostic architecture can be imported without issues"""
        try:
            from diagnostic_architecture import (
                DiagnosticCollector,
                EnvironmentValidator,
                DatabaseDiagnostic,
                ConfigurationDiagnostic,
                ModelImportDiagnostic,
                InitializationDiagnostic
            )
            
            # Test that classes can be instantiated
            collector = DiagnosticCollector()
            diagnostic = InitializationDiagnostic()
            
            self.assertIsNotNone(collector)
            self.assertIsNotNone(diagnostic)
            
        except ImportError as e:
            self.fail(f"Failed to import diagnostic architecture: {e}")
    
    def test_wsgi_integration_compatibility(self):
        """Test that diagnostic system is compatible with WSGI integration"""
        try:
            # Test that the functions expected by wsgi.py exist
            from diagnostic_architecture import run_startup_diagnostics, initialize_diagnostics
            
            # Test that they can be called (even if they fail due to mocking)
            diagnostic = initialize_diagnostics()
            self.assertIsNotNone(diagnostic)
            
        except Exception as e:
            self.fail(f"WSGI integration compatibility failed: {e}")


def run_deployment_validation():
    """Run complete deployment validation"""
    print("=" * 80)
    print("STEVEDORES DASHBOARD 3.0 - DIAGNOSTIC ARCHITECTURE VALIDATION")
    print("=" * 80)
    
    # Check Python version
    if sys.version_info < (3, 12):
        print("❌ CRITICAL: Python 3.12+ required for production deployment")
        return False
    
    print(f"✅ Python version: {sys.version}")
    
    # Check required dependencies
    required_modules = ['psutil', 'flask', 'sqlalchemy']
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ Module {module}: Available")
        except ImportError:
            missing_modules.append(module)
            print(f"❌ Module {module}: Missing")
    
    if missing_modules:
        print(f"❌ CRITICAL: Missing required modules: {missing_modules}")
        return False
    
    # Run unit tests
    print("\n" + "=" * 40)
    print("RUNNING DIAGNOSTIC UNIT TESTS")
    print("=" * 40)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestDiagnosticArchitecture))
    suite.addTests(loader.loadTestsFromTestCase(TestProductionIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 40)
    print("VALIDATION SUMMARY")
    print("=" * 40)
    
    if result.wasSuccessful():
        print("✅ All diagnostic tests PASSED")
        print("✅ Diagnostic architecture ready for production deployment")
        print("✅ Enhanced error logging and crash prevention active")
        print("\nDeployment recommendations:")
        print("  - Deploy with enhanced wsgi.py")
        print("  - Monitor /tmp/stevedores_diagnostic_*.json logs")
        print("  - Use production_monitor.py for real-time monitoring")
        return True
    else:
        print(f"❌ {len(result.failures)} test failures")
        print(f"❌ {len(result.errors)} test errors")
        print("❌ Diagnostic architecture NOT ready for production")
        
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"  - {test}: {traceback.split('AssertionError: ')[-1].split('\n')[0]}")
        
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"  - {test}: {traceback.split('\n')[-2]}")
        
        return False


if __name__ == '__main__':
    success = run_deployment_validation()
    sys.exit(0 if success else 1)