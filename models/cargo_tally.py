"""
Cargo Tally model for real-time cargo tracking
Handles individual cargo tally entries and calculations
"""

from datetime import datetime

def create_cargo_tally_model(db):
    """Create CargoTally model with database instance to avoid circular imports"""
    
    class CargoTally(db.Model):
        """Cargo tally model for real-time tracking"""
        
        __tablename__ = 'cargo_tallies'
        
        id = db.Column(db.Integer, primary_key=True)
        vessel_id = db.Column(db.Integer, nullable=False, index=True)
        
        # Tally information
        tally_type = db.Column(db.String(20), default='loaded')  # loaded, discharged
        cargo_count = db.Column(db.Integer, nullable=False)
        location = db.Column(db.String(50), nullable=True)  # deck, hatch, zone info
        
        # Timestamps
        timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        recorded_by_id = db.Column(db.Integer, nullable=True)
        
        # Sync tracking for offline operations
        synced = db.Column(db.Boolean, default=False)
        sync_timestamp = db.Column(db.DateTime, nullable=True)
        
        # Additional metadata
        notes = db.Column(db.Text, nullable=True)
        shift_period = db.Column(db.String(20), nullable=True)  # morning, afternoon, night
        
        def __repr__(self):
            return f'<CargoTally {self.cargo_count} {self.tally_type} for vessel {self.vessel_id}>'
        
        def mark_synced(self):
            """Mark this tally as synced with server"""
            self.synced = True
            self.sync_timestamp = datetime.utcnow()
            db.session.commit()
        
        def to_dict(self):
            """Convert cargo tally to dictionary for API responses"""
            return {
                'id': self.id,
                'vessel_id': self.vessel_id,
                'tally_type': self.tally_type,
                'cargo_count': self.cargo_count,
                'location': self.location,
                'timestamp': self.timestamp.isoformat() if self.timestamp else None,
                'recorded_by_id': self.recorded_by_id,
                'synced': self.synced,
                'sync_timestamp': self.sync_timestamp.isoformat() if self.sync_timestamp else None,
                'notes': self.notes,
                'shift_period': self.shift_period
            }
        
        @classmethod
        def get_vessel_total(cls, vessel_id, tally_type='loaded'):
            """Get total cargo count for vessel by type"""
            result = db.session.query(
                db.func.sum(cls.cargo_count)
            ).filter_by(
                vessel_id=vessel_id,
                tally_type=tally_type
            ).scalar()
            return result or 0
        
        @classmethod
        def get_vessel_tallies(cls, vessel_id, limit=50):
            """Get recent tallies for a vessel"""
            return cls.query.filter_by(
                vessel_id=vessel_id
            ).order_by(
                cls.timestamp.desc()
            ).limit(limit).all()
        
        @classmethod
        def get_unsynced_tallies(cls):
            """Get all tallies that need to be synced"""
            return cls.query.filter_by(synced=False).all()
        
        @classmethod
        def create_tally(cls, vessel_id, cargo_count, tally_type='loaded', **kwargs):
            """Create a new cargo tally entry"""
            tally = cls(
                vessel_id=vessel_id,
                cargo_count=cargo_count,
                tally_type=tally_type,
                **kwargs
            )
            db.session.add(tally)
            db.session.commit()
            
            # Update vessel progress
            cls._update_vessel_progress(vessel_id)
            
            return tally
        
        @classmethod
        def _update_vessel_progress(cls, vessel_id):
            """Update vessel progress based on cargo tallies"""
            # Import here to avoid circular imports
            from models.vessel import create_vessel_model
            Vessel = create_vessel_model(db)
            
            vessel = Vessel.query.get(vessel_id)
            if vessel and vessel.total_cargo_capacity > 0:
                loaded_count = cls.get_vessel_total(vessel_id, 'loaded')
                progress = (loaded_count / vessel.total_cargo_capacity) * 100
                vessel.update_progress(progress)
    
    return CargoTally