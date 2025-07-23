#!/usr/bin/env python3
"""
Test script for cargo tally widgets system
Tests both online and offline functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, init_database
import requests
import json

def test_cargo_widget_system():
    """Test the cargo tally widget system"""
    
    print("🧪 Testing Cargo Tally Widget System")
    print("=" * 50)
    
    # Initialize database
    with app.app_context():
        if not init_database():
            print("❌ Database initialization failed")
            return False
    
    # Start the app in test mode
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as client:
        
        print("\n1. Testing offline dashboard data endpoint...")
        response = client.get('/offline-dashboard/dashboard-data')
        
        if response.status_code == 200:
            data = json.loads(response.data)
            print(f"✅ Dashboard data loaded: {data.get('success', False)}")
            print(f"   Mode: {data.get('mode', 'unknown')}")
            print(f"   Vessels: {len(data.get('vessels', []))}")
        else:
            print(f"❌ Dashboard data failed: {response.status_code}")
        
        print("\n2. Testing vessel data endpoint...")
        # Test with non-existent vessel first
        response = client.get('/offline-dashboard/vessel/999/data')
        if response.status_code in [200, 404]:
            print("✅ Vessel data endpoint responds correctly to invalid ID")
        
        print("\n3. Testing cargo tally widget JavaScript file...")
        response = client.get('/static/js/cargo-tally-widgets.js')
        if response.status_code == 200:
            js_content = response.data.decode('utf-8')
            if 'CargoTallyWidget' in js_content:
                print("✅ Cargo tally widget JavaScript file accessible")
                print(f"   File size: {len(js_content)} bytes")
            else:
                print("❌ JavaScript file missing CargoTallyWidget class")
        else:
            print(f"❌ JavaScript file not accessible: {response.status_code}")
        
        print("\n4. Testing offline functionality...")
        # Test cache refresh
        response = client.post('/offline-dashboard/cache/refresh', 
                             json={'type': 'vessels'})
        if response.status_code == 200:
            print("✅ Cache refresh works")
        else:
            print(f"❌ Cache refresh failed: {response.status_code}")
        
        print("\n5. Testing dashboard template rendering...")
        response = client.get('/dashboard')
        if response.status_code in [200, 302]:  # 302 if not logged in
            print("✅ Dashboard template loads")
        else:
            print(f"❌ Dashboard failed: {response.status_code}")
    
    print("\n" + "=" * 50)
    print("🎯 Cargo Tally Widget System Test Complete")
    return True

if __name__ == '__main__':
    test_cargo_widget_system()