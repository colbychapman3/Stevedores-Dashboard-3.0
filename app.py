#!/usr/bin/env python3
"""
Stevedores Dashboard 3.0 - Offline-First Maritime Operations Management
Built for reliable ship operations regardless of connectivity
Python 3.12/3.13 compatible
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, make_response, flash, has_app_context
from flask_sqlalchemy import SQLAlchemy
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
DEPLOYMENT_VERSION = "3.0.7-DB-DIAGNOSTICS-20250806"
print(f"🚢 STEVEDORES DASHBOARD {DEPLOYMENT_VERSION} STARTING...")

# Early logging setup for configuration debugging with enhanced formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [APP] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
config_logger = logging.getLogger(__name__)
config_logger.info("🏗️  App.py initialization starting...")
config_logger.info(f"🐍 Python version: {sys.version}")
config_logger.info(f"🌍 Working directory: {os.getcwd()}")

# Configuration - Standardized precedence: env -> render_config -> production_config -> fallback
config_name = os.environ.get('FLASK_CONFIG', 'render')
config_loaded = False

config_logger.info(f"🔧 Target configuration: {config_name}")
config_logger.info(f"🔐 SECRET_KEY environment: {'SET' if os.environ.get('SECRET_KEY') else 'NOT SET'}")
config_logger.info(f"🗄️  DATABASE_URL environment: {'SET' if os.environ.get('DATABASE_URL') else 'NOT SET'}")

# Try render_config first (preferred for Render deployment)
if not config_loaded:
    try:
        config_logger.info("📋 Attempting to load render_config...")
        from render_config import config
        config_logger.info(f"📋 render_config imported, available configs: {list(config.keys())}")
        
        if config_name in config:
            config_logger.info(f"🔧 Loading config class: {config_name}")
            app.config.from_object(config[config_name])
            config[config_name].init_app(app)
            config_loaded = True
            config_logger.info(f"✅ Loaded render_config: {config_name}")
        else:
            config_logger.warning(f"⚠️  Config '{config_name}' not found, trying 'render' fallback")
            app.config.from_object(config['render'])
            config['render'].init_app(app)
            config_loaded = True
            config_logger.info(f"✅ Loaded render_config: render (fallback)")
    except ImportError as e:
        config_logger.info(f"⚠️  render_config not available: {e}")
    except Exception as e:
        config_logger.error(f"❌ Error loading render_config: {e}")

# Fallback to production_config
if not config_loaded:
    try:
        config_logger.info("📋 Attempting to load production_config...")
        from production_config import config
        fallback_name = 'production' if config_name in ['render', 'production'] else config_name
        config_logger.info(f"📋 production_config imported, available configs: {list(config.keys())}")
        config_logger.info(f"🔧 Using fallback config name: {fallback_name}")
        
        if fallback_name in config:
            config_logger.info(f"🔧 Loading config class: {fallback_name}")
            app.config.from_object(config[fallback_name])
            config[fallback_name].init_app(app)
            config_loaded = True
            config_logger.info(f"✅ Loaded production_config: {fallback_name}")
        else:
            config_logger.error(f"❌ Config '{fallback_name}' not found in production_config")
            config_logger.info(f"💡 Available configs: {list(config.keys())}")
    except ImportError as e:
        config_logger.info(f"⚠️  production_config not available: {e}")
    except Exception as e:
        config_logger.error(f"❌ Error loading production_config: {e}")

# Final fallback to basic configuration
if not config_loaded:
    config_logger.warning("⚠️  No configuration file loaded, using environment-based fallback")
    
    # SECURITY FIX: Remove hardcoded SECRET_KEY fallback - require environment variable
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        config_logger.error("❌ CRITICAL: SECRET_KEY environment variable is required")
        raise ValueError("SECRET_KEY environment variable is required for security. Set SECRET_KEY in your environment.")
    
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///stevedores.db')
    debug_mode = os.environ.get('FLASK_ENV', 'production') == 'development'
    
    config_logger.info(f"🔐 Using SECRET_KEY from environment (length: {len(secret_key)})")
    config_logger.info(f"🗄️  Using DATABASE_URL: {database_url.split('://')[0]}://***" if '://' in database_url else database_url)
    config_logger.info(f"🐛 Debug mode: {debug_mode}")
    
    app.config.update({
        'SECRET_KEY': secret_key,
        'SQLALCHEMY_DATABASE_URI': database_url,
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'DEBUG': debug_mode
    })
    config_loaded = True
    config_logger.info("✅ Loaded basic fallback configuration with secure SECRET_KEY")

# Validate final configuration
if config_loaded:
    config_logger.info("🔍 Validating final configuration...")
    
    # Validate SECRET_KEY
    final_secret = app.config.get('SECRET_KEY')
    if not final_secret:
        config_logger.error("❌ CRITICAL: No SECRET_KEY in final configuration")
        raise ValueError("SECRET_KEY is missing from final configuration")
    else:
        config_logger.info(f"✅ SECRET_KEY validated (length: {len(final_secret)})")
    
    # Validate DATABASE_URI
    final_db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
    if not final_db_uri:
        config_logger.error("❌ CRITICAL: No DATABASE_URI in final configuration")
        raise ValueError("SQLALCHEMY_DATABASE_URI is missing from final configuration")
    else:
        config_logger.info(f"✅ DATABASE_URI validated: {final_db_uri.split('://')[0]}://***" if '://' in final_db_uri else "✅ DATABASE_URI validated")
    
    config_logger.info("✅ Configuration validation completed successfully")
else:
    config_logger.error("❌ CRITICAL: No configuration was loaded")
    raise RuntimeError("Failed to load any configuration - deployment cannot continue")

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

# Initialize Security Manager for maritime operations with enhanced error handling
config_logger.info("🔒 Initializing security systems...")

try:
    config_logger.info("🔒 Loading security manager...")
    from utils.security_manager import init_security_manager
    security_manager = init_security_manager(app)
    config_logger.info("✅ Security manager initialized successfully")
except Exception as e:
    config_logger.error(f"❌ Failed to initialize security manager: {e}")
    # Continue without security manager for degraded mode
    security_manager = None

# Initialize Phase 2: API Security Layer with detailed error handling
config_logger.info("🔐 Initializing API security layer...")

try:
    config_logger.info("🔐 Loading JWT authentication...")
    from utils.jwt_auth import init_jwt_auth
    jwt_manager = init_jwt_auth(app)
    config_logger.info("✅ JWT authentication initialized successfully")
except Exception as e:
    config_logger.error(f"❌ Failed to initialize JWT authentication: {e}")
    jwt_manager = None

try:
    config_logger.info("📋 Loading audit logger...")
    from utils.audit_logger import init_audit_logger
    audit_logger = init_audit_logger(app)
    config_logger.info("✅ Audit logger initialized successfully")
except Exception as e:
    config_logger.error(f"❌ Failed to initialize audit logger: {e}")
    audit_logger = None

try:
    config_logger.info("🛡️  Loading API middleware...")
    from utils.api_middleware import init_api_middleware
    api_middleware = init_api_middleware(app)
    config_logger.info("✅ API middleware initialized successfully")
except Exception as e:
    config_logger.error(f"❌ Failed to initialize API middleware: {e}")
    api_middleware = None

config_logger.info("✅ Security systems initialization completed")

# Initialize database retry logic for production stability
# Import and initialize after db is created to avoid circular imports
db_retry_manager = None

def init_db_retry():
    """Initialize database retry logic after app and db are set up"""
    global db_retry_manager
    try:
        from utils.database_retry import DatabaseConnectionManager
        db_retry_manager = DatabaseConnectionManager()
        db_retry_manager.db = db
        db_retry_manager.app = app
        db_retry_manager._configure_engine_options()
        app.logger.info("Database retry logic initialized for maritime operations")
        return db_retry_manager
    except Exception as e:
        app.logger.error(f"Failed to initialize database retry logic: {e}")
        return None

# Initialize after imports
db_retry_manager = init_db_retry()

# Import robust database initialization after db is created
from utils.database_init import init_database_with_diagnostics, safe_init_database, get_database_status

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

# Import models after db initialization using factory functions with enhanced logging
config_logger.info("📦 Loading model factory functions...")

try:
    config_logger.info("📦 Importing user model factory...")
    from models.user import create_user_model
    config_logger.info("✅ User model factory imported successfully")
except Exception as e:
    config_logger.error(f"❌ Failed to import user model factory: {e}")
    raise

try:
    config_logger.info("📦 Importing vessel model factory...")
    from models.vessel import create_vessel_model
    config_logger.info("✅ Vessel model factory imported successfully")
except Exception as e:
    config_logger.error(f"❌ Failed to import vessel model factory: {e}")
    raise

try:
    config_logger.info("📦 Importing cargo tally model factory...")
    from models.cargo_tally import create_cargo_tally_model
    config_logger.info("✅ Cargo tally model factory imported successfully")
except Exception as e:
    config_logger.error(f"❌ Failed to import cargo tally model factory: {e}")
    raise

config_logger.info("📦 All model factories imported successfully")

# Create model classes with detailed logging
config_logger.info("🏗️  Creating model classes...")

try:
    config_logger.info("🏗️  Creating User model...")
    User = create_user_model(db)
    config_logger.info("✅ User model created successfully")
except Exception as e:
    config_logger.error(f"❌ Failed to create User model: {e}")
    raise

try:
    config_logger.info("🏗️  Creating Vessel model...")
    Vessel = create_vessel_model(db)
    config_logger.info("✅ Vessel model created successfully")
except Exception as e:
    config_logger.error(f"❌ Failed to create Vessel model: {e}")
    raise

try:
    config_logger.info("🏗️  Creating CargoTally model...")
    CargoTally = create_cargo_tally_model(db)
    config_logger.info("✅ CargoTally model created successfully")
except Exception as e:
    config_logger.error(f"❌ Failed to create CargoTally model: {e}")
    raise

config_logger.info("✅ All model classes created successfully")

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

# Enhanced health check endpoint with comprehensive database diagnostics
@app.route('/health')
def health_check():
    """Comprehensive health check including database diagnostics and retry logic"""
    try:
        # Get database status with our enhanced diagnostics
        db_status = get_database_status(app, db)
        
        # Also get legacy database retry health if available
        retry_health = {'status': 'unknown', 'available': False}
        try:
            from utils.database_retry import database_health_check
            retry_health = database_health_check()
            retry_health['available'] = True
        except ImportError:
            logger.debug("Database retry health check not available")
        
        overall_status = 'healthy'
        if not db_status['healthy']:
            overall_status = 'degraded' if db_status['status'] in ['degraded', 'warnings'] else 'unhealthy'
        
        return jsonify({
            'status': overall_status,
            'timestamp': datetime.utcnow().isoformat(),
            'version': DEPLOYMENT_VERSION,
            'offline_ready': True,
            'database': {
                'enhanced_diagnostics': db_status,
                'retry_logic': retry_health
            },
            'features': {
                'database_diagnostics': True,
                'database_retry': retry_health['available'],
                'csrf_protection': True,
                'sqlalchemy_cache': True,
                'service_worker_auth': True,
                'comprehensive_error_reporting': True
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': DEPLOYMENT_VERSION,
            'error': str(e),
            'message': 'Health check system failure - check application logs'
        }), 503

# Additional comprehensive health check endpoints
try:
    config_logger.info("🏥 Adding comprehensive health check endpoints...")
    from enhanced_health_check import comprehensive_health_check
    
    @app.route('/health/detailed')
    def detailed_health_check():
        """Detailed health check with full system information"""
        try:
            health_report = comprehensive_health_check()
            return jsonify(health_report), 200
        except Exception as e:
            logger.error(f"Detailed health check failed: {e}")
            return jsonify({
                'overall_status': 'error',
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
                'version': DEPLOYMENT_VERSION
            }), 503
    
    @app.route('/health/quick')
    def quick_health_check():
        """Quick health check for basic status"""
        try:
            # Just check database connectivity
            from enhanced_health_check import check_database_health
            database_health = check_database_health()
            
            return jsonify({
                'status': 'healthy' if database_health.get('status') == 'healthy' else 'unhealthy',
                'timestamp': datetime.utcnow().isoformat(),
                'database': database_health.get('status'),
                'version': DEPLOYMENT_VERSION
            }), 200 if database_health.get('status') == 'healthy' else 503
        except Exception as e:
            return jsonify({
                'status': 'error',
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }), 503
    
    config_logger.info("✅ Comprehensive health check endpoints added")
    
except ImportError as e:
    config_logger.warning(f"⚠️  Comprehensive health check not available: {e}")
    config_logger.warning("💡 Install psutil for enhanced system monitoring: pip install psutil")
except Exception as e:
    config_logger.error(f"❌ Failed to add comprehensive health check endpoints: {e}")

# Robust database initialization function for production
def init_database():
    """Initialize database with comprehensive diagnostics and error handling
    
    This function replaces the previous duplicate implementations with a single,
    robust version that provides detailed error diagnostics for production debugging
    and prevents worker crashes.
    
    Returns:
        bool: True if initialization successful, False otherwise
    """
    logger.info("🚀 Starting robust database initialization...")
    
    try:
        # Use our comprehensive diagnostics-enabled initialization
        success = safe_init_database(app, db)
        
        if success:
            logger.info("✅ Database initialization completed successfully")
        else:
            logger.error("❌ Database initialization failed - check diagnostic logs above")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Critical database initialization error: {e}")
        # Don't crash the worker - return False to indicate failure
        return False

# Enhanced database initialization endpoint with diagnostics
@app.route('/init-database')
def init_database_endpoint():
    """Initialize database with comprehensive diagnostics - HTTP endpoint"""
    try:
        logger.info("🔧 Manual database initialization requested via HTTP endpoint")
        
        # Use our comprehensive initialization with diagnostics
        success, diagnostic_data = init_database_with_diagnostics(app, db)
        
        if success:
            summary = diagnostic_data.get('summary', {})
            return jsonify({
                'success': True,
                'message': 'Database initialized successfully with comprehensive diagnostics',
                'login_credentials': 'demo@maritime.test / demo123',
                'diagnostics': {
                    'checks_passed': summary.get('checks_passed', 0),
                    'total_checks': summary.get('total_checks', 0),
                    'success_rate': summary.get('success_rate', 0)
                },
                'timestamp': diagnostic_data.get('timestamp')
            })
        else:
            return jsonify({
                'error': 'Database initialization failed',
                'message': 'Check server logs for detailed diagnostic information',
                'diagnostics_available': True
            }), 500
        
    except Exception as e:
        logger.error(f"Database initialization endpoint error: {e}")
        return jsonify({
            'error': f'Database initialization failed: {str(e)}',
            'message': 'Check server logs for detailed error information',
            'timestamp': datetime.utcnow().isoformat()
        }), 500

# Database diagnostics endpoint for production debugging
@app.route('/diagnostics/database')
def database_diagnostics_endpoint():
    """Run comprehensive database diagnostics - production debugging endpoint"""
    try:
        logger.info("🔍 Database diagnostics requested via HTTP endpoint")
        
        # Get database status with full diagnostics
        db_status = get_database_status(app, db)
        
        return jsonify({
            'database_diagnostics': db_status,
            'timestamp': datetime.utcnow().isoformat(),
            'version': DEPLOYMENT_VERSION,
            'endpoint': 'database_diagnostics'
        })
        
    except Exception as e:
        logger.error(f"Database diagnostics endpoint error: {e}")
        return jsonify({
            'error': f'Database diagnostics failed: {str(e)}',
            'message': 'Check server logs for detailed error information',
            'timestamp': datetime.utcnow().isoformat()
        }), 500

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

# Exempt specific routes from CSRF for offline functionality
# NOTE: Auth routes should NOT be exempted from CSRF for security
csrf.exempt(document_bp)
csrf.exempt(sync_bp) 
csrf.exempt(offline_dashboard_bp)

# SECURITY FIX: Remove CSRF exemption from auth routes to prevent CSRF attacks
# csrf.exempt(auth_bp)  # REMOVED - auth routes should be CSRF protected





if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=os.environ.get('FLASK_ENV') == 'development'
    )