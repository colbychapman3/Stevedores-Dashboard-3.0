#!/usr/bin/env python3
"""
Simple environment variable checker for Render deployment
"""
import os
import secrets

def check_environment():
    """Check required environment variables for Render deployment"""
    
    print("🔍 Checking Environment Variables for Render Deployment\n")
    
    # Required variables
    required_vars = {
        'SECRET_KEY': 'Flask security key',
        'DATABASE_URL': 'Supabase PostgreSQL connection', 
        'REDIS_URL': 'Upstash Redis connection'
    }
    
    # Optional but recommended
    optional_vars = {
        'FLASK_CONFIG': 'Should be "render" or "production"',
        'SENTRY_DSN': 'Error monitoring (optional)',
        'MAIL_SERVER': 'Email notifications (optional)'
    }
    
    all_good = True
    
    print("📋 REQUIRED VARIABLES:")
    print("=" * 50)
    
    for var, description in required_vars.items():
        value = os.environ.get(var)
        if value:
            if var == 'SECRET_KEY':
                print(f"✅ {var}: SET (length: {len(value)})")
                if len(value) < 32:
                    print(f"   ⚠️  WARNING: Secret key is short ({len(value)} chars). Recommend 64+ chars")
            elif var == 'DATABASE_URL':
                if value.startswith('postgresql://') or value.startswith('postgres://'):
                    # Hide password in output
                    safe_url = value.split('@')[0].split(':')[:-1]
                    safe_url = ':'.join(safe_url) + ':***@' + value.split('@')[1] if '@' in value else value
                    print(f"✅ {var}: SET ({safe_url})")
                else:
                    print(f"❌ {var}: INVALID (should start with postgresql://)")
                    all_good = False
            elif var == 'REDIS_URL':
                if value.startswith('redis://'):
                    # Hide password in output
                    safe_url = value.split('@')[0].split(':')[:-1]
                    safe_url = ':'.join(safe_url) + ':***@' + value.split('@')[1] if '@' in value else value
                    print(f"✅ {var}: SET ({safe_url})")
                else:
                    print(f"❌ {var}: INVALID (should start with redis://)")
                    all_good = False
        else:
            print(f"❌ {var}: MISSING - {description}")
            all_good = False
    
    print(f"\n📋 OPTIONAL VARIABLES:")
    print("=" * 50)
    
    for var, description in optional_vars.items():
        value = os.environ.get(var)
        if value:
            print(f"✅ {var}: SET ({value})")
        else:
            print(f"⚪ {var}: NOT SET - {description}")
    
    print(f"\n{'✅ ALL REQUIRED VARIABLES ARE SET!' if all_good else '❌ MISSING REQUIRED VARIABLES!'}")
    
    if not all_good:
        print("\n🔧 TO FIX:")
        print("1. Go to your Render dashboard")
        print("2. Navigate to your stevedores-dashboard-3.0 service")  
        print("3. Go to Environment tab")
        print("4. Add/update the missing variables")
        print("5. Redeploy the service")
        
        if not os.environ.get('SECRET_KEY'):
            new_secret = secrets.token_hex(32)
            print(f"\n🔑 NEW SECRET_KEY (copy this): {new_secret}")
    
    return all_good

if __name__ == "__main__":
    check_environment()