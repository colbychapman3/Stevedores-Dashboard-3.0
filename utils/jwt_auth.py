"""
JWT Authentication System for Stevedores Dashboard 3.0
Secure API authentication for maritime operations
"""

import os
import jwt
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any, Union
from functools import wraps
from flask import request, jsonify, current_app, g
from flask_login import current_user

logger = logging.getLogger(__name__)

class JWTAuthManager:
    """JWT Authentication manager for maritime API security"""
    
    def __init__(self, app=None):
        self.app = app
        self.secret_key = None
        self.algorithm = 'HS256'
        self.token_expiry = timedelta(hours=24)  # Maritime shift duration
        self.refresh_token_expiry = timedelta(days=30)  # Extended operations
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize JWT auth with Flask app"""
        self.app = app
        self.secret_key = app.config.get('JWT_SECRET_KEY', app.config.get('SECRET_KEY'))
        
        if not self.secret_key:
            raise ValueError("JWT_SECRET_KEY or SECRET_KEY must be configured")
        
        # Configure JWT settings
        self.algorithm = app.config.get('JWT_ALGORITHM', 'HS256')
        self.token_expiry = timedelta(
            hours=app.config.get('JWT_ACCESS_TOKEN_EXPIRES', 24)
        )
        self.refresh_token_expiry = timedelta(
            days=app.config.get('JWT_REFRESH_TOKEN_EXPIRES', 30)
        )
        
        logger.info("JWT Authentication manager initialized for maritime operations")
    
    def generate_tokens(self, user_id: int, additional_claims: Optional[Dict] = None) -> Dict[str, str]:
        """
        Generate access and refresh JWT tokens for maritime operations
        
        Args:
            user_id: User ID for token
            additional_claims: Additional claims to include
            
        Returns:
            dict: Contains access_token and refresh_token
        """
        try:
            now = datetime.now(timezone.utc)
            
            # Base claims for maritime operations
            base_claims = {
                'user_id': user_id,
                'iat': now,
                'iss': 'stevedores-dashboard',
                'aud': 'maritime-api',
                'maritime_context': True,
            }
            
            # Add any additional claims
            if additional_claims:
                base_claims.update(additional_claims)
            
            # Generate access token
            access_claims = base_claims.copy()
            access_claims.update({
                'exp': now + self.token_expiry,
                'type': 'access',
                'scope': 'maritime-operations'
            })
            
            access_token = jwt.encode(
                access_claims,
                self.secret_key,
                algorithm=self.algorithm
            )
            
            # Generate refresh token
            refresh_claims = base_claims.copy()
            refresh_claims.update({
                'exp': now + self.refresh_token_expiry,
                'type': 'refresh',
                'scope': 'token-refresh'
            })
            
            refresh_token = jwt.encode(
                refresh_claims,
                self.secret_key,
                algorithm=self.algorithm
            )
            
            logger.info(f"JWT tokens generated for user {user_id}")
            
            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'Bearer',
                'expires_in': int(self.token_expiry.total_seconds()),
                'expires_at': (now + self.token_expiry).isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Failed to generate JWT tokens: {e}")
            raise
    
    def verify_token(self, token: str, token_type: str = 'access') -> Optional[Dict]:
        """
        Verify and decode JWT token
        
        Args:
            token: JWT token string
            token_type: Expected token type ('access' or 'refresh')
            
        Returns:
            dict: Decoded token claims or None if invalid
        """
        try:
            # Decode and verify token
            claims = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                audience='maritime-api',
                issuer='stevedores-dashboard'
            )
            
            # Verify token type
            if claims.get('type') != token_type:
                logger.warning(f"Invalid token type: expected {token_type}, got {claims.get('type')}")
                return None
            
            # Verify maritime context
            if not claims.get('maritime_context'):
                logger.warning("Token missing maritime context")
                return None
            
            return claims
            
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
        except Exception as e:
            logger.error(f"JWT token verification failed: {e}")
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """
        Generate new access token using refresh token
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            dict: New token set or None if invalid
        """
        try:
            # Verify refresh token
            claims = self.verify_token(refresh_token, 'refresh')
            if not claims:
                return None
            
            # Generate new tokens
            user_id = claims.get('user_id')
            additional_claims = {
                k: v for k, v in claims.items() 
                if k not in ['exp', 'iat', 'type', 'scope']
            }
            
            return self.generate_tokens(user_id, additional_claims)
            
        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}")
            return None
    
    def revoke_token(self, token: str) -> bool:
        """
        Revoke a JWT token (add to blacklist)
        
        Args:
            token: Token to revoke
            
        Returns:
            bool: True if successfully revoked
        """
        try:
            # In a production system, you would add this to a Redis blacklist
            # For now, we'll log the revocation
            claims = self.verify_token(token)
            if claims:
                logger.info(f"JWT token revoked for user {claims.get('user_id')}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")
            return False

# Global JWT manager instance
jwt_manager = JWTAuthManager()

def init_jwt_auth(app) -> JWTAuthManager:
    """Initialize JWT authentication with Flask app"""
    jwt_manager.init_app(app)
    return jwt_manager

def get_jwt_manager() -> JWTAuthManager:
    """Get the global JWT manager instance"""
    return jwt_manager

def extract_jwt_token() -> Optional[str]:
    """
    Extract JWT token from request headers or query parameters
    
    Returns:
        str: JWT token or None if not found
    """
    # Check Authorization header
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]  # Remove 'Bearer ' prefix
    
    # Check query parameter (for WebSocket or special cases)
    token = request.args.get('token')
    if token:
        return token
    
    # Check form data (for file uploads)
    token = request.form.get('token')
    if token:
        return token
    
    return None

def jwt_required(f):
    """
    Decorator to require valid JWT token for API endpoints
    
    Usage:
        @app.route('/api/secure')
        @jwt_required
        def secure_endpoint():
            # Access user info via g.jwt_claims
            return jsonify({'user_id': g.jwt_claims['user_id']})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = extract_jwt_token()
        
        if not token:
            return jsonify({
                'error': 'JWT token required',
                'message': 'Access token must be provided in Authorization header'
            }), 401
        
        claims = jwt_manager.verify_token(token)
        if not claims:
            return jsonify({
                'error': 'Invalid JWT token',
                'message': 'Token is expired, invalid, or malformed'
            }), 401
        
        # Store claims in Flask's g object for use in the endpoint
        g.jwt_claims = claims
        g.jwt_user_id = claims.get('user_id')
        
        return f(*args, **kwargs)
    
    return decorated_function

