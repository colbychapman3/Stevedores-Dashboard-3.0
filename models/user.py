"""
User model for stevedoring operations
Simple authentication system
"""

from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import check_password_hash

def create_user_model(db):
    """Create User model with database instance to avoid circular imports"""
    
    class User(db.Model, UserMixin):
        """User model for stevedoring operations"""
        
        __tablename__ = 'users'
        
        id = db.Column(db.Integer, primary_key=True)
        email = db.Column(db.String(120), unique=True, nullable=False, index=True)
        username = db.Column(db.String(80), unique=True, nullable=False, index=True)
        password_hash = db.Column(db.String(255), nullable=False)
        is_active = db.Column(db.Boolean, default=True, nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        last_login = db.Column(db.DateTime)
        
        def __repr__(self):
            return f'<User {self.username}>'
        
        def check_password(self, password):
            """Check if provided password matches hash"""
            return check_password_hash(self.password_hash, password)
        
        def update_last_login(self):
            """Update last login timestamp"""
            self.last_login = datetime.utcnow()
            db.session.commit()
        
        def to_dict(self):
            """Convert user to dictionary for API responses"""
            return {
                'id': self.id,
                'email': self.email,
                'username': self.username,
                'is_active': self.is_active,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'last_login': self.last_login.isoformat() if self.last_login else None
            }
    
    return User