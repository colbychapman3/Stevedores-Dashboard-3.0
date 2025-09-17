#!/usr/bin/env python3
"""
Stevedores Dashboard 3.0 - Offline-First Maritime Operations Management
Built for reliable ship operations regardless of connectivity
Python 3.12/3.13 compatible
"""

import os
import sys
import logging
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, make_response, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

# Python version compatibility check
if sys.version_info < (3, 12):
    raise RuntimeError("Python 3.12 or higher is required")

# PostgreSQL compatibility check for Python 3.13
try:
    import psycopg2
    # Test if psycopg2 is compatible with current Python version
    psycopg2_version = psycopg2.__version__
    logging.info(f"psycopg2-binary {psycopg2_version} loaded successfully with Python {sys.version}")
except ImportError:
    logging.warning("psycopg2-binary not available - PostgreSQL features will be limited")

# Initialize Flask app
app = Flask(__name__)

# FORCE CACHE REFRESH: Production build version identifier
DEPLOYMENT_VERSION = "3.0.7-MERGE-CONFLICT-FINAL-FIX-20250810"
print(f"🚢 STEVEDORES DASHBOARD {DEPLOYMENT_VERSION} STARTING...")

# Early logging setup for configuration debugging
logging.basicConfig(level=logging.INFO)
config_logger = logging.getLogger(__name__)

# Configuration - Standardized precedence: env -> render_config -> production_config -> fallback
config_name = os.environ.get('FLASK_CONFIG', 'render')
config_loaded = False

# Try render_config first (preferred for Render deployment)
if not config_loaded:
    try:
        from render_config import config
        app.config.from_object(config[config_name])
        config[config_name].init_app(app)
        config_loaded = True
        config_logger.info(f"✅ Loaded render_config: {config_name}")
    except ImportError:
        config_logger.info("⚠️  render_config not available, trying production_config")

# Fallback to production_config
if not config_loaded:
    try:
        from production_config import config
        fallback_name = 'production' if config_name in ['render', 'production'] else config_name
        if fallback_name in config:
            app.config.from_object(config[fallback_name])
            config[fallback_name].init_app(app)
            config_loaded = True
            config_logger.info(f"✅ Loaded production_config: {fallback_name}")
        else:
            config_logger.warning(f"⚠️  Config '{fallback_name}' not found in production_config")
    except ImportError:
        config_logger.info("⚠️  production_config not available, using basic fallback")
    except Exception as e:
        config_logger.error(f"❌ Error loading production_config: {e}")

# Final fallback to basic configuration
if not config_loaded:
    # SECURITY FIX: Remove hardcoded SECRET_KEY fallback - require environment variable
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        raise ValueError("SECRET_KEY environment variable is required for security. Set SECRET_KEY in your environment.")
    
    app.config.update({
        'SECRET_KEY': secret_key,
        'SQLALCHEMY_DATABASE_URI': os.environ.get('DATABASE_URL', 'sqlite:///stevedores.db'),
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'DEBUG': os.environ.get('FLASK_ENV', 'production') == 'development'
    })
    config_logger.info("✅ Loaded basic fallback configuration with secure SECRET_KEY")

# Database configuration - handled by render_config.py for production

# Fix Supabase postgres:// to postgresql:// if needed
database_url = app.config.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///stevedores.db')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
elif not database_url:
    # Set fallback database URL if none provided
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///stevedores.db'
    config_logger.info("⚠️  No database URL provided, using SQLite fallback")

# SQLAlchemy settings handled by render_config.py

# Security configurations - Fixed: Don't override production CSRF timeout
# app.config['WTF_CSRF_TIME_LIMIT'] = None  # REMOVED: This was overriding production config!
# Only disable CSRF timeout in development/testing, production should use config file setting
if app.config.get('DEBUG', False) or app.config.get('TESTING', False):
    app.config['WTF_CSRF_TIME_LIMIT'] = None  # Only for development
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Initialize extensions
db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access the dashboard.'
login_manager.login_message_category = 'info'


