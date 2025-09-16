"""
Production Database Migration & Schema Compatibility
Comprehensive solution for Stevedores Dashboard 3.0 production deployment
"""

import os
import logging
from datetime import datetime
from sqlalchemy import text, MetaData, inspect
from flask import Flask

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProductionDatabaseMigration:
    """Production-safe database migration and schema compatibility handler"""
    
    def __init__(self, app=None, db=None):
        self.app = app
        self.db = db
        self.metadata = None
        self.inspector = None
        
    def initialize(self, app, db):
        """Initialize with Flask app and database"""
        self.app = app
        self.db = db
        self.metadata = MetaData()
        self.inspector = inspect(db.engine)
        
    def get_existing_columns(self, table_name):
        """Get list of existing columns in production database"""
        try:
            columns = self.inspector.get_columns(table_name)
            return {col['name']: col for col in columns}
        except Exception as e:
            logger.warning(f"Could not inspect table {table_name}: {e}")
            return {}
    
    def get_required_vessel_columns(self):
        """Define all required vessel table columns with types and defaults"""
        return {
            # Core required columns (should exist)
            'id': {'type': 'INTEGER', 'nullable': False, 'primary_key': True},
            'name': {'type': 'VARCHAR(100)', 'nullable': False, 'default': None},
            'status': {'type': 'VARCHAR(30)', 'nullable': True, 'default': "'expected'"},
            'created_at': {'type': 'TIMESTAMP', 'nullable': False, 'default': 'CURRENT_TIMESTAMP'},
            'updated_at': {'type': 'TIMESTAMP', 'nullable': True, 'default': 'CURRENT_TIMESTAMP'},
            
            # Step 1 - Basic vessel information
            'shipping_line': {'type': 'VARCHAR(50)', 'nullable': True, 'default': "'K-line'"},
            'vessel_type': {'type': 'VARCHAR(50)', 'nullable': True, 'default': "'Auto Only'"},
            'port_of_call': {'type': 'VARCHAR(100)', 'nullable': True, 'default': "'Colonel Island'"},
            'operation_start_date': {'type': 'DATE', 'nullable': True, 'default': 'NULL'},
            'operation_end_date': {'type': 'DATE', 'nullable': True, 'default': 'NULL'},
            'stevedoring_company': {'type': 'VARCHAR(100)', 'nullable': True, 'default': "'APS Stevedoring'"},
            'operation_type': {'type': 'VARCHAR(50)', 'nullable': True, 'default': "'Discharge Only'"},
            'berth_assignment': {'type': 'VARCHAR(20)', 'nullable': True, 'default': "'Berth 1'"},
            'operations_manager': {'type': 'VARCHAR(50)', 'nullable': True, 'default': "'Jonathan'"},
            
            # Legacy fields for backward compatibility
            'eta': {'type': 'TIMESTAMP', 'nullable': True, 'default': 'NULL'},
            'etd': {'type': 'TIMESTAMP', 'nullable': True, 'default': 'NULL'},
            
            # Step 2 - Team assignments (JSON)
            'team_assignments': {'type': 'TEXT', 'nullable': True, 'default': 'NULL'},
            
            # Step 3 - Cargo configuration (JSON)
            'cargo_configuration': {'type': 'TEXT', 'nullable': True, 'default': 'NULL'},
            
            # Step 4 - Operational parameters
            'total_drivers': {'type': 'INTEGER', 'nullable': True, 'default': '0'},
            'shift_start_time': {'type': 'TIME', 'nullable': True, 'default': 'NULL'},
            'shift_end_time': {'type': 'TIME', 'nullable': True, 'default': 'NULL'},
            'ship_start_time': {'type': 'TIME', 'nullable': True, 'default': 'NULL'},
            'ship_complete_time': {'type': 'TIME', 'nullable': True, 'default': 'NULL'},
            'number_of_breaks': {'type': 'INTEGER', 'nullable': True, 'default': '0'},
            'target_completion': {'type': 'TIMESTAMP', 'nullable': True, 'default': 'NULL'},
            'number_of_vans': {'type': 'INTEGER', 'nullable': True, 'default': '0'},
            'number_of_wagons': {'type': 'INTEGER', 'nullable': True, 'default': '0'},
            'number_of_low_decks': {'type': 'INTEGER', 'nullable': True, 'default': '0'},
            
            # TICO vehicle details (JSON)
            'van_details': {'type': 'TEXT', 'nullable': True, 'default': 'NULL'},
            'wagon_details': {'type': 'TEXT', 'nullable': True, 'default': 'NULL'},
            
            # Legacy fields for backward compatibility
            'total_cargo_capacity': {'type': 'INTEGER', 'nullable': True, 'default': '0'},
            'cargo_type': {'type': 'VARCHAR(50)', 'nullable': True, 'default': "'automobile'"},
            'heavy_equipment_count': {'type': 'INTEGER', 'nullable': True, 'default': '0'},
            'shift_start': {'type': 'TIME', 'nullable': True, 'default': 'NULL'},
            'shift_end': {'type': 'TIME', 'nullable': True, 'default': 'NULL'},
            'drivers_assigned': {'type': 'INTEGER', 'nullable': True, 'default': '0'},
            'tico_vehicles_needed': {'type': 'INTEGER', 'nullable': True, 'default': '0'},
            
            # Status and tracking
            'current_berth': {'type': 'VARCHAR(20)', 'nullable': True, 'default': 'NULL'},
            'progress_percentage': {'type': 'REAL', 'nullable': True, 'default': '0.0'},
            'created_by_id': {'type': 'INTEGER', 'nullable': True, 'default': 'NULL'},
            
            # Document processing metadata
            'document_source': {'type': 'VARCHAR(100)', 'nullable': True, 'default': 'NULL'},
            'wizard_completed': {'type': 'BOOLEAN', 'nullable': True, 'default': 'FALSE'},
            
            # Wizard step data storage (JSON fields)
            'step_1_data': {'type': 'TEXT', 'nullable': True, 'default': 'NULL'},
            'step_2_data': {'type': 'TEXT', 'nullable': True, 'default': 'NULL'},
            'step_3_data': {'type': 'TEXT', 'nullable': True, 'default': 'NULL'},
            'step_4_data': {'type': 'TEXT', 'nullable': True, 'default': 'NULL'},
        }
    
    def generate_migration_sql(self, table_name='vessels'):
        """Generate SQL for adding missing columns"""
        existing_columns = self.get_existing_columns(table_name)
        required_columns = self.get_required_vessel_columns()
        
        migration_sql = []
        missing_columns = []
        
        for col_name, col_def in required_columns.items():
            if col_name not in existing_columns:
                missing_columns.append(col_name)
                
                # Build ALTER TABLE statement
                sql_parts = [f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def['type']}"]
                
                if not col_def.get('nullable', True):
                    sql_parts.append("NOT NULL")
                
                if col_def.get('default') and col_def['default'] != 'NULL':
                    sql_parts.append(f"DEFAULT {col_def['default']}")
                
                migration_sql.append(" ".join(sql_parts) + ";")
        
        return migration_sql, missing_columns
    
    def run_production_migration(self):
        """Execute production-safe database migration"""
        logger.info("🚀 Starting production database migration")
        
        try:
            # Generate migration SQL
            migration_sql, missing_columns = self.generate_migration_sql()
            
            if not missing_columns:
                logger.info("✅ No missing columns detected - database schema is up to date")
                return True, []
            
            logger.info(f"📋 Found {len(missing_columns)} missing columns: {missing_columns}")
            
            # Execute migrations in transaction
            with self.db.engine.begin() as conn:
                for sql_statement in migration_sql:
                    logger.info(f"🔧 Executing: {sql_statement}")
                    conn.execute(text(sql_statement))
            
            logger.info(f"✅ Successfully added {len(missing_columns)} missing columns")
            return True, missing_columns
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            return False, str(e)
    
    def validate_schema(self):
        """Validate current database schema against model requirements"""
        existing_columns = self.get_existing_columns('vessels')
        required_columns = self.get_required_vessel_columns()
        
        missing_columns = []
        for col_name in required_columns:
            if col_name not in existing_columns:
                missing_columns.append(col_name)
        
        return {
            'valid': len(missing_columns) == 0,
            'existing_columns': list(existing_columns.keys()),
            'missing_columns': missing_columns,
            'total_required': len(required_columns),
            'total_existing': len(existing_columns)
        }

# Global migration instance
production_migration = ProductionDatabaseMigration()

def initialize_production_migration(app, db):
    """Initialize the production migration system"""
    production_migration.initialize(app, db)
    return production_migration

def run_migration_if_needed():
    """Run migration only if columns are missing"""
    if production_migration.app is None:
        # Silently return if not initialized to avoid spam warnings
        return False, "Not initialized"
    
    with production_migration.app.app_context():
        return production_migration.run_production_migration()

def get_schema_status():
    """Get current schema validation status"""
    if production_migration.app is None:
        return {"valid": False, "error": "Not initialized"}
    
    with production_migration.app.app_context():
        return production_migration.validate_schema()