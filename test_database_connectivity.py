#!/usr/bin/env python3
"""
Database Connectivity Test - Isolated database testing
Tests database initialization, model creation, and basic operations
"""

import os
import sys
import sqlite3
import tempfile
import traceback

def test_database_connectivity():
    """Test database connectivity and initialization"""
    
    print("🔍 DATABASE CONNECTIVITY TESTING")
    print("="*50)
    
    # Add project directory to path
    project_dir = os.path.dirname(os.path.abspath(__file__))
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)
    
    temp_db = None
    results = []
    
    try:
        # Test 1: SQLite Database Creation
        print("\n🔍 Test 1: SQLite Database Creation")
        temp_db = tempfile.mktemp(suffix='.db')
        
        # Test raw SQLite connectivity
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Create a test table
        cursor.execute('''
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert test data
        cursor.execute("INSERT INTO test_table (name) VALUES (?)", ("test_record",))
        conn.commit()
        
        # Query test data
        cursor.execute("SELECT * FROM test_table")
        records = cursor.fetchall()
        
        if len(records) == 1 and records[0][1] == "test_record":
            print("   ✅ SQLite database creation and operations: SUCCESS")
            results.append(('PASS', 'SQLite Basic Operations', None))
        else:
            print("   ❌ SQLite database operations: FAILED")
            results.append(('FAIL', 'SQLite Basic Operations', 'Data verification failed'))
        
        conn.close()
        
    except Exception as e:
        print(f"   ❌ SQLite database test: ERROR - {e}")
        results.append(('ERROR', 'SQLite Basic Operations', str(e)))
    
    try:
        # Test 2: Flask-SQLAlchemy Integration
        print("\n🔍 Test 2: Flask-SQLAlchemy Integration")
        
        # Set test environment
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['SECRET_KEY'] = 'test-db-key'
        os.environ['DATABASE_URL'] = f'sqlite:///{temp_db}'
        
        # Import Flask and SQLAlchemy
        from flask import Flask
        from flask_sqlalchemy import SQLAlchemy
        
        # Create test app
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{temp_db}'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['TESTING'] = True
        
        # Initialize SQLAlchemy
        db = SQLAlchemy(app)
        
        # Define test model
        class TestModel(db.Model):
            __tablename__ = 'flask_test'
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(100), nullable=False)
            
            def to_dict(self):
                return {'id': self.id, 'name': self.name}
        
        # Test database operations within app context
        with app.app_context():
            # Create tables
            db.create_all()
            
            # Test model creation
            test_record = TestModel(name='Flask SQLAlchemy Test')
            db.session.add(test_record)
            db.session.commit()
            
            # Test query
            retrieved = TestModel.query.filter_by(name='Flask SQLAlchemy Test').first()
            
            if retrieved and retrieved.name == 'Flask SQLAlchemy Test':
                print("   ✅ Flask-SQLAlchemy integration: SUCCESS")
                results.append(('PASS', 'Flask-SQLAlchemy Integration', None))
            else:
                print("   ❌ Flask-SQLAlchemy integration: FAILED")
                results.append(('FAIL', 'Flask-SQLAlchemy Integration', 'Model operations failed'))
        
    except Exception as e:
        print(f"   ❌ Flask-SQLAlchemy test: ERROR - {e}")
        results.append(('ERROR', 'Flask-SQLAlchemy Integration', str(e)))
    
    try:
        # Test 3: Model Factory Functions
        print("\n🔍 Test 3: Model Factory Functions")
        
        # Import model factories
        from models.user import create_user_model
        from models.vessel import create_vessel_model
        from models.cargo_tally import create_cargo_tally_model
        
        # Create fresh app and db
        app2 = Flask(__name__)
        app2.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{temp_db}'
        app2.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app2.config['TESTING'] = True
        
        db2 = SQLAlchemy(app2)
        
        # Create models using factories
        User = create_user_model(db2)
        Vessel = create_vessel_model(db2)
        CargoTally = create_cargo_tally_model(db2)
        
        # Test model attributes
        with app2.app_context():
            # Create tables
            db2.create_all()
            
            # Test User model
            if hasattr(User, 'email') and hasattr(User, 'username'):
                print("   ✅ User model factory: SUCCESS")
                results.append(('PASS', 'User Model Factory', None))
            else:
                print("   ❌ User model factory: FAILED")
                results.append(('FAIL', 'User Model Factory', 'Missing attributes'))
            
            # Test Vessel model  
            if hasattr(Vessel, 'name') and hasattr(Vessel, 'status'):
                print("   ✅ Vessel model factory: SUCCESS")
                results.append(('PASS', 'Vessel Model Factory', None))
            else:
                print("   ❌ Vessel model factory: FAILED")
                results.append(('FAIL', 'Vessel Model Factory', 'Missing attributes'))
            
            # Test CargoTally model
            if hasattr(CargoTally, 'vessel_id') and hasattr(CargoTally, 'cargo_count'):
                print("   ✅ CargoTally model factory: SUCCESS")
                results.append(('PASS', 'CargoTally Model Factory', None))
            else:
                print("   ❌ CargoTally model factory: FAILED")
                results.append(('FAIL', 'CargoTally Model Factory', 'Missing attributes'))
        
    except Exception as e:
        print(f"   ❌ Model factory test: ERROR - {e}")
        results.append(('ERROR', 'Model Factory Functions', str(e)))
    
    try:
        # Test 4: App Database Initialization
        print("\n🔍 Test 4: App Database Initialization")
        
        # Create new temp database for app test
        app_db = tempfile.mktemp(suffix='.db')
        os.environ['DATABASE_URL'] = f'sqlite:///{app_db}'
        
        # Import the actual app module
        import app as stevedores_app
        
        # Test initialization function
        with stevedores_app.app.app_context():
            success = stevedores_app.init_database()
            
            if success:
                # Verify demo user was created
                demo_user = stevedores_app.User.query.filter_by(email='demo@maritime.test').first()
                
                if demo_user:
                    print("   ✅ App database initialization: SUCCESS")
                    results.append(('PASS', 'App Database Initialization', None))
                else:
                    print("   ❌ App database initialization: FAILED - No demo user")
                    results.append(('FAIL', 'App Database Initialization', 'Demo user not created'))
            else:
                print("   ❌ App database initialization: FAILED")
                results.append(('FAIL', 'App Database Initialization', 'init_database returned False'))
        
        # Clean up app database
        if os.path.exists(app_db):
            os.unlink(app_db)
        
    except Exception as e:
        print(f"   ❌ App database initialization test: ERROR - {e}")
        results.append(('ERROR', 'App Database Initialization', str(e)))
    
    # Clean up temp database  
    try:
        if temp_db and os.path.exists(temp_db):
            os.unlink(temp_db)
    except:
        pass
    
    # Summary
    print("\n" + "="*50)
    print("📊 DATABASE CONNECTIVITY SUMMARY")
    print("="*50)
    
    passed = len([r for r in results if r[0] == 'PASS'])
    failed = len([r for r in results if r[0] == 'FAIL']) 
    errors = len([r for r in results if r[0] == 'ERROR'])
    total = len(results)
    
    print(f"Total Database Tests: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"🔥 Errors: {errors}")
    
    success_rate = (passed / total * 100) if total > 0 else 0
    print(f"📈 Success Rate: {success_rate:.1f}%")
    
    if failed + errors == 0:
        print("\n🎉 ALL DATABASE TESTS SUCCESSFUL!")
        return True
    else:
        print(f"\n❌ {failed + errors} DATABASE TESTS FAILED!")
        
        print("\n🔍 FAILED TESTS:")
        for status, test_name, error in results:
            if status in ['FAIL', 'ERROR']:
                print(f"   ❌ {test_name}: {error}")
        
        return False


if __name__ == '__main__':
    success = test_database_connectivity()
    sys.exit(0 if success else 1)