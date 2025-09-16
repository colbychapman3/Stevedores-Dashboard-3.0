#!/usr/bin/env python3
"""
Production Security Validation Test
Tests the security middleware in production-like conditions
"""

import os
import sys
import time
import requests
import subprocess
import threading
from contextlib import contextmanager

# Set environment variables for production-like testing
os.environ['SECRET_KEY'] = 'test-production-secret-key-12345'
os.environ['FLASK_ENV'] = 'production'
os.environ['DATABASE_URL'] = 'sqlite:///test_production.db'
os.environ['DISABLE_HTTPS_REDIRECT'] = '1'  # For local testing

def start_test_server():
    """Start the Flask app in a separate process for testing"""
    try:
        # Change to the correct directory
        os.chdir('/home/colby/Stevedores-Dashboard-3.0')
        
        # Start the Flask development server
        process = subprocess.Popen([
            'venv/bin/python', 'app.py'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Give the server time to start
        time.sleep(3)
        
        return process
    except Exception as e:
        print(f"❌ Error starting test server: {e}")
        return None

def test_security_headers():
    """Test that security headers are properly set"""
    print("🔍 Testing Security Headers...")
    
    try:
        response = requests.get('http://localhost:5000/health', timeout=5)
        
        print(f"Status Code: {response.status_code}")
        print("Security Headers Found:")
        
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Content-Security-Policy': 'CSP policy present',
            'Cache-Control': 'cache directive present'
        }
        
        headers_present = 0
        for header, expected in security_headers.items():
            if header in response.headers:
                headers_present += 1
                value = response.headers[header][:50] + "..." if len(response.headers[header]) > 50 else response.headers[header]
                print(f"  ✅ {header}: {value}")
            else:
                print(f"  ❌ {header}: Missing")
        
        print(f"Security Headers Score: {headers_present}/{len(security_headers)}")
        return headers_present >= len(security_headers) * 0.7  # 70% pass rate
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error testing security headers: {e}")
        return False

def test_csp_policy():
    """Test that CSP policy is properly configured"""
    print("\n🔍 Testing Content Security Policy...")
    
    try:
        response = requests.get('http://localhost:5000/health', timeout=5)
        
        csp_header = response.headers.get('Content-Security-Policy')
        if csp_header:
            print(f"✅ CSP Header Present: {csp_header[:100]}...")
            
            # Check for key CSP directives
            required_directives = ['default-src', 'script-src', 'style-src', 'object-src']
            found_directives = []
            
            for directive in required_directives:
                if directive in csp_header:
                    found_directives.append(directive)
                    print(f"  ✅ {directive}: Found")
                else:
                    print(f"  ❌ {directive}: Missing")
            
            success = len(found_directives) >= len(required_directives) * 0.8
            print(f"CSP Directives Score: {len(found_directives)}/{len(required_directives)}")
            return success
        else:
            print("❌ No CSP header found")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error testing CSP: {e}")
        return False

def test_health_endpoint_security():
    """Test security status in health endpoint"""
    print("\n🔍 Testing Health Endpoint Security Status...")
    
    try:
        response = requests.get('http://localhost:5000/health', timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            security_status = data.get('security_status', {})
            
            if security_status:
                print("✅ Security Status in Health Check:")
                for key, value in security_status.items():
                    status = "✅" if value else "❌"
                    print(f"  {status} {key}: {value}")
                
                # Check critical security features
                critical_features = ['middleware_initialized', 'csp_enabled']
                all_critical_ok = all(security_status.get(feature, False) for feature in critical_features)
                
                return all_critical_ok
            else:
                print("❌ No security status in health check")
                return False
        else:
            print(f"❌ Health endpoint returned {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing health endpoint: {e}")
        return False

def test_csp_violation_endpoint():
    """Test CSP violation reporting"""
    print("\n🔍 Testing CSP Violation Reporting...")
    
    try:
        violation_report = {
            "csp-report": {
                "violated-directive": "script-src",
                "blocked-uri": "https://evil.com/script.js",
                "document-uri": "http://localhost:5000/dashboard"
            }
        }
        
        response = requests.post(
            'http://localhost:5000/security/csp-report',
            json=violation_report,
            timeout=5
        )
        
        if response.status_code == 204:
            print("✅ CSP violation reporting works")
            return True
        else:
            print(f"❌ CSP violation reporting returned {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing CSP violation reporting: {e}")
        return False

def main():
    """Main test execution"""
    print("🔒 Production Security Validation Test")
    print("=" * 60)
    
    # Start test server
    print("🚀 Starting test server...")
    server_process = start_test_server()
    
    if not server_process:
        print("❌ Failed to start test server")
        return False
    
    try:
        # Wait for server to be fully ready
        print("⏳ Waiting for server to be ready...")
        time.sleep(5)
        
        # Check if server is responding
        try:
            response = requests.get('http://localhost:5000/health', timeout=10)
            print(f"✅ Server is responding (Status: {response.status_code})")
        except Exception as e:
            print(f"❌ Server not responding: {e}")
            return False
        
        # Run security tests
        tests = [
            ("Security Headers", test_security_headers),
            ("CSP Policy", test_csp_policy),
            ("Health Endpoint Security", test_health_endpoint_security),
            ("CSP Violation Reporting", test_csp_violation_endpoint)
        ]
        
        results = []
        for test_name, test_func in tests:
            print(f"\n{'='*20} {test_name} {'='*20}")
            try:
                result = test_func()
                results.append((test_name, result))
                print(f"Result: {'✅ PASS' if result else '❌ FAIL'}")
            except Exception as e:
                print(f"❌ Test error: {e}")
                results.append((test_name, False))
        
        # Print summary
        print(f"\n{'='*60}")
        print("🔒 Production Security Test Results:")
        print(f"{'='*60}")
        
        passed_tests = 0
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} {test_name}")
            if result:
                passed_tests += 1
        
        print(f"\nOverall: {passed_tests}/{len(results)} tests passed")
        
        if passed_tests == len(results):
            print("✅ ALL SECURITY TESTS PASSED! Production ready.")
        elif passed_tests >= len(results) * 0.8:
            print("⚠️  Most security tests passed. Review failed tests.")
        else:
            print("❌ Multiple security tests failed. Review implementation.")
        
        return passed_tests >= len(results) * 0.8
        
    finally:
        # Clean up
        if server_process:
            print("\n🛑 Stopping test server...")
            server_process.terminate()
            server_process.wait(timeout=5)

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)