# Database initialization function (used by wsgi.py)
def init_database():
    """Initialize database and create demo users - used by production startup"""
    try:
        logger.info("🚀 Starting comprehensive database initialization...")
        
        # Step 1: Create all tables
        db.create_all()
        logger.info("✅ Database tables created successfully")
        
        # Step 2: Run production database migration to add any missing columns
        try:
            from production_db_migration import initialize_production_migration, run_migration_if_needed
            
            # Initialize migration system
            migration_system = initialize_production_migration(app, db)
            logger.info("✅ Production migration system initialized")
            
            # Run migration if needed
            with app.app_context():
                migration_success, migration_result = run_migration_if_needed()
                if migration_success and migration_result:
                    logger.info(f"✅ Production migration completed: {len(migration_result)} columns added: {migration_result}")
                elif migration_success and not migration_result:
                    logger.info("✅ Database schema is up to date - no migration needed")
                else:
                    logger.warning(f"⚠️  Migration had issues: {migration_result}")
                    
        except Exception as migration_error:
            logger.error(f"❌ Migration system error: {migration_error}")
            # Don't fail init_database completely, but log the issue
            logger.warning("⚠️  Continuing database initialization without migration")
        
        # Step 3: Ensure vessel model is properly initialized with schema detection
        try:
            from models.vessel import create_vessel_model
            Vessel = create_vessel_model(db)
            logger.info("✅ Vessel model initialized with schema compatibility")
        except Exception as vessel_model_error:
            logger.error(f"❌ Vessel model initialization error: {vessel_model_error}")
        
        # Step 4: Create demo users
        users_created = []
        
        # Create simple demo user if it doesn't exist
        if not User.query.filter_by(email='demo@maritime.test').first():
            demo_user = User(
                email='demo@maritime.test',
                username='demo_user',
                password_hash=generate_password_hash('demo123'),
                is_active=True
            )
            db.session.add(demo_user)
            users_created.append('demo@maritime.test')
            logger.info("✅ Demo user created: demo@maritime.test")
        
        # Step 5: Commit all changes
        db.session.commit()
        logger.info(f"🎯 Database initialization completed successfully!")
        logger.info(f"📊 Users created: {users_created}")
        logger.info("🌊 Stevedores Dashboard 3.0 database ready for production!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        return False

# Database initialization and demo user creation
@app.route('/init-database')
def init_database_endpoint():
    """Initialize database and create all demo users - HTTP endpoint"""
    try:
        success = init_database()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Database initialized successfully',
                'login_credentials': 'demo@maritime.test / demo123'
            })
        else:
            return jsonify({'error': 'Database initialization failed - check logs'}), 500
        
    except Exception as e:
        logger.error(f"Database initialization endpoint error: {e}")
        return jsonify({'error': f'Database initialization failed: {str(e)}'}), 500

# API Routes
@app.route('/api/vessels/summary')
def api_vessels_summary():
    """Get vessel summary for dashboard"""
    try:
        vessels = Vessel.query.all()
        summary = {
            'total_vessels': len(vessels),
            'active_vessels': len([v for v in vessels if v.status in ['arrived', 'berthed', 'operations_active']]),
            'vessels': [v.to_dict() for v in vessels],
            'timestamp': datetime.utcnow().isoformat()
        }
        return jsonify(summary)
    except Exception as e:
        logger.error(f"API vessel summary error: {e}")
        return jsonify({'error': 'Failed to fetch vessel summary'}), 500

@app.route('/api/vessels/<int:vessel_id>')
def api_vessel_details(vessel_id):
    """Get individual vessel details"""
    try:
        vessel = Vessel.query.get_or_404(vessel_id)
        return jsonify(vessel.to_dict())
    except Exception as e:
        logger.error(f"API vessel details error: {e}")
        return jsonify({'error': 'Failed to fetch vessel details'}), 500

@app.route('/api/vessels/<int:vessel_id>/cargo-tally', methods=['GET', 'POST'])
@csrf.exempt
def api_vessel_cargo_tally(vessel_id):
    """Handle cargo tally for specific vessel"""
    try:
        vessel = Vessel.query.get_or_404(vessel_id)
        
        if request.method == 'GET':
            # Return recent tallies
            tallies = CargoTally.query.filter_by(vessel_id=vessel_id).order_by(CargoTally.timestamp.desc()).limit(10).all()
            return jsonify({
                'vessel_id': vessel_id,
                'vessel_name': vessel.name,
                'recent_tallies': [tally.to_dict() for tally in tallies],
                'total_loaded': sum([t.cargo_count for t in CargoTally.query.filter_by(vessel_id=vessel_id, tally_type='loaded').all()]),
                'progress': vessel.progress_percentage
            })
        
        elif request.method == 'POST':
            # Add new tally entry
            data = request.get_json()
            
            tally = CargoTally(
                vessel_id=vessel_id,
                tally_type=data.get('tally_type', 'loaded'),
                cargo_count=int(data.get('cargo_count', 1)),
                location=data.get('location', ''),
                notes=data.get('notes', ''),
                shift_period=data.get('shift_period', 'morning')
            )
            
            db.session.add(tally)
            db.session.commit()
            
            # Update vessel progress
            total_loaded = sum([t.cargo_count for t in CargoTally.query.filter_by(vessel_id=vessel_id, tally_type='loaded').all()])
            progress = (total_loaded / vessel.total_cargo_capacity) * 100 if vessel.total_cargo_capacity > 0 else 0
            vessel.update_progress(progress)
            
            return jsonify({
                'success': True,
                'tally_id': tally.id,
                'new_progress': vessel.progress_percentage,
                'total_loaded': total_loaded
            }), 201
            
    except Exception as e:
        logger.error(f"API cargo tally error: {e}")
        return jsonify({'error': 'Failed to process cargo tally'}), 500

