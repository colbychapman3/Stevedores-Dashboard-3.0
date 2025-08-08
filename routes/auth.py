"""
Authentication routes for stevedoring operations
Simple login/logout functionality
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf.csrf import validate_csrf, ValidationError
from werkzeug.security import check_password_hash

# Import Phase 2 API security components
from utils.jwt_auth import get_jwt_manager, jwt_required
from utils.api_validators import validate_json, user_auth_schema, maritime_api_response
from utils.audit_logger import get_audit_logger, AuditEventType, AuditSeverity
from utils.maritime_api_policies import require_maritime_permission, MaritimePermission

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
        print(f"[DEBUG] Login attempt started")
        
        # SECURITY FIX: Validate CSRF token for non-JSON requests
        if not request.is_json:
            try:
                validate_csrf(request.form.get('csrf_token'))
                print(f"[DEBUG] CSRF token validated successfully")
            except ValidationError as e:
                print(f"[DEBUG] CSRF validation failed: {e}")
                flash('Invalid security token. Please try again.', 'error')
                return render_template('auth/login.html'), 400
        
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

# JWT API Authentication Endpoints (Phase 2)

@auth_bp.route('/api/login', methods=['POST'])
@validate_json(user_auth_schema.__class__)
def api_login():
    """JWT-based API authentication endpoint"""
    try:
        from flask import g
        
        db, User = get_db_and_models()
        jwt_manager = get_jwt_manager()
        audit_logger = get_audit_logger()
        
        # Get validated data from middleware
        login_data = g.validated_data
        email = login_data['email']
        password = login_data['password']
        
        # Find user
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password) and user.is_active:
            # Successful authentication
            
            # Generate JWT tokens
            additional_claims = {
                'maritime_context': True,
                'scopes': ['maritime-operations'],
                'user_email': user.email,
            }
            
            tokens = jwt_manager.generate_tokens(user.id, additional_claims)
            
            # Update last login
            user.update_last_login()
            
            # Log successful authentication
            audit_logger.log_authentication_event(
                AuditEventType.LOGIN_SUCCESS,
                user.id,
                True,
                details={
                    'email': email,
                    'token_type': 'jwt',
                    'scopes': additional_claims['scopes']
                }
            )
            
            return maritime_api_response(
                data={
                    'user': user.to_dict(),
                    'tokens': tokens,
                    'maritime_context': True
                },
                message='Authentication successful'
            )
        
        else:
            # Failed authentication
            audit_logger.log_authentication_event(
                AuditEventType.LOGIN_FAILURE,
                None,
                False,
                details={
                    'email': email,
                    'reason': 'invalid_credentials'
                }
            )
        
        return maritime_api_response(
            errors=['Invalid email or password'],
            status_code=401
        )
        
    except Exception as e:
        audit_logger.log_security_event(
            AuditEventType.SECURITY_VIOLATION,
            f"API login error: {str(e)}"
        )
        return maritime_api_response(
            errors=['Authentication failed'],
            status_code=500
        )

@auth_bp.route('/api/logout', methods=['POST'])
@jwt_required
def api_logout():
    """JWT-based API logout endpoint"""
    try:
        from flask import g
        
        jwt_manager = get_jwt_manager()
        audit_logger = get_audit_logger()
        
        # Get current token from request
        from utils.jwt_auth import extract_jwt_token
        token = extract_jwt_token()
        
        if token:
            # Revoke token
            jwt_manager.revoke_token(token)
            
            # Log logout event
            audit_logger.log_authentication_event(
                AuditEventType.LOGOUT,
                g.jwt_user_id,
                True,
                details={'token_revoked': True}
            )
        
        return maritime_api_response(
            message='Logout successful'
        )
        
    except Exception as e:
        return maritime_api_response(
            errors=['Logout failed'],
            status_code=500
        )

@auth_bp.route('/api/refresh', methods=['POST'])
def api_refresh():
    """JWT token refresh endpoint"""
    try:
        jwt_manager = get_jwt_manager()
        audit_logger = get_audit_logger()
        
        # Get refresh token from request
        refresh_token = request.json.get('refresh_token') if request.is_json else None
        
        if not refresh_token:
            return maritime_api_response(
                errors=['Refresh token required'],
                status_code=400
            )
        
        # Generate new tokens
        new_tokens = jwt_manager.refresh_access_token(refresh_token)
        
        if new_tokens:
            # Log token refresh
            audit_logger.log_event(
                AuditEventType.TOKEN_ISSUED,
                "Access token refreshed",
                severity=AuditSeverity.LOW
            )
            
            return maritime_api_response(
                data={'tokens': new_tokens},
                message='Token refreshed successfully'
            )
        
        else:
            return maritime_api_response(
                errors=['Invalid or expired refresh token'],
                status_code=401
            )
            
    except Exception as e:
        return maritime_api_response(
            errors=['Token refresh failed'],
            status_code=500
        )

@auth_bp.route('/api/user/profile', methods=['GET'])
@jwt_required
def api_user_profile():
    """Get current user profile via JWT"""
    try:
        from flask import g
        
        db, User = get_db_and_models()
        
        # Get user from JWT claims
        user = User.query.get(g.jwt_user_id)
        
        if not user:
            return maritime_api_response(
                errors=['User not found'],
                status_code=404
            )
        
        return maritime_api_response(
            data={
                'user': user.to_dict(),
                'jwt_claims': g.jwt_claims,
                'maritime_context': True
            }
        )
        
    except Exception as e:
        return maritime_api_response(
            errors=['Failed to get user profile'],
            status_code=500
        )

@auth_bp.route('/api/create-api-key', methods=['POST'])
@jwt_required
@require_maritime_permission(MaritimePermission.MANAGE_SYSTEM)
def create_api_key():
    """Create long-lived API key for system integrations"""
    try:
        from flask import g
        from utils.jwt_auth import create_api_key
        
        data = request.get_json()
        description = data.get('description', 'API Key')
        expires_days = data.get('expires_days', 365)
        
        # Create API key
        api_key_data = create_api_key(
            user_id=g.jwt_user_id,
            description=description,
            expires_days=expires_days
        )
        
        # Log API key creation
        audit_logger = get_audit_logger()
        audit_logger.log_event(
            AuditEventType.TOKEN_ISSUED,
            f"API key created: {description}",
            details={
                'description': description,
                'expires_days': expires_days
            },
            severity=AuditSeverity.MEDIUM
        )
        
        return maritime_api_response(
            data=api_key_data,
            message='API key created successfully'
        )
        
    except Exception as e:
        return maritime_api_response(
            errors=['Failed to create API key'],
            status_code=500
        )

@auth_bp.route('/debug-user')
def debug_user():
    """Debug endpoint to test user lookup and password verification"""
    try:
        db, User = get_db_and_models()
        
        # Test user lookup
        email = 'demo@maritime.test'
        user = User.query.filter_by(email=email).first()
        
        result = {
            'user_exists': user is not None,
            'email_searched': email,
        }
        
        if user:
            result.update({
                'user_id': user.id,
                'user_email': user.email,
                'user_username': user.username,
                'user_is_active': user.is_active,
                'password_hash_exists': bool(user.password_hash),
                'password_hash_length': len(user.password_hash) if user.password_hash else 0,
            })
            
            # Test password verification
            test_password = 'demo123'
            try:
                password_check_result = user.check_password(test_password)
                result['password_check_success'] = True
                result['password_check_result'] = password_check_result
            except Exception as e:
                result['password_check_success'] = False
                result['password_check_error'] = str(e)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'exception_type': type(e).__name__
        })