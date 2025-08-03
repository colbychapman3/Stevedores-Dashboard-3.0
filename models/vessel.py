"""
Vessel model for stevedoring operations
Stores vessel information from 4-step wizard
"""

from datetime import datetime

def create_vessel_model(db):
    """Create Vessel model with database instance to avoid circular imports"""
    
    class Vessel(db.Model):
        """Vessel model for stevedoring operations"""
        
        __tablename__ = 'vessels'
        
        id = db.Column(db.Integer, primary_key=True)
        
        # Basic vessel information (Step 1)
        name = db.Column(db.String(100), nullable=False, index=True)
        shipping_line = db.Column(db.String(50), nullable=False, default='K-line')  # K-line, Grimaldi, Glovis, MOL
        vessel_type = db.Column(db.String(50), nullable=False, default='Auto Only')  # Auto Only, Heavy Only, Auto + Heavy
        port_of_call = db.Column(db.String(100), nullable=False, default='Colonel Island')
        operation_start_date = db.Column(db.Date, nullable=True)
        operation_end_date = db.Column(db.Date, nullable=True)
        stevedoring_company = db.Column(db.String(100), nullable=False, default='APS Stevedoring')
        operation_type = db.Column(db.String(50), nullable=False, default='Discharge Only')  # Discharge Only, Loading Only, Discharge + Loadback
        berth_assignment = db.Column(db.String(20), nullable=False, default='Berth 1')  # Berth 1, Berth 2, Berth 3
        operations_manager = db.Column(db.String(50), nullable=False, default='Jonathan')  # Jonathan, Joe, Mark
        
        # Legacy fields for backward compatibility
        eta = db.Column(db.DateTime, nullable=True)
        etd = db.Column(db.DateTime, nullable=True)
        
        # Team assignments (Step 2) - stored as JSON
        team_assignments = db.Column(db.Text, nullable=True)  # JSON: {auto_operations: [], high_heavy: []}
        
        # Cargo configuration (Step 3) - stored as JSON  
        cargo_configuration = db.Column(db.Text, nullable=True)  # JSON: {discharge: {}, loadback: {}}
        
        # Operational parameters (Step 4)
        total_drivers = db.Column(db.Integer, default=0)
        shift_start_time = db.Column(db.Time, nullable=True)
        shift_end_time = db.Column(db.Time, nullable=True)
        ship_start_time = db.Column(db.Time, nullable=True)
        ship_complete_time = db.Column(db.Time, nullable=True)
        number_of_breaks = db.Column(db.Integer, default=0)
        target_completion = db.Column(db.DateTime, nullable=True)
        number_of_vans = db.Column(db.Integer, default=0)
        number_of_wagons = db.Column(db.Integer, default=0)
        number_of_low_decks = db.Column(db.Integer, default=0)
        
        # TICO vehicle details - stored as JSON
        van_details = db.Column(db.Text, nullable=True)  # JSON: [{id_number: '', driver_name: ''}, ...]
        wagon_details = db.Column(db.Text, nullable=True)  # JSON: [{id_number: '', driver_name: ''}, ...]
        
        # Legacy fields for backward compatibility
        total_cargo_capacity = db.Column(db.Integer, default=0)
        cargo_type = db.Column(db.String(50), default='automobile')
        heavy_equipment_count = db.Column(db.Integer, default=0)
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
            return int(self.progress_percentage * self.total_cargo_capacity / 100)
        
        def get_cargo_remaining(self):
            """Calculate remaining cargo to load"""
            return self.total_cargo_capacity - self.get_cargo_loaded()
        
        def is_operations_complete(self):
            """Check if vessel operations are complete"""
            return self.status == 'operations_complete' or self.progress_percentage >= 100.0
        
        def to_dict(self, include_progress=True):
            """Convert vessel to dictionary for API responses"""
            import json
            
            data = {
                'id': self.id,
                'name': self.name,
                'shipping_line': self.shipping_line,
                'vessel_type': self.vessel_type,
                'port_of_call': self.port_of_call,
                'operation_start_date': self.operation_start_date.isoformat() if self.operation_start_date else None,
                'operation_end_date': self.operation_end_date.isoformat() if self.operation_end_date else None,
                'stevedoring_company': self.stevedoring_company,
                'operation_type': self.operation_type,
                'berth_assignment': self.berth_assignment,
                'operations_manager': self.operations_manager,
                'team_assignments': json.loads(self.team_assignments) if self.team_assignments else None,
                'cargo_configuration': json.loads(self.cargo_configuration) if self.cargo_configuration else None,
                'total_drivers': self.total_drivers,
                'shift_start_time': self.shift_start_time.isoformat() if self.shift_start_time else None,
                'shift_end_time': self.shift_end_time.isoformat() if self.shift_end_time else None,
                'ship_start_time': self.ship_start_time.isoformat() if self.ship_start_time else None,
                'ship_complete_time': self.ship_complete_time.isoformat() if self.ship_complete_time else None,
                'number_of_breaks': self.number_of_breaks,
                'target_completion': self.target_completion.isoformat() if self.target_completion else None,
                'number_of_vans': self.number_of_vans,
                'number_of_wagons': self.number_of_wagons,
                'number_of_low_decks': self.number_of_low_decks,
                'van_details': json.loads(self.van_details) if self.van_details else None,
                'wagon_details': json.loads(self.wagon_details) if self.wagon_details else None,
                'status': self.status,
                'current_berth': self.current_berth,
                'wizard_completed': self.wizard_completed,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
                'document_source': self.document_source,
                # Legacy fields
                'eta': self.eta.isoformat() if self.eta else None,
                'etd': self.etd.isoformat() if self.etd else None,
                'total_cargo_capacity': self.total_cargo_capacity,
                'cargo_type': self.cargo_type,
                'heavy_equipment_count': self.heavy_equipment_count,
                'shift_start': self.shift_start.isoformat() if self.shift_start else None,
                'shift_end': self.shift_end.isoformat() if self.shift_end else None,
                'drivers_assigned': self.drivers_assigned,
                'tico_vehicles_needed': self.tico_vehicles_needed
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
    
    return Vessel