# Vessel details page route
@app.route('/vessel/<vessel_id>')
@login_required
def vessel_details(vessel_id):
    """Individual vessel details page with cargo tally widgets"""
    try:
        # Check if it's an offline vessel ID
        if str(vessel_id).startswith('offline_'):
            # Handle offline vessel
            from utils.offline_data_manager import OfflineDataManager
            offline_manager = OfflineDataManager()
            offline_vessels = offline_manager.get_offline_vessels()
            
            vessel_data = next((v for v in offline_vessels if v.get('offline_id') == vessel_id), None)
            if not vessel_data:
                flash('Offline vessel not found', 'error')
                return redirect(url_for('dashboard'))
            
            # Create a vessel-like object for template compatibility
            class OfflineVessel:
                def __init__(self, data):
                    self.id = data.get('offline_id')
                    self.name = data.get('name', 'Unknown Vessel')
                    self.vessel_type = data.get('vessel_type', 'Unknown')
                    self.port_of_call = data.get('port_of_call', '')
                    self.status = data.get('status', 'expected')
                    self.progress_percentage = data.get('progress_percentage', 0)
                    self.total_cargo_capacity = data.get('total_cargo_capacity', 0)
                    self.heavy_equipment_count = data.get('heavy_equipment_count', 0)
                    self.drivers_assigned = data.get('drivers_assigned', 0)
                    self.tico_vehicles_needed = data.get('tico_vehicles_needed', 0)
                    self.eta = data.get('eta')
                    self.etd = data.get('etd')
                
                def get_cargo_loaded(self):
                    return int(self.total_cargo_capacity * (self.progress_percentage / 100))
            
            vessel = OfflineVessel(vessel_data)
            recent_tallies = []  # Offline tallies will be loaded by the widget
            
        else:
            # Handle regular vessel
            vessel = Vessel.query.get_or_404(int(vessel_id))
            recent_tallies = CargoTally.query.filter_by(vessel_id=int(vessel_id)).order_by(CargoTally.timestamp.desc()).limit(5).all()
        
        return render_template('vessel_details.html', 
                             vessel=vessel, 
                             recent_tallies=recent_tallies)
    except Exception as e:
        logger.error(f"Vessel details error: {e}")
        flash('Error loading vessel details', 'error')
        return redirect(url_for('dashboard'))

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    logger.error(f"Internal server error: {error}")
    return render_template('errors/500.html'), 500

# Register blueprints
from routes.auth import auth_bp
from routes.wizard import wizard_bp
from routes.document_processing import document_bp
from routes.sync_routes import sync_bp
from routes.offline_dashboard import offline_dashboard_bp
from routes.health_production import health_bp
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(wizard_bp, url_prefix='/wizard')
app.register_blueprint(document_bp, url_prefix='/document')
app.register_blueprint(sync_bp, url_prefix='/sync')
app.register_blueprint(offline_dashboard_bp, url_prefix='/offline-dashboard')
app.register_blueprint(health_bp)  # No prefix - health checks at /health

csrf.exempt(document_bp)
csrf.exempt(sync_bp) 
csrf.exempt(offline_dashboard_bp)

# SECURITY FIX: Remove CSRF exemption from auth routes to prevent CSRF attacks
# csrf.exempt(auth_bp)  # REMOVED - auth routes should be CSRF protected

# Setup logger
logger = logging.getLogger(__name__)

# CSP Nonce function for templates
@app.context_processor
def inject_csp_nonce():
    """Provide CSP nonce for templates - consistent per request"""
    from flask import g
    import secrets
    
    # Generate nonce once per request and store in Flask's g
    if not hasattr(g, 'csp_nonce_value'):
        g.csp_nonce_value = secrets.token_urlsafe(16)
    
    return dict(csp_nonce=lambda: g.csp_nonce_value)

# Import models after db initialization
from models.user import create_user_model
from models.vessel import create_vessel_model
from models.cargo_tally import create_cargo_tally_model

# Create models
User = create_user_model(db)
Vessel = create_vessel_model(db)
CargoTally = create_cargo_tally_model(db)

