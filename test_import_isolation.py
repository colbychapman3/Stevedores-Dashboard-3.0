#!/usr/bin/env python3
"""
Import Isolation Test - Test imports in complete isolation
Validates that all critical imports can be resolved independently
"""

import sys
import os
import importlib
import traceback

def test_import_isolation():
    """Test each import in complete isolation"""
    
    print("🔍 IMPORT ISOLATION TESTING")
    print("="*50)
    
    # Add project directory to path
    project_dir = os.path.dirname(os.path.abspath(__file__))
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)
    
    # Critical imports to test
    imports_to_test = [
        # Core Flask imports
        ('flask', 'Flask framework'),
        ('flask_sqlalchemy', 'Flask-SQLAlchemy extension'),
        ('flask_login', 'Flask-Login extension'),  
        ('flask_wtf', 'Flask-WTF extension'),
        
        # Database imports
        ('sqlalchemy', 'SQLAlchemy ORM'),
        ('psycopg2', 'PostgreSQL adapter'),
        
        # Security imports
        ('werkzeug.security', 'Werkzeug security utilities'),
        ('cryptography', 'Cryptography library'),
        
        # Model imports (relative to project)
        ('models.user', 'User model factory'),
        ('models.vessel', 'Vessel model factory'),
        ('models.cargo_tally', 'CargoTally model factory'),
        
        # Route imports (relative to project)
        ('routes.auth', 'Authentication routes'),
        ('routes.wizard', 'Wizard routes'),
        ('routes.document_processing', 'Document processing routes'),
        ('routes.sync_routes', 'Sync routes'),
        ('routes.offline_dashboard', 'Offline dashboard routes'),
        
        # Utility imports (relative to project)
        ('utils.offline_data_manager', 'Offline data manager'),
        ('utils.sync_manager', 'Sync manager'),
        ('utils.document_processor', 'Document processor'),
        
        # Config imports (optional)
        ('render_config', 'Render configuration (optional)'),
        ('production_config', 'Production configuration (optional)')
    ]
    
    results = []
    
    for module_name, description in imports_to_test:
        print(f"\n🔍 Testing import: {module_name}")
        try:
            # Fresh import each time
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            # Attempt import
            module = importlib.import_module(module_name)
            
            print(f"   ✅ SUCCESS: {description}")
            results.append(('PASS', module_name, description, None))
            
        except ImportError as e:
            # Check if this is an optional import
            if 'optional' in description.lower():
                print(f"   ⚠️  OPTIONAL: {description} - {e}")
                results.append(('OPTIONAL', module_name, description, str(e)))
            else:
                print(f"   ❌ FAILED: {description} - {e}")
                results.append(('FAIL', module_name, description, str(e)))
                
        except Exception as e:
            print(f"   ❌ ERROR: {description} - {e}")
            results.append(('ERROR', module_name, description, str(e)))
    
    # Summary
    print("\n" + "="*50)
    print("📊 IMPORT ISOLATION SUMMARY")
    print("="*50)
    
    passed = len([r for r in results if r[0] == 'PASS'])
    failed = len([r for r in results if r[0] == 'FAIL'])
    errors = len([r for r in results if r[0] == 'ERROR'])
    optional = len([r for r in results if r[0] == 'OPTIONAL'])
    total = len(results)
    
    print(f"Total Imports Tested: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"🔥 Errors: {errors}")
    print(f"⚠️  Optional: {optional}")
    
    critical_failed = failed + errors
    success_rate = ((passed + optional) / total * 100) if total > 0 else 0
    
    print(f"📈 Success Rate: {success_rate:.1f}%")
    
    if critical_failed == 0:
        print("\n🎉 ALL CRITICAL IMPORTS SUCCESSFUL!")
        return True
    else:
        print(f"\n❌ {critical_failed} CRITICAL IMPORTS FAILED!")
        
        print("\n🔍 FAILED IMPORTS:")
        for status, module, desc, error in results:
            if status in ['FAIL', 'ERROR']:
                print(f"   ❌ {module}: {error}")
        
        return False


if __name__ == '__main__':
    success = test_import_isolation()
    sys.exit(0 if success else 1)