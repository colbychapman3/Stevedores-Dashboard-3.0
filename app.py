#!/usr/bin/env python3
"""
Stevedores Dashboard 3.0 - Offline-First Maritime Operations Management
Built for reliable ship operations regardless of connectivity
"""

import os
import logging
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, make_response, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

# Initialize Flask app
app = Flask(__name__)

# FORCE CACHE REFRESH: Production build version identifier
DEPLOYMENT_VERSION = "3.0.3-AUTH-DEBUG-20250805"
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

# PRODUCTION FIXES: Initialize production-ready components
if not app.config.get('TESTING', False):
    try:
        # Initialize Redis client with resilience patterns
        from utils.redis_client import get_redis_client
        redis_client = get_redis_client(app.config.get('REDIS_URL'))
        logger.info("✅ Redis client with circuit breaker initialized")
        
        # Initialize security middleware (Flask-Talisman)
        from utils.security_middleware import init_security_middleware
        security_middleware = init_security_middleware(app)
        logger.info("✅ Security middleware (Talisman) initialized")
        
        # Initialize rate limiter with fallback
        from utils.rate_limiter import init_rate_limiter
        rate_limiter = init_rate_limiter(app)
        logger.info("✅ Rate limiter with fallback initialized")
        
        # Initialize enhanced memory monitor with config-driven settings
        from utils.memory_monitor import init_memory_monitor
        memory_warning = app.config.get('MEMORY_WARNING_THRESHOLD', 75.0)
        memory_critical = app.config.get('MEMORY_CRITICAL_THRESHOLD', 85.0)
        
        memory_monitor = init_memory_monitor(
            warning_threshold=memory_warning,
            critical_threshold=memory_critical
        )
        logger.info(f"✅ Enhanced memory monitor initialized (Warning: {memory_warning}%, Critical: {memory_critical}%)")
        
        # Initialize memory leak prevention middleware
        from utils.memory_middleware import init_memory_middleware
        memory_middleware = init_memory_middleware(app)
        logger.info("✅ Memory leak prevention middleware initialized")
        
        # Initialize comprehensive health monitor
        from utils.health_monitor import init_health_monitor
        health_monitor = init_health_monitor()
        logger.info("✅ Health monitor with all checks initialized")
        
        # Initialize production monitoring with memory integration
        from production_monitoring import MetricCollector
        production_monitor = MetricCollector()
        production_monitor.register_memory_monitor(memory_monitor)
        
        # Start periodic memory metrics collection
        import threading
        def periodic_memory_collection():
            while True:
                try:
                    production_monitor.collect_memory_metrics()
                    time.sleep(30)  # Collect metrics every 30 seconds
                except Exception as e:
                    logger.error(f"Periodic memory collection error: {e}")
                    time.sleep(60)  # Longer sleep on error
        
        memory_collection_thread = threading.Thread(target=periodic_memory_collection, daemon=True)
        memory_collection_thread.start()
        
        logger.info("✅ Production monitoring with memory integration initialized")
        
    except Exception as e:
        logger.error(f"❌ Production component initialization error: {e}")
        # Don't fail startup, but log the error

# Exempt API routes from CSRF protection for offline functionality
@csrf.exempt
def csrf_exempt_api(func):
    """Decorator to exempt API routes from CSRF"""
    return func
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = app.logger

# Import models after db initialization using factory functions
# DEBUGGING: Force production cache refresh - these are the ONLY model imports
print("🔍 DEBUG: Loading models from factory functions...")
from models.user import create_user_model
from models.vessel import create_vessel_model  
from models.cargo_tally import create_cargo_tally_model
print("🔍 DEBUG: Model imports completed successfully")