# Login manager user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Dashboard route
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard with vessel overview - Production-grade with comprehensive error handling"""
    try:
        logger.info("🚢 Loading dashboard...")
        
        # Step 1: Perform database health check
        try:
            # Test basic database connectivity
            with db.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info("✅ Database connectivity confirmed")
        except Exception as db_health_error:
            logger.error(f"❌ Database health check failed: {db_health_error}")
            flash('Database connectivity issues detected. Please try again.', 'error')
            return render_template('dashboard.html', vessels=[], vessel_count=0)
        
        # Step 2: Ensure vessel model is created and migration is applied
        try:
            from models.vessel import create_vessel_model
            Vessel = create_vessel_model(db)
            logger.info("✅ Vessel model initialized with production compatibility")
        except Exception as model_error:
            logger.error(f"❌ Vessel model initialization failed: {model_error}")
            flash('System model initialization error. Administrators have been notified.', 'error')
            return render_template('dashboard.html', vessels=[], vessel_count=0)
        
        # Step 3: Attempt to run emergency migration if still missing columns
        try:
            from production_db_migration import run_migration_if_needed
            migration_success, migration_result = run_migration_if_needed()
            if migration_success and migration_result:
                logger.info(f"✅ Emergency migration completed: {len(migration_result)} columns added")
        except Exception as emergency_migration_error:
            logger.warning(f"⚠️  Emergency migration failed: {emergency_migration_error}")
        
        # Step 4: Query vessels with comprehensive error handling
        vessels = []
        try:
            # Force session refresh to see latest data
            db.session.expire_all()
            db.session.commit()  # Ensure any pending transactions are committed
            # Test query with minimal columns first
            vessel_count = Vessel.query.count()
            logger.info(f"📊 Found {vessel_count} vessels in database")

            # Debug: List vessel IDs and names
            vessel_ids = db.session.query(Vessel.id, Vessel.name).all()
            logger.info(f"🔍 Vessel IDs in database: {[f'ID:{v[0]} Name:{v[1]}' for v in vessel_ids]}")

            # Now attempt full query
            vessels = Vessel.query.all()
            logger.info(f"✅ Successfully queried {len(vessels)} vessels")

            # Debug: Log vessel details
            for v in vessels:
                logger.info(f"📋 Vessel: ID={v.id}, Name={v.name}, Status={v.status}, Created={getattr(v, 'created_at', 'N/A')}")
            
        except Exception as query_error:
            logger.error(f"❌ Vessel query failed: {query_error}")
            
            # Try to determine if it's a column issue
            if "UndefinedColumn" in str(query_error) or "does not exist" in str(query_error):
                logger.error("🚨 Column compatibility error detected - forcing migration")
                try:
                    # Force migration with direct SQL
                    missing_columns = [
                        'operation_start_date', 'operation_end_date', 'shipping_line',
                        'vessel_type', 'port_of_call', 'stevedoring_company', 'operation_type',
                        'berth_assignment', 'operations_manager', 'team_assignments', 'cargo_configuration'
                    ]
                    
                    with db.engine.connect() as connection:
                        # Start a transaction for all column additions
                        trans = connection.begin()
                        try:
                            for column in missing_columns:
                                try:
                                    if column.endswith('_date'):
                                        connection.execute(text(f"ALTER TABLE vessels ADD COLUMN IF NOT EXISTS {column} DATE"))
                                    elif column in ['team_assignments', 'cargo_configuration']:
                                        connection.execute(text(f"ALTER TABLE vessels ADD COLUMN IF NOT EXISTS {column} TEXT"))
                                    else:
                                        connection.execute(text(f"ALTER TABLE vessels ADD COLUMN IF NOT EXISTS {column} VARCHAR(100)"))
                                    logger.info(f"✅ Added missing column: {column}")
                                except Exception as col_error:
                                    logger.warning(f"⚠️  Could not add column {column}: {col_error}")
                                    # Continue with other columns even if one fails
                            
                            trans.commit()
                            logger.info("✅ Database migration transaction completed")
                        except Exception as trans_error:
                            trans.rollback()
                            logger.error(f"❌ Migration transaction failed, rolled back: {trans_error}")
                            raise trans_error
                    
                    # Retry query after adding columns
                    vessels = Vessel.query.all()
                    logger.info(f"✅ Query successful after emergency column addition: {len(vessels)} vessels")
                    
                except Exception as emergency_fix_error:
                    logger.error(f"❌ Emergency column fix failed: {emergency_fix_error}")
                    vessels = []
            else:
                vessels = []
        
        # Step 5: Safely serialize vessel data
        vessel_data = []
        serialization_errors = 0
        
        for vessel in vessels:
            try:
                vessel_dict = vessel.to_dict(include_progress=True)
                vessel_data.append(vessel_dict)
            except Exception as vessel_error:
                logger.warning(f"⚠️  Failed to serialize vessel {vessel.id}: {vessel_error}")
                serialization_errors += 1
                # Create minimal vessel data as fallback
                try:
                    minimal_vessel = {
                        'id': getattr(vessel, 'id', 'unknown'),
                        'name': getattr(vessel, 'name', 'Unknown Vessel'),
                        'status': getattr(vessel, 'status', 'unknown'),
                        'vessel_type': 'Auto Only',
                        'port_of_call': 'Colonel Island',
                        'progress_percentage': 0,
                        'shipping_line': 'K-line'
                    }
                    vessel_data.append(minimal_vessel)
                    logger.info(f"✅ Created fallback data for vessel {vessel.id}")
                except Exception as fallback_error:
                    logger.error(f"❌ Fallback vessel data creation failed: {fallback_error}")
                    # Skip this vessel entirely
                    continue
        
        if serialization_errors > 0:
            flash(f'Some vessel data could not be loaded ({serialization_errors} vessels affected). System is running in compatibility mode.', 'warning')
        
        logger.info(f"🎯 Dashboard loaded successfully with {len(vessel_data)} vessels")
        return render_template('dashboard.html', 
                             vessels=vessel_data,
                             vessel_count=len(vessel_data))
                             
    except Exception as e:
        logger.error(f"❌ Critical dashboard error: {e}")
        import traceback
        logger.error(f"❌ Dashboard error traceback: {traceback.format_exc()}")
        
        # Try to render dashboard with empty data instead of failing completely
        try:
            flash('Dashboard data temporarily unavailable. System is running in emergency fallback mode.', 'error')
            return render_template('dashboard.html', vessels=[], vessel_count=0)
        except Exception as template_error:
            logger.error(f"❌ Dashboard template error: {template_error}")
            # Last resort: return a simple HTML response with basic styling
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Dashboard - Stevedores Dashboard 3.0</title>
                <link rel="stylesheet" href="{url_for('static', filename='css/tailwind.min.css')}">
            </head>
            <body class="bg-gray-50 min-h-screen">
                <div class="max-w-4xl mx-auto py-8 px-4">
                    <div class="bg-white rounded-lg shadow-md p-8 text-center">
                        <h1 class="text-2xl font-bold text-red-600 mb-4">🚨 Dashboard Temporarily Unavailable</h1>
                        <p class="text-gray-600 mb-4">The system is experiencing technical difficulties and is running in emergency mode.</p>
                        <div class="bg-red-50 border border-red-200 rounded p-4 mb-4">
                            <p class="text-sm text-red-700">Technical Error: {str(e)}</p>
                        </div>
                        <p class="text-gray-600 mb-6">Please visit <code>/init-database</code> to reset the system, or contact support.</p>
                        <div class="space-x-4">
                            <a href="/init-database" class="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700">Initialize Database</a>
                            <a href="/auth/logout" class="bg-gray-600 text-white px-6 py-2 rounded-lg hover:bg-gray-700">Logout</a>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """, 503





