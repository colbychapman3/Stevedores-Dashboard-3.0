"""
Authentication routes for stevedoring operations
Simple login/logout functionality
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

auth_bp = Blueprint('auth', __name__)

def get_db_and_models():
    """Get database and models - import here to avoid circular imports"""
    from app import db
    from models.user import create_user_model
    User = create_user_model(db)
    return db, User

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login endpoint"""
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return render_template('auth/login.html')
    
    # Handle POST request
    try:
        db, User = get_db_and_models()
        
        if request.is_json:
            data = request.get_json()
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')
        else:
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
        
        # Validate input
        if not email or not password:
            if request.is_json:
                return jsonify({'error': 'Email and password are required'}), 400
            flash('Email and password are required', 'error')
            return render_template('auth/login.html')
        
        # Find user
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=True)
            user.update_last_login()
            
            if request.is_json:
                return jsonify({
                    'success': True,
                    'user': user.to_dict(),
                    'redirect_url': url_for('dashboard')
                })
            return redirect(url_for('dashboard'))
        else:
            error_msg = 'Invalid email or password'
            if request.is_json:
                return jsonify({'error': error_msg}), 401
            flash(error_msg, 'error')
            return render_template('auth/login.html')
            
    except Exception as e:
        error_msg = 'Login failed. Please try again.'
        if request.is_json:
            return jsonify({'error': error_msg}), 500
        flash(error_msg, 'error')
        return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout endpoint"""
    logout_user()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('index'))

@auth_bp.route('/api/user')
@login_required  
def current_user_info():
    """Get current user information (API endpoint)"""
    return jsonify({
        'user': current_user.to_dict(),
        'authenticated': True
    })