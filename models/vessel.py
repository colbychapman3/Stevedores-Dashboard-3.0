"""
Vessel model for stevedoring operations
Stores vessel information from 4-step wizard
"""

from datetime import datetime

# Global cache to prevent multiple Vessel model creation
_vessel_model_cache = None

def create_vessel_model(db):
    """Create Vessel model with database instance to avoid circular imports and table redefinition"""
    global _vessel_model_cache
    
    # Return cached model if already created to prevent redefinition
    if _vessel_model_cache is not None:
        return _vessel_model_cache
    
    class Vessel(db.Model):
        """Vessel model for stevedoring operations"""
        
        __tablename__ = 'vessels'
        __table_args__ = {'extend_existing': True}
        
        id = db.Column(db.Integer, primary_key=True)
        
        # Basic vessel information (Step 1)
        name = db.Column(db.String(100), nullable=False, index=True)
        vessel_type = db.Column(db.String(50), nullable=False)
        port_of_call = db.Column(db.String(100), nullable=False)
        eta = db.Column(db.DateTime, nullable=True)
        etd = db.Column(db.DateTime, nullable=True)
        
        # Cargo information (Step 2)  
        total_cargo_capacity = db.Column(db.Integer, default=0)
        cargo_type = db.Column(db.String(50), default='automobile')
        heavy_equipment_count = db.Column(db.Integer, default=0)
        
        # Operational parameters (Step 3)
        shift_start = db.Column(db.Time, nullable=True)
        shift_end = db.Column(db.Time, nullable=True)
        drivers_assigned = db.Column(db.Integer, default=0)
        tico_vehicles_needed = db.Column(db.Integer, default=0)
        
        # Status and tracking
        status = db.Column(db.String(30), default='expected')
        # Status: expected, arrived, berthed, operations_active, operations_complete, departed
        
        current_berth = db.Column(db.String(20), nullable=True)
        progress_percentage = db.Column(db.Float, default=0.0)
        
        # Timestamps
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        created_by_id = db.Column(db.Integer, nullable=True)
        
        # Document processing metadata
        document_source = db.Column(db.String(100), nullable=True)  # filename of auto-fill document
        wizard_completed = db.Column(db.Boolean, default=False)
        
        # Wizard step data storage (JSON fields)
        step_1_data = db.Column(db.Text, nullable=True)  # Basic vessel info
        step_2_data = db.Column(db.Text, nullable=True)  # Cargo configuration
        step_3_data = db.Column(db.Text, nullable=True)  # Operational parameters
        step_4_data = db.Column(db.Text, nullable=True)  # Final review & notes
        
        def __repr__(self):
            return f'<Vessel {self.name} ({self.status})>'
        
        def update_progress(self, percentage):
            """Update vessel operation progress"""
            self.progress_percentage = max(0.0, min(100.0, percentage))
            self.updated_at = datetime.utcnow()
            if percentage >= 100.0:
                self.status = 'operations_complete'
            elif percentage > 0:
                self.status = 'operations_active'
            db.session.commit()
        
        def set_status(self, new_status):
            """Update vessel status"""
            valid_statuses = [
                'expected', 'arrived', 'berthed', 
                'operations_active', 'operations_complete', 'departed'
            ]
            if new_status in valid_statuses:
                self.status = new_status
                self.updated_at = datetime.utcnow()
                db.session.commit()
        
        def get_cargo_loaded(self):
            """Calculate total cargo loaded from tally records"""
            # This will be connected to cargo_tally records
            progress = self.progress_percentage or 0.0
            capacity = self.total_cargo_capacity or 0
            return int(progress * capacity / 100)
        
        def get_cargo_remaining(self):
            """Calculate remaining cargo to load"""
            return self.total_cargo_capacity - self.get_cargo_loaded()
        
        def is_operations_complete(self):
            """Check if vessel operations are complete"""
            return self.status == 'operations_complete' or self.progress_percentage >= 100.0
        
        def to_dict(self, include_progress=True):
            """Convert vessel to dictionary for API responses"""
            data = {
                'id': self.id,
                'name': self.name,
                'vessel_type': self.vessel_type,
                'port_of_call': self.port_of_call,
                'eta': self.eta.isoformat() if self.eta else None,
                'etd': self.etd.isoformat() if self.etd else None,
                'total_cargo_capacity': self.total_cargo_capacity,
                'cargo_type': self.cargo_type,
                'heavy_equipment_count': self.heavy_equipment_count,
                'shift_start': self.shift_start.isoformat() if self.shift_start else None,
                'shift_end': self.shift_end.isoformat() if self.shift_end else None,
                'drivers_assigned': self.drivers_assigned,
                'tico_vehicles_needed': self.tico_vehicles_needed,
                'status': self.status,
                'current_berth': self.current_berth,
                'wizard_completed': self.wizard_completed,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
                'document_source': self.document_source
            }
            
            if include_progress:
                data.update({
                    'progress_percentage': self.progress_percentage,
                    'cargo_loaded': self.get_cargo_loaded(),
                    'cargo_remaining': self.get_cargo_remaining(),
                    'is_complete': self.is_operations_complete()
                })
            
            return data
        
        @classmethod
        def get_active_vessels(cls):
            """Get all vessels with active operations"""
            return cls.query.filter(
                cls.status.in_(['arrived', 'berthed', 'operations_active'])
            ).all()
        
        @classmethod
        def get_by_status(cls, status):
            """Get vessels by status"""
            return cls.query.filter_by(status=status).all()
    
    # Cache the model to prevent redefinition
    _vessel_model_cache = Vessel
    return Vessel