# Service Worker route - serve from templates directory
@app.route('/service-worker.js')
def service_worker():
    """Serve the service worker JavaScript file with proper content type"""
    response = make_response(render_template('service-worker.js'))
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Cache-Control'] = 'no-cache'  # Service workers shouldn't be cached
    return response

# Manifest route for PWA
@app.route('/manifest.json')
def manifest():
    """Serve the PWA manifest file"""
    manifest_data = {
        "name": "Stevedores Dashboard 3.0",
        "short_name": "StevedoresPWA",
        "description": "Offline-first maritime operations management for reliable ship operations",
        "start_url": "/dashboard",
        "display": "standalone",
        "background_color": "#3b82f6",
        "theme_color": "#3b82f6",
        "orientation": "any",
        "scope": "/",
        "categories": ["productivity", "business", "utilities"],
        "lang": "en-US",
        "icons": [
            {
                "src": "/static/icons/icon-192x192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": "/static/icons/icon-384x384.png", 
                "sizes": "384x384",
                "type": "image/png"
            },
            {
                "src": "/static/icons/icon-512x512.png",
                "sizes": "512x512", 
                "type": "image/png"
            }
        ]
    }
    response = make_response(jsonify(manifest_data))
    response.headers['Content-Type'] = 'application/manifest+json'
    return response


if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=os.environ.get('FLASK_ENV') == 'development'
    )