#!/usr/bin/env python3
"""
Stevedores Dashboard 3.0 - Offline-First Maritime Operations Management
Built for reliable ship operations regardless of connectivity
"""

import os
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, make_response, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'stevedores-dashboard-3.0-secret-key')

# Database configuration - SQLite for development, PostgreSQL for production
database_url = os.environ.get('DATABASE_URL', 'sqlite:///stevedores.db')

# Fix Render's postgres:// to postgresql:// if needed
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Security configurations
app.config['WTF_CSRF_TIME_LIMIT'] = None
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Initialize extensions
db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)

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
from models.user import create_user_model
from models.vessel import create_vessel_model  
from models.cargo_tally import create_cargo_tally_model

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
    """Main stevedoring dashboard"""
    vessels = Vessel.query.all()
    return render_template('dashboard.html', vessels=vessels)


# PWA routes
@app.route('/manifest.json')
def manifest():
    """PWA Web App Manifest"""
    manifest_data = {
        "name": "Stevedores Dashboard 3.0",
        "short_name": "StevedoresDash",
        "description": "Offline-capable maritime stevedoring operations management",
        "start_url": "/dashboard",
        "display": "standalone",
        "background_color": "#1e40af",
        "theme_color": "#3b82f6",
        "orientation": "portrait-primary",
        "icons": [
            {
                "src": "/static/icons/icon-192x192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": "/static/icons/icon-512x512.png",
                "sizes": "512x512", 
                "type": "image/png",
                "purpose": "any maskable"
            }
        ],
        "categories": ["productivity", "business"],
        "display_override": ["standalone", "minimal-ui"],
        "prefer_related_applications": False
    }
    
    response = make_response(jsonify(manifest_data))
    response.headers['Content-Type'] = 'application/manifest+json'
    response.headers['Cache-Control'] = 'public, max-age=3600'
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

# Health check endpoint
@app.route('/health')
def health_check():
    """Basic health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '3.0.0',
        'offline_ready': True
    }), 200

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
@app.route('/vessel/<int:vessel_id>')
@login_required
def vessel_details(vessel_id):
    """Individual vessel details page with cargo tally widgets"""
    try:
        vessel = Vessel.query.get_or_404(vessel_id)
        recent_tallies = CargoTally.query.filter_by(vessel_id=vessel_id).order_by(CargoTally.timestamp.desc()).limit(5).all()
        
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
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(wizard_bp, url_prefix='/wizard')
app.register_blueprint(document_bp, url_prefix='/document')

# Exempt document processing routes from CSRF for offline functionality
csrf.exempt(document_bp)

# Database initialization
def init_database():
    """Initialize database tables and create sample data if needed"""
    try:
        with app.app_context():
            db.create_all()
            
            # Create default admin user if not exists
            if not User.query.filter_by(email='admin@stevedores.com').first():
                admin = User(
                    email='admin@stevedores.com',
                    username='admin',
                    password_hash=generate_password_hash('admin123'),
                    role='manager',
                    is_active=True
                )
                db.session.add(admin)
            
            # Create default stevedore user
            if not User.query.filter_by(email='stevedore@stevedores.com').first():
                stevedore = User(
                    email='stevedore@stevedores.com',
                    username='stevedore',
                    password_hash=generate_password_hash('stevedore123'),
                    role='stevedore',
                    is_active=True
                )
                db.session.add(stevedore)
            
            db.session.commit()
            logger.info("Database initialized successfully!")
            return True
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False

# CLI commands
@app.cli.command()
def init_db():
    """Initialize the database with tables and sample data"""
    if init_database():
        print("Database initialized successfully!")
    else:
        print("Database initialization failed!")

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=os.environ.get('FLASK_ENV') == 'development'
    )