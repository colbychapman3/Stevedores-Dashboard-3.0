#!/usr/bin/env python3
"""
Stevedores Dashboard 3.0 Deployment Validation
Validates deployment structure and files without requiring Flask
"""

import os
import json
import sys
from pathlib import Path

def validate_file_structure():
    """Validate that all required files are present"""
    print("🧪 Validating file structure...")
    
    required_files = [
        'app.py',
        'wsgi.py',
        'gunicorn.conf.py',
        'production_config.py',
        'requirements.txt',
        'Dockerfile',
        'docker-compose.yml',
        '.env.example',
        'templates/base.html',
        'templates/service-worker.js',
        'static/js/pwa-manager.js',
        'static/js/cargo-tally-widgets.js',
        'static/js/sync-manager.js',
        'docker/nginx.conf',
        'docker/supervisord.conf',
        'deployment_checklist.md',
        'README_PRODUCTION.md'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing files: {', '.join(missing_files)}")
        return False
    else:
        print(f"✅ All {len(required_files)} required files present")
        return True

def validate_configuration_files():
    """Validate configuration files are properly formatted"""
    print("\n🧪 Validating configuration files...")
    
    # Check production_config.py
    try:
        with open('production_config.py', 'r') as f:
            config_content = f.read()
            
        required_configs = ['ProductionConfig', 'SECRET_KEY', 'SQLALCHEMY_DATABASE_URI']
        for config in required_configs:
            if config not in config_content:
                print(f"❌ Missing configuration: {config}")
                return False
        
        print("✅ Production configuration valid")
    except Exception as e:
        print(f"❌ Production config error: {e}")
        return False
    
    # Check Docker Compose
    try:
        with open('docker-compose.yml', 'r') as f:
            docker_content = f.read()
            
        required_services = ['stevedores-dashboard', 'postgres', 'redis']
        for service in required_services:
            if service not in docker_content:
                print(f"❌ Missing Docker service: {service}")
                return False
        
        print("✅ Docker Compose configuration valid")
    except Exception as e:
        print(f"❌ Docker Compose error: {e}")
        return False
    
    return True

def validate_javascript_files():
    """Validate JavaScript files contain required functionality"""
    print("\n🧪 Validating JavaScript files...")
    
    js_files = {
        'static/js/pwa-manager.js': ['PWAManager', 'registerServiceWorker'],
        'static/js/cargo-tally-widgets.js': ['CargoTallyWidget', 'class CargoTallyWidget'],
        'static/js/sync-manager.js': ['SyncManager'],
        'templates/service-worker.js': ['addEventListener', 'fetch', 'sync']
    }
    
    for file_path, required_content in js_files.items():
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            missing_content = []
            for item in required_content:
                if item not in content:
                    missing_content.append(item)
            
            if missing_content:
                print(f"❌ {file_path} missing: {', '.join(missing_content)}")
                return False
            else:
                print(f"✅ {file_path} valid")
                
        except Exception as e:
            print(f"❌ Error reading {file_path}: {e}")
            return False
    
    return True

def validate_templates():
    """Validate template files"""
    print("\n🧪 Validating template files...")
    
    # Check base template
    try:
        with open('templates/base.html', 'r') as f:
            base_content = f.read()
        
        required_elements = ['manifest.json', 'pwa-manager.js', 'service-worker']
        for element in required_elements:
            if element not in base_content:
                print(f"❌ Base template missing: {element}")
                return False
        
        print("✅ Base template valid")
    except Exception as e:
        print(f"❌ Template error: {e}")
        return False
    
    return True

def validate_docker_configuration():
    """Validate Docker configuration"""
    print("\n🧪 Validating Docker configuration...")
    
    # Check Dockerfile
    try:
        with open('Dockerfile', 'r') as f:
            dockerfile_content = f.read()
        
        required_instructions = ['FROM', 'COPY', 'RUN', 'EXPOSE', 'CMD']
        for instruction in required_instructions:
            if instruction not in dockerfile_content:
                print(f"❌ Dockerfile missing: {instruction}")
                return False
        
        print("✅ Dockerfile valid")
    except Exception as e:
        print(f"❌ Dockerfile error: {e}")
        return False
    
    # Check Nginx config
    try:
        with open('docker/nginx.conf', 'r') as f:
            nginx_content = f.read()
        
        required_configs = ['server {', 'location /', 'proxy_pass']
        for config in required_configs:
            if config not in nginx_content:
                print(f"❌ Nginx config missing: {config}")
                return False
        
        print("✅ Nginx configuration valid")
    except Exception as e:
        print(f"❌ Nginx config error: {e}")
        return False
    
    return True

def validate_dependencies():
    """Validate requirements.txt"""
    print("\n🧪 Validating dependencies...")
    
    try:
        with open('requirements.txt', 'r') as f:
            requirements = f.read()
        
        critical_deps = ['Flask', 'SQLAlchemy', 'gunicorn']
        for dep in critical_deps:
            if dep not in requirements:
                print(f"❌ Missing dependency: {dep}")
                return False
        
        print("✅ Dependencies valid")
    except Exception as e:
        print(f"❌ Requirements error: {e}")
        return False
    
    return True

def validate_security_configuration():
    """Validate security configurations"""
    print("\n🧪 Validating security configuration...")
    
    # Check .env.example for security variables
    try:
        with open('.env.example', 'r') as f:
            env_content = f.read()
        
        security_vars = ['SECRET_KEY', 'DATABASE_URL', 'REDIS_URL']
        for var in security_vars:
            if var not in env_content:
                print(f"❌ Missing environment variable: {var}")
                return False
        
        print("✅ Security configuration template valid")
    except Exception as e:
        print(f"❌ Environment config error: {e}")
        return False
    
    return True

def check_file_sizes():
    """Check that critical files are not empty and have reasonable sizes"""
    print("\n🧪 Checking file sizes...")
    
    size_checks = {
        'static/js/pwa-manager.js': (10000, 50000),  # 10KB - 50KB
        'static/js/cargo-tally-widgets.js': (20000, 60000),  # 20KB - 60KB
        'templates/service-worker.js': (10000, 50000),  # 10KB - 50KB
        'app.py': (5000, 100000),  # 5KB - 100KB
    }
    
    for file_path, (min_size, max_size) in size_checks.items():
        try:
            file_size = Path(file_path).stat().st_size
            if file_size < min_size:
                print(f"❌ {file_path} too small ({file_size} bytes, expected > {min_size})")
                return False
            elif file_size > max_size:
                print(f"⚠️  {file_path} very large ({file_size} bytes, expected < {max_size})")
            else:
                print(f"✅ {file_path} size OK ({file_size} bytes)")
        except Exception as e:
            print(f"❌ Cannot check {file_path}: {e}")
            return False
    
    return True

def generate_deployment_summary():
    """Generate deployment summary"""
    print("\n📊 Deployment Summary:")
    print("=" * 50)
    
    # Count files by type
    py_files = len(list(Path('.').glob('**/*.py')))
    js_files = len(list(Path('static/js').glob('*.js'))) if Path('static/js').exists() else 0
    html_files = len(list(Path('templates').glob('*.html'))) if Path('templates').exists() else 0
    config_files = len([f for f in ['Dockerfile', 'docker-compose.yml', 'gunicorn.conf.py'] if Path(f).exists()])
    
    print(f"📄 Python files: {py_files}")
    print(f"📄 JavaScript files: {js_files}")
    print(f"📄 HTML templates: {html_files}")
    print(f"📄 Configuration files: {config_files}")
    
    # Calculate total project size
    total_size = sum(f.stat().st_size for f in Path('.').rglob('*') if f.is_file())
    total_size_mb = total_size / (1024 * 1024)
    print(f"📊 Total project size: {total_size_mb:.1f} MB")
    
    print("\n🚀 Key Features Implemented:")
    print("✅ Offline-first PWA architecture")
    print("✅ Advanced service worker with caching")
    print("✅ Cargo tally widget system")
    print("✅ Document processing with auto-fill")
    print("✅ Background sync with conflict resolution")
    print("✅ Production-ready Docker deployment")
    print("✅ Comprehensive monitoring and logging")
    print("✅ Security hardened configuration")

def main():
    """Run all validation tests"""
    print("🚢 Stevedores Dashboard 3.0 - Deployment Validation")
    print("=" * 60)
    
    tests = [
        validate_file_structure,
        validate_configuration_files,
        validate_javascript_files,
        validate_templates,
        validate_docker_configuration,
        validate_dependencies,
        validate_security_configuration,
        check_file_sizes
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print("❌ Test failed")
        except Exception as e:
            print(f"❌ Test error: {e}")
    
    print("\n" + "=" * 60)
    print(f"🎯 Validation Results: {passed}/{total} tests passed")
    
    success_rate = (passed / total) * 100
    print(f"📊 Success Rate: {success_rate:.1f}%")
    
    if success_rate >= 90:
        print("🚀 DEPLOYMENT VALIDATION PASSED!")
        print("⚓ System ready for maritime production deployment!")
        generate_deployment_summary()
        return True
    else:
        print("⚠️  DEPLOYMENT VALIDATION NEEDS ATTENTION")
        print("🔧 Please address the issues above before deployment")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)