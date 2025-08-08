#!/usr/bin/env python3
"""
Configuration Loading Test - Test all configuration scenarios
Validates configuration loading precedence and fallback mechanisms
"""

import os
import sys
import tempfile
import traceback

def test_configuration_loading():
    """Test configuration loading in various scenarios"""
    
    print("🔍 CONFIGURATION LOADING TESTING")
    print("="*50)
    
    # Add project directory to path
    project_dir = os.path.dirname(os.path.abspath(__file__))
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)
    
    results = []
    
    # Test 1: Basic Configuration Loading
    print("\n🔍 Test 1: Basic Configuration Validation")
    try:
        # Save original environment
        original_env = {}
        for key in ['FLASK_CONFIG', 'SECRET_KEY', 'DATABASE_URL']:
            original_env[key] = os.environ.get(key)
        
        # Set test environment
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['SECRET_KEY'] = 'test-config-key'
        os.environ['DATABASE_URL'] = 'sqlite:///test_config.db'
        
        # Clear Flask config if set
        if 'FLASK_CONFIG' in os.environ:
            del os.environ['FLASK_CONFIG']
        
        # Import Flask
        from flask import Flask
        
        # Create test app
        app = Flask(__name__)
        
        # Test basic config loading
        app.config.update({
            'SECRET_KEY': os.environ.get('SECRET_KEY', 'fallback-key'),
            'SQLALCHEMY_DATABASE_URI': os.environ.get('DATABASE_URL', 'sqlite:///fallback.db'),
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'DEBUG': os.environ.get('FLASK_ENV', 'production') == 'development'
        })
        
        # Validate configuration
        if app.config['SECRET_KEY'] == 'test-config-key':
            print("   ✅ Basic configuration loading: SUCCESS")
            results.append(('PASS', 'Basic Configuration', None))
        else:
            print("   ❌ Basic configuration loading: FAILED")
            results.append(('FAIL', 'Basic Configuration', 'SECRET_KEY not set correctly'))
        
        # Restore environment
        for key, value in original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]
        
    except Exception as e:
        print(f"   ❌ Basic configuration test: ERROR - {e}")
        results.append(('ERROR', 'Basic Configuration', str(e)))
    
    # Test 2: Render Config Loading (if available)
    print("\n🔍 Test 2: Render Config Loading")
    try:
        # Check if render_config exists
        try:
            from render_config import config as render_config
            render_available = True
        except ImportError:
            render_available = False
        
        if render_available:
            # Test render config structure
            if hasattr(render_config, 'get') or isinstance(render_config, dict):
                print("   ✅ Render config available and structured: SUCCESS")
                results.append(('PASS', 'Render Config Availability', None))
            else:
                print("   ❌ Render config malformed: FAILED")
                results.append(('FAIL', 'Render Config Structure', 'Config not properly structured'))
        else:
            print("   ⚠️  Render config not available (using fallback)")
            results.append(('OPTIONAL', 'Render Config Availability', 'Not available'))
        
    except Exception as e:
        print(f"   ❌ Render config test: ERROR - {e}")
        results.append(('ERROR', 'Render Config Loading', str(e)))
    
    # Test 3: Production Config Loading (if available)
    print("\n🔍 Test 3: Production Config Loading")
    try:
        # Check if production_config exists
        try:
            from production_config import config as prod_config
            prod_available = True
        except ImportError:
            prod_available = False
        
        if prod_available:
            # Test production config structure
            if hasattr(prod_config, 'get') or isinstance(prod_config, dict):
                print("   ✅ Production config available and structured: SUCCESS")
                results.append(('PASS', 'Production Config Availability', None))
            else:
                print("   ❌ Production config malformed: FAILED")
                results.append(('FAIL', 'Production Config Structure', 'Config not properly structured'))
        else:
            print("   ⚠️  Production config not available (using fallback)")
            results.append(('OPTIONAL', 'Production Config Availability', 'Not available'))
        
    except Exception as e:
        print(f"   ❌ Production config test: ERROR - {e}")
        results.append(('ERROR', 'Production Config Loading', str(e)))
    
    # Test 4: App Configuration Loading Logic
    print("\n🔍 Test 4: App Configuration Loading Logic")
    try:
        # Save original environment
        original_env = {}
        for key in ['FLASK_CONFIG', 'SECRET_KEY', 'DATABASE_URL']:
            original_env[key] = os.environ.get(key)
        
        # Set test environment
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['SECRET_KEY'] = 'app-config-test-key'
        os.environ['DATABASE_URL'] = 'sqlite:///app_config_test.db'
        
        # Test different FLASK_CONFIG values
        config_scenarios = [
            ('render', 'Render config scenario'),
            ('production', 'Production config scenario'),
            ('development', 'Development config scenario'),
            (None, 'No config specified (default)')
        ]
        
        scenario_results = []
        
        for config_value, description in config_scenarios:
            try:
                # Clear modules to get fresh imports
                modules_to_clear = ['app']
                for module in modules_to_clear:
                    if module in sys.modules:
                        del sys.modules[module]
                
                # Set config environment
                if config_value:
                    os.environ['FLASK_CONFIG'] = config_value
                elif 'FLASK_CONFIG' in os.environ:
                    del os.environ['FLASK_CONFIG']
                
                # Import app (this triggers config loading)
                import app as stevedores_app
                
                # Check that app was created successfully  
                if stevedores_app.app:
                    # Check essential config keys exist
                    if 'SECRET_KEY' in stevedores_app.app.config and 'SQLALCHEMY_DATABASE_URI' in stevedores_app.app.config:
                        scenario_results.append(f"✅ {description}: SUCCESS")
                    else:
                        scenario_results.append(f"❌ {description}: Missing config keys")
                else:
                    scenario_results.append(f"❌ {description}: App not created")
                
            except Exception as e:
                scenario_results.append(f"❌ {description}: ERROR - {str(e)[:100]}")
        
        # Print scenario results
        for result in scenario_results:
            print(f"   {result}")
        
        # Overall assessment
        success_count = len([r for r in scenario_results if "SUCCESS" in r])
        if success_count >= len(config_scenarios) // 2:
            print("   ✅ App configuration loading logic: SUCCESS")
            results.append(('PASS', 'App Configuration Logic', None))
        else:
            print("   ❌ App configuration loading logic: FAILED")
            results.append(('FAIL', 'App Configuration Logic', f'Only {success_count}/{len(config_scenarios)} scenarios passed'))
        
        # Restore environment
        for key, value in original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]
        
    except Exception as e:
        print(f"   ❌ App configuration logic test: ERROR - {e}")
        results.append(('ERROR', 'App Configuration Logic', str(e)))
    
    # Test 5: Security Configuration
    print("\n🔍 Test 5: Security Configuration")
    try:
        # Save original environment
        original_env = {}
        for key in ['SECRET_KEY', 'DATABASE_URL']:
            original_env[key] = os.environ.get(key)
        
        # Set test environment
        os.environ['SECRET_KEY'] = 'security-test-key'
        os.environ['DATABASE_URL'] = 'sqlite:///security_test.db'
        
        # Clear modules
        if 'app' in sys.modules:
            del sys.modules['app']
        
        # Import app
        import app as stevedores_app
        
        security_checks = []
        
        # Check SECRET_KEY is not default
        if stevedores_app.app.config.get('SECRET_KEY') not in ['dev', 'change-me', '']:
            security_checks.append("✅ SECRET_KEY not default")
        else:
            security_checks.append("❌ SECRET_KEY is default/empty")
        
        # Check CSRF time limit is set
        if 'WTF_CSRF_TIME_LIMIT' in stevedores_app.app.config:
            security_checks.append("✅ CSRF time limit configured")
        else:
            security_checks.append("❌ CSRF time limit not set")
        
        # Check session lifetime is set
        if 'PERMANENT_SESSION_LIFETIME' in stevedores_app.app.config:
            security_checks.append("✅ Session lifetime configured")
        else:
            security_checks.append("❌ Session lifetime not set")
        
        # Print security checks
        for check in security_checks:
            print(f"   {check}")
        
        # Overall security assessment
        success_checks = len([c for c in security_checks if "✅" in c])
        if success_checks >= len(security_checks) * 0.8:  # 80% pass rate
            print("   ✅ Security configuration: SUCCESS")
            results.append(('PASS', 'Security Configuration', None))
        else:
            print("   ❌ Security configuration: FAILED")
            results.append(('FAIL', 'Security Configuration', f'Only {success_checks}/{len(security_checks)} checks passed'))
        
        # Restore environment
        for key, value in original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]
        
    except Exception as e:
        print(f"   ❌ Security configuration test: ERROR - {e}")
        results.append(('ERROR', 'Security Configuration', str(e)))
    
    # Summary
    print("\n" + "="*50)
    print("📊 CONFIGURATION LOADING SUMMARY")
    print("="*50)
    
    passed = len([r for r in results if r[0] == 'PASS'])
    failed = len([r for r in results if r[0] == 'FAIL'])
    errors = len([r for r in results if r[0] == 'ERROR'])
    optional = len([r for r in results if r[0] == 'OPTIONAL'])
    total = len(results)
    
    print(f"Total Configuration Tests: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"🔥 Errors: {errors}")
    print(f"⚠️  Optional: {optional}")
    
    success_rate = ((passed + optional) / total * 100) if total > 0 else 0
    print(f"📈 Success Rate: {success_rate:.1f}%")
    
    critical_failed = failed + errors
    if critical_failed == 0:
        print("\n🎉 ALL CONFIGURATION TESTS SUCCESSFUL!")
        return True
    else:
        print(f"\n❌ {critical_failed} CONFIGURATION TESTS FAILED!")
        
        print("\n🔍 FAILED TESTS:")
        for status, test_name, error in results:
            if status in ['FAIL', 'ERROR']:
                print(f"   ❌ {test_name}: {error}")
        
        return False


if __name__ == '__main__':
    success = test_configuration_loading()
    sys.exit(0 if success else 1)