def jwt_optional(f):
    """
    Decorator to optionally verify JWT token for API endpoints
    Token validation is performed if present, but not required
    
    Usage:
        @app.route('/api/optional')
        @jwt_optional
        def optional_endpoint():
            if hasattr(g, 'jwt_claims'):
                # User is authenticated
                return jsonify({'user_id': g.jwt_claims['user_id']})
            else:
                # Anonymous access
                return jsonify({'message': 'Anonymous access'})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = extract_jwt_token()
        
        if token:
            claims = jwt_manager.verify_token(token)
            if claims:
                g.jwt_claims = claims
                g.jwt_user_id = claims.get('user_id')
            else:
                # Invalid token - could log this as suspicious
                logger.warning(f"Invalid JWT token attempt from {request.remote_addr}")
        
        return f(*args, **kwargs)
    
    return decorated_function

def maritime_scope_required(required_scope: str):
    """
    Decorator to require specific maritime scope in JWT token
    
    Args:
        required_scope: Required scope (e.g., 'vessel-management', 'cargo-operations')
    
    Usage:
        @app.route('/api/vessels')
        @jwt_required
        @maritime_scope_required('vessel-management')
        def vessel_endpoint():
            return jsonify({'vessels': []})
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'jwt_claims'):
                return jsonify({
                    'error': 'JWT authentication required',
                    'message': 'This endpoint requires JWT authentication'
                }), 401
            
            token_scopes = g.jwt_claims.get('scopes', [])
            if isinstance(token_scopes, str):
                token_scopes = [token_scopes]
            
            if required_scope not in token_scopes and 'maritime-operations' not in token_scopes:
                return jsonify({
                    'error': 'Insufficient scope',
                    'message': f'Required scope: {required_scope}',
                    'provided_scopes': token_scopes
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def get_current_jwt_user() -> Optional[Dict]:
    """
    Get current user information from JWT claims
    
    Returns:
        dict: User information or None if not authenticated
    """
    if hasattr(g, 'jwt_claims'):
        return {
            'user_id': g.jwt_claims.get('user_id'),
            'scopes': g.jwt_claims.get('scopes', []),
            'maritime_context': g.jwt_claims.get('maritime_context', False),
            'issued_at': g.jwt_claims.get('iat'),
            'expires_at': g.jwt_claims.get('exp'),
        }
    return None

def create_api_key(user_id: int, description: str, expires_days: int = 365) -> Dict[str, Any]:
    """
    Create long-lived API key for maritime system integrations
    
    Args:
        user_id: User ID for the API key
        description: Description of the API key usage
        expires_days: Expiration in days (default 1 year)
    
    Returns:
        dict: API key information
    """
    try:
        now = datetime.now(timezone.utc)
        
        claims = {
            'user_id': user_id,
            'iat': now,
            'exp': now + timedelta(days=expires_days),
            'iss': 'stevedores-dashboard',
            'aud': 'maritime-api',
            'type': 'api_key',
            'description': description,
            'maritime_context': True,
            'scopes': ['maritime-operations', 'api-access'],
        }
        
        api_key = jwt.encode(claims, jwt_manager.secret_key, algorithm=jwt_manager.algorithm)
        
        logger.info(f"API key created for user {user_id}: {description}")
        
        return {
            'api_key': api_key,
            'description': description,
            'created_at': now.isoformat(),
            'expires_at': (now + timedelta(days=expires_days)).isoformat(),
            'user_id': user_id,
        }
        
    except Exception as e:
        logger.error(f"Failed to create API key: {e}")
        raise