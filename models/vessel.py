"""
Vessel model for stevedoring operations
Stores vessel information from 4-step wizard
"""

from datetime import datetime
from sqlalchemy import text

# Global cache to prevent multiple Vessel model creation
_vessel_model_cache = None

def create_vessel_model(db):
    """Create Vessel model with database instance to avoid circular imports and table redefinition"""
    global _vessel_model_cache
    
    # Return cached model if already created to prevent redefinition
    if _vessel_model_cache is not None:
        return _vessel_model_cache
    
    def check_column_exists(table_name, column_name):
        """Check if a column exists in the database table"""
        try:
            # For PostgreSQL, check information_schema (SQLAlchemy 2.x compatible)
            with db.engine.connect() as connection:
                result = connection.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = :table_name AND column_name = :column_name
                """), {'table_name': table_name, 'column_name': column_name})
                return result.fetchone() is not None
        except Exception:
            # Fallback for other databases or if query fails
            return False
    
    class Vessel(db.Model):
        """Vessel model for stevedoring operations"""
        
        __tablename__ = 'vessels'
        __table_args__ = {'extend_existing': True}
        
        id = db.Column(db.Integer, primary_key=True)
        
        # Basic vessel information (Step 1)
        name = db.Column(db.String(100), nullable=False, index=True)
        shipping_line = db.Column(db.String(50), nullable=True, default='K-line')  # K-line, Grimaldi, Glovis, MOL
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
            """Convert vessel to dictionary for API responses with production schema compatibility"""
            import json
            
            # Safe JSON parsing with error handling
            def safe_json_loads(json_str):
                if not json_str:
                    return None
                try:
                    return json.loads(json_str)
                except (json.JSONDecodeError, TypeError):
                    # Return None for invalid JSON data, don't crash the whole operation
                    return None
            
            # Production-grade safe attribute access with column existence detection
            def safe_getattr(obj, attr, fallback=None, format_func=None):
                try:
                    value = getattr(obj, attr)
                    if value is not None and format_func:
                        return format_func(value)
                    return value
                except (AttributeError, Exception):
                    # Column doesn't exist in database or access failed
                    return fallback
            
            # Safe date/datetime formatting
            def format_date(dt_obj):
                if dt_obj:
                    return dt_obj.isoformat()
                return None
            
            def format_time(time_obj):
                if time_obj:
                    return time_obj.isoformat()
                return None
            
            # Production-grade data serialization with schema compatibility
            data = {
                # Core fields (should always exist)
                'id': self.id,
                'name': self.name,
                'status': safe_getattr(self, 'status', 'expected'),
                'created_at': safe_getattr(self, 'created_at', None, format_date),
                'updated_at': safe_getattr(self, 'updated_at', None, format_date),
                
                # Step 1 - Basic vessel information (may be missing in old schemas)
                'shipping_line': safe_getattr(self, 'shipping_line', 'K-line'),
                'vessel_type': safe_getattr(self, 'vessel_type', 'Auto Only'),
                'port_of_call': safe_getattr(self, 'port_of_call', 'Colonel Island'),
                'operation_start_date': safe_getattr(self, 'operation_start_date', None, format_date),
                'operation_end_date': safe_getattr(self, 'operation_end_date', None, format_date),
                'stevedoring_company': safe_getattr(self, 'stevedoring_company', 'APS Stevedoring'),
                'operation_type': safe_getattr(self, 'operation_type', 'Discharge Only'),
                'berth_assignment': safe_getattr(self, 'berth_assignment', 'Berth 1'),
                'operations_manager': safe_getattr(self, 'operations_manager', 'Jonathan'),
                
                # Step 2 - Team assignments (JSON)
                'team_assignments': safe_json_loads(safe_getattr(self, 'team_assignments', None)),
                
                # Step 3 - Cargo configuration (JSON)
                'cargo_configuration': safe_json_loads(safe_getattr(self, 'cargo_configuration', None)),
                
                # Step 4 - Operational parameters
                'total_drivers': safe_getattr(self, 'total_drivers', 0),
                'shift_start_time': safe_getattr(self, 'shift_start_time', None, format_time),
                'shift_end_time': safe_getattr(self, 'shift_end_time', None, format_time),
                'ship_start_time': safe_getattr(self, 'ship_start_time', None, format_time),
                'ship_complete_time': safe_getattr(self, 'ship_complete_time', None, format_time),
                'number_of_breaks': safe_getattr(self, 'number_of_breaks', 0),
                'target_completion': safe_getattr(self, 'target_completion', None, format_date),
                'number_of_vans': safe_getattr(self, 'number_of_vans', 0),
                'number_of_wagons': safe_getattr(self, 'number_of_wagons', 0),
                'number_of_low_decks': safe_getattr(self, 'number_of_low_decks', 0),
                
                # TICO vehicle details (JSON)
                'van_details': safe_json_loads(safe_getattr(self, 'van_details', None)),
                'wagon_details': safe_json_loads(safe_getattr(self, 'wagon_details', None)),
                
                # Status and tracking
                'current_berth': safe_getattr(self, 'current_berth', None),
                'progress_percentage': safe_getattr(self, 'progress_percentage', 0.0),
                'created_by_id': safe_getattr(self, 'created_by_id', None),
                
                # Document processing metadata
                'document_source': safe_getattr(self, 'document_source', None),
                'wizard_completed': safe_getattr(self, 'wizard_completed', False),
                
                # Wizard step data (JSON)
                'step_1_data': safe_json_loads(safe_getattr(self, 'step_1_data', None)),
                'step_2_data': safe_json_loads(safe_getattr(self, 'step_2_data', None)),
                'step_3_data': safe_json_loads(safe_getattr(self, 'step_3_data', None)),
                'step_4_data': safe_json_loads(safe_getattr(self, 'step_4_data', None)),
                
                # Legacy fields for backward compatibility
                'eta': safe_getattr(self, 'eta', None, format_date),
                'etd': safe_getattr(self, 'etd', None, format_date),
                'total_cargo_capacity': safe_getattr(self, 'total_cargo_capacity', 0),
                'cargo_type': safe_getattr(self, 'cargo_type', 'automobile'),
                'heavy_equipment_count': safe_getattr(self, 'heavy_equipment_count', 0),
                'shift_start': safe_getattr(self, 'shift_start', None, format_time),
                'shift_end': safe_getattr(self, 'shift_end', None, format_time),
                'drivers_assigned': safe_getattr(self, 'drivers_assigned', 0),
                'tico_vehicles_needed': safe_getattr(self, 'tico_vehicles_needed', 0)
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
    
    # Production database migration and schema compatibility
    try:
        from production_db_migration import initialize_production_migration, run_migration_if_needed
        
        # Initialize migration system with Flask app context
        from flask import current_app
        if current_app:
            migration_system = initialize_production_migration(current_app, db)
            
            # Run comprehensive migration if needed
            success, result = run_migration_if_needed()
            if success and result:
                print(f"✅ Production migration completed: {len(result)} columns added")
            elif not success:
                print(f"⚠️  Migration issue: {result}")
            else:
                print("✅ Database schema is up to date")
            
    except Exception as e:
        print(f"⚠️  Migration system not available: {e}")
        
        # Fallback to basic column check for critical columns (SQLAlchemy 2.x compatible)
        try:
            if not check_column_exists('vessels', 'shipping_line'):
                with db.engine.connect() as connection:
                    connection.execute(text("""
                        ALTER TABLE vessels 
                        ADD COLUMN shipping_line VARCHAR(50) DEFAULT 'K-line'
                    """))
                    connection.commit()
                print("✅ Added missing shipping_line column (fallback)")
        except Exception as fallback_error:
            print(f"⚠️  Fallback migration failed: {fallback_error}")
    
    # Cache the model to prevent redefinition
    _vessel_model_cache = Vessel
    return Vessel