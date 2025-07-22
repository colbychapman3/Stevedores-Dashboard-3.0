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
app.register_blueprint(auth_bp, url_prefix='/auth')

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