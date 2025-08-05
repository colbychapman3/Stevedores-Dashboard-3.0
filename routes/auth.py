"""
Authentication routes for stevedoring operations
Simple login/logout functionality
"""

from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/session-status')
def session_status():
    """API endpoint to check session validity - returns JSON"""
    return jsonify({
        'authenticated': current_user.is_authenticated,
        'user_id': current_user.id if current_user.is_authenticated else None,
        'timestamp': datetime.utcnow().isoformat()
    })

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
        print(f"[DEBUG] Login attempt started")
        db, User = get_db_and_models()
        print(f"[DEBUG] Got database and User model")
        
        if request.is_json:
            data = request.get_json()
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')
            print(f"[DEBUG] JSON request - email: {email}")
        else:
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            print(f"[DEBUG] Form request - email: {email}")
        
        # Validate input
        if not email or not password:
            print(f"[DEBUG] Missing email or password")
            if request.is_json:
                return jsonify({'error': 'Email and password are required'}), 400
            flash('Email and password are required', 'error')
            return render_template('auth/login.html')
        
        # Find user
        print(f"[DEBUG] Looking up user with email: {email}")
        user = User.query.filter_by(email=email).first()
        print(f"[DEBUG] User found: {user is not None}")
        
        if user:
            print(f"[DEBUG] User exists - is_active: {user.is_active}")
            password_valid = user.check_password(password)
            print(f"[DEBUG] Password check result: {password_valid}")
            
            if password_valid and user.is_active:
                print(f"[DEBUG] Authentication successful, logging in user")
                login_user(user, remember=True)
                user.update_last_login()
                print(f"[DEBUG] User logged in successfully")
                
                if request.is_json:
                    return jsonify({
                        'success': True,
                        'user': user.to_dict(),
                        'redirect_url': url_for('dashboard')
                    })
                return redirect(url_for('dashboard'))
            else:
                print(f"[DEBUG] Authentication failed - password_valid: {password_valid}, is_active: {user.is_active}")
        else:
            print(f"[DEBUG] No user found with email: {email}")
        
        error_msg = 'Invalid email or password'
        if request.is_json:
            return jsonify({'error': error_msg}), 401
        flash(error_msg, 'error')
        return render_template('auth/login.html')
            
    except Exception as e:
        print(f"[DEBUG] Exception during login: {str(e)}")
        print(f"[DEBUG] Exception type: {type(e).__name__}")
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
        
        error_msg = f'Login failed: {str(e)}'
        if request.is_json:
            return jsonify({'error': error_msg, 'debug': str(e)}), 500
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

# SECURITY FIX: Debug endpoint removed for production security
# Original debug endpoint has been removed to prevent information disclosure
# For debugging, use proper logging and monitoring tools instead