# Create model classes
User = create_user_model(db)
Vessel = create_vessel_model(db)
CargoTally = create_cargo_tally_model(db)

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Main routes
@app.route('/')
def index():
    """Main landing page - redirect to dashboard if authenticated"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    """Main stevedoring dashboard with offline support"""
    try:
        # Try to get vessels from database
        vessels = Vessel.query.all()
        
        # Cache vessel data for offline use
        from utils.offline_data_manager import OfflineDataManager
        offline_manager = OfflineDataManager()
        vessel_list = [vessel.to_dict(include_progress=True) for vessel in vessels]
        offline_manager.cache_vessel_data(vessel_list, "server")
        
        return render_template('dashboard_offline.html', vessels=vessels)
        
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        
        # Fallback to offline-only template
        return render_template('dashboard_offline.html', vessels=[])

@app.route('/cargo-tally')
@login_required
def cargo_tally():
    """Cargo tally management page"""
    return render_template('cargo_tally.html')

@app.route('/reports')
@login_required
def reports():
    """Reports and analytics page"""
    return render_template('reports.html')

# PWA routes
@app.route('/manifest.json')
def manifest():
    """Advanced PWA Web App Manifest with comprehensive offline support"""
    manifest_data = {
        "name": "Stevedores Dashboard 3.0 - Maritime Operations",
        "short_name": "StevedoresPWA",
        "description": "Advanced offline-capable maritime stevedoring operations management system optimized for ship operations",
        "start_url": "/dashboard?pwa=true",
        "display": "standalone",
        "background_color": "#1e40af",
        "theme_color": "#3b82f6",
        "orientation": "portrait-primary",
        "scope": "/",
        
        # Advanced PWA icons with multiple purposes
        "icons": [
            {
                "src": "/static/icons/icon-72x72.png",
                "sizes": "72x72",
                "type": "image/png",
                "purpose": "any"
            },
            {
                "src": "/static/icons/icon-96x96.png",
                "sizes": "96x96",
                "type": "image/png",
                "purpose": "any"
            },
            {
                "src": "/static/icons/icon-128x128.png",
                "sizes": "128x128",
                "type": "image/png",
                "purpose": "any"
            },
            {
                "src": "/static/icons/icon-144x144.png",
                "sizes": "144x144",
                "type": "image/png",
                "purpose": "any"
            },
            {
                "src": "/static/icons/icon-152x152.png",
                "sizes": "152x152",
                "type": "image/png",
                "purpose": "any"
            },
            {
                "src": "/static/icons/icon-192x192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": "/static/icons/icon-384x384.png",
                "sizes": "384x384",
                "type": "image/png",
                "purpose": "any"
            },
            {
                "src": "/static/icons/icon-512x512.png",
                "sizes": "512x512", 
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": "/static/icons/maskable-icon-192x192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "maskable"
            },
            {
                "src": "/static/icons/maskable-icon-512x512.png",
                "sizes": "512x512",
                "type": "image/png", 
                "purpose": "maskable"
            }
        ],
        
        # Advanced PWA features
        "categories": ["productivity", "business", "navigation", "utilities"],
        "display_override": ["standalone", "minimal-ui", "browser"],
        "prefer_related_applications": False,
        "edge_side_panel": {
            "preferred_width": 480
        },
        
        # Maritime-specific shortcuts
        "shortcuts": [
            {
                "name": "New Vessel",
                "short_name": "New Vessel",
                "description": "Create a new vessel operation",
                "url": "/wizard?shortcut=true",
                "icons": [
                    {
                        "src": "/static/icons/shortcut-vessel.png",
                        "sizes": "96x96",
                        "type": "image/png"
                    }
                ]
            },
            {
                "name": "Cargo Tally",
                "short_name": "Cargo Tally",
                "description": "Quick cargo tally input",
                "url": "/dashboard?view=tally",
                "icons": [
                    {
                        "src": "/static/icons/shortcut-cargo.png",
                        "sizes": "96x96",
                        "type": "image/png"
                    }
                ]
            },
            {
                "name": "Offline Dashboard",
                "short_name": "Offline",
                "description": "Access offline dashboard",
                "url": "/dashboard?offline=true",
                "icons": [
                    {
                        "src": "/static/icons/shortcut-offline.png",
                        "sizes": "96x96",
                        "type": "image/png"
                    }
                ]
            }
        ],
        
        # Protocol handlers for maritime operations
        "protocol_handlers": [
            {
                "protocol": "web+stevedores",
                "url": "/handle-protocol?type=%s"
            }
        ],
        
        # File handlers for maritime documents
        "file_handlers": [
            {
                "action": "/document/upload",
                "accept": {
                    "application/pdf": [".pdf"],
                    "text/plain": [".txt"],
                    "text/csv": [".csv"],
                    "application/vnd.ms-excel": [".xlsx", ".xls"]
                }
            }
        ],
        
        # Advanced launch configuration
        "launch_handler": {
            "client_mode": "focus-existing"
        },
        
        # Manifest ID for update detection
        "id": "/manifest.json",
        
        # Enhanced metadata
        "lang": "en-US",
        "dir": "ltr",
        "iarc_rating_id": "none",
        
        # Maritime-specific metadata
        "related_applications": [],
        "prefer_related_applications": False,
        
        # Advanced PWA capabilities
        "handle_links": "preferred",
        "capture_links": "new-client"
    }
    
    response = make_response(jsonify(manifest_data))
    response.headers['Content-Type'] = 'application/manifest+json'
    response.headers['Cache-Control'] = 'public, max-age=86400'  # 24 hours cache
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route('/service-worker.js')
def service_worker():
    """Service worker for offline capabilities"""
    response = make_response(render_template('service-worker.js'))
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

@app.route('/offline')
def offline():
    """Offline page when no connectivity"""
    return render_template('offline.html')

# ENHANCED Health check endpoint with dependency validation
@app.route('/health')
def health_check():
    """Comprehensive production health check with dependency validation"""
    try:
        from utils.health_monitor import get_health_monitor
        from utils.security_middleware import security_health_check
        
        health_monitor = get_health_monitor()
        
        # Run all health checks
        result = health_monitor.run_all_checks(use_cache=True)
        
        # Add security middleware status
        security_status = security_health_check()
        
        # Add application-specific info
        result.update({
            'offline_ready': True,
            'deployment_version': DEPLOYMENT_VERSION,
            'security_status': security_status
        })
        
        # Determine HTTP status based on health
        if result['status'] == 'healthy':
            status_code = 200
        elif result['status'] == 'degraded':
            status_code = 200  # Still operational
        else:
            status_code = 503  # Service unavailable
        
        return jsonify(result), status_code
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            'status': 'error',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e),
            'version': '3.0.0'
        }), 500

@app.route('/health/quick')
def quick_health_check():
    """Quick health check for load balancers (cached)"""
    try:
        from utils.health_monitor import get_health_monitor
        health_monitor = get_health_monitor()
        result = health_monitor.get_quick_status()
        
        status_code = 200 if result.get('status') in ['healthy', 'degraded'] else 503
        return jsonify(result), status_code
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }), 500

# Security monitoring endpoints
@app.route('/security/status')
@login_required
def security_status():
    """Security status endpoint for administrators"""
    try:
        from utils.security_middleware import security_health_check
        status = security_health_check()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Security status error: {e}")
        return jsonify({'error': 'Failed to get security status'}), 500

@app.route('/security/violations')
@login_required
def security_violations():
    """Security violation report for administrators"""
    try:
        from utils.security_middleware import security_violation_report
        limit = min(int(request.args.get('limit', 50)), 1000)  # Max 1000 violations
        report = security_violation_report(limit)
        return jsonify(report)
    except Exception as e:
        logger.error(f"Security violations error: {e}")
        return jsonify({'error': 'Failed to get violation report'}), 500

# Database initialization function (used by wsgi.py)
def init_database():
    """Initialize database and create demo users - used by production startup"""
    try:
        # Create all tables
        db.create_all()
        logger.info("Database tables created successfully")
        
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
            logger.info("Demo user created: demo@maritime.test")
        
        db.session.commit()
        logger.info(f"Database initialization completed. Users created: {users_created}")
        return True
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
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
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(wizard_bp, url_prefix='/wizard')
app.register_blueprint(document_bp, url_prefix='/document')
app.register_blueprint(sync_bp, url_prefix='/sync')
app.register_blueprint(offline_dashboard_bp, url_prefix='/offline-dashboard')

# Register memory monitoring routes
from routes.memory_monitoring import register_memory_routes
register_memory_routes(app)
logger.info("✅ Memory monitoring routes registered")

# CRITICAL FIX: Exempt health check endpoints from rate limiting
# These endpoints must ALWAYS work for load balancers and monitoring
if not app.config.get('TESTING', False):
    try:
        from utils.rate_limiter import get_rate_limiter
        rate_limiter = get_rate_limiter()
        if rate_limiter and rate_limiter.limiter:
            # Exempt health and monitoring endpoints
            rate_limiter.limiter.exempt(health_check)
            rate_limiter.limiter.exempt(quick_health_check) 
            rate_limiter.limiter.exempt(security_status)
            logger.info("✅ Health check endpoints exempted from rate limiting")
    except Exception as e:
        logger.warning(f"⚠️  Failed to exempt health endpoints from rate limiting: {e}")

# Exempt document processing, sync, offline dashboard, and auth routes from CSRF for offline functionality
csrf.exempt(document_bp)
csrf.exempt(auth_bp)
csrf.exempt(sync_bp)
csrf.exempt(offline_dashboard_bp)



# Database initialization function (was missing - causing startup failure)
def init_database():
    """Initialize database and create demo users for production deployment
    
    This function was missing but called by wsgi.py and test files,
    causing ImportError on production startup.
    """
    try:
        with app.app_context():
            # Create all tables
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Create demo user if not exists
            if not User.query.filter_by(email='demo@maritime.test').first():
                demo_user = User(
                    email='demo@maritime.test',
                    username='demo_user',
                    password_hash=generate_password_hash('demo123'),
                    is_active=True
                )
                db.session.add(demo_user)
                db.session.commit()
                logger.info("Demo user created: demo@maritime.test / demo123")
            else:
                logger.info("Demo user already exists")
            
            return True
            
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False


if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=os.environ.get('FLASK_ENV') == 'development'
    )