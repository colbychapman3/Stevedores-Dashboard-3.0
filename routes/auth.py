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

from app import InputValidator, limiter

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """User login endpoint"""
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return render_template('auth/login.html')

    # Handle POST request
    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        validator = InputValidator(data)
        validator.validate_email('email')
        validator.validate_password('password')

        if validator.errors:
            if request.is_json:
                return jsonify({'errors': validator.errors}), 400
            for error in validator.errors.values():
                flash(error, 'error')
            return render_template('auth/login.html')

        sanitized_data = validator.get_sanitized_data()
        email = sanitized_data.get('email').strip().lower()
        password = sanitized_data.get('password')

        db, User = get_db_and_models()
        
        # Find user
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=True)
            user.update_last_login()
            session['ip_address'] = request.remote_addr
            session['user_agent'] = request.headers.get('User-Agent')

            if request.is_json:
                return jsonify({
                    'success': True,
                    'user': user.to_dict(),
                    'redirect_url': url_for('dashboard')
                })
            return redirect(url_for('dashboard'))

        error_msg = 'Invalid email or password'
        if request.is_json:
            return jsonify({'error': error_msg}), 401
        flash(error_msg, 'error')
        return render_template('auth/login.html')

    except Exception as e:
        error_msg = f'Login failed: {str(e)}'
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