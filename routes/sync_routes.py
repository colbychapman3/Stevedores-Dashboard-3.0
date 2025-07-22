"""
Sync API Routes
Handles offline/online data synchronization for maritime operations
"""

import json
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, session
from flask_login import login_required, current_user
from utils.sync_manager import SyncManager, BackgroundSyncScheduler, SyncStatus, ConflictResolution
from models.user import create_user_model
from models.vessel import create_vessel_model
from models.cargo_tally import create_cargo_tally_model

# Create blueprint
sync_bp = Blueprint('sync', __name__)

# Global sync manager instance
sync_manager = SyncManager()
sync_scheduler = BackgroundSyncScheduler(sync_manager)

@sync_bp.route('/status', methods=['GET'])
@login_required
def sync_status():
    """Get current sync status and statistics"""
    try:
        status = sync_scheduler.get_sync_status()
        status['user_id'] = current_user.id
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        current_app.logger.error(f"Sync status error: {e}")
        return jsonify({'error': 'Failed to get sync status'}), 500

@sync_bp.route('/queue', methods=['POST'])
@login_required
def add_to_sync_queue():
    """Add a record to the sync queue"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        table = data.get('table')
        operation = data.get('operation')  # create, update, delete
        record_data = data.get('data', {})
        record_id = data.get('id')
        
        if not table or not operation:
            return jsonify({'error': 'Table and operation required'}), 400
        
        # Add user context
        record_data['user_id'] = current_user.id
        record_data['client_timestamp'] = datetime.utcnow().isoformat()
        
        sync_id = sync_manager.add_to_sync_queue(table, operation, record_data, record_id)
        
        # Try immediate sync if online
        if sync_scheduler.network_status.is_online and sync_scheduler.should_sync():
            sync_scheduler.start_sync()
            # Trigger background sync (would be handled by background task in production)
        
        return jsonify({
            'success': True,
            'sync_id': sync_id,
            'queued_at': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Add to sync queue error: {e}")
        return jsonify({'error': 'Failed to add to sync queue'}), 500

@sync_bp.route('/process', methods=['POST'])
@login_required
def process_sync_batch():
    """Process a batch of sync records"""
    try:
        # Get database instances
        from app import db
        User = create_user_model(db)
        Vessel = create_vessel_model(db)
        CargoTally = create_cargo_tally_model(db)
        
        batch_size = request.get_json().get('batch_size', 10) if request.get_json() else 10
        
        # Get pending records
        pending_records = sync_manager.get_pending_sync_records(batch_size)
        
        if not pending_records:
            return jsonify({
                'success': True,
                'message': 'No records to sync',
                'processed': 0
            })
        
        processed_count = 0
        conflicts = []
        errors = []
        
        for record in pending_records:
            try:
                sync_manager.mark_as_syncing(record.id)
                
                # Process based on table type
                if record.table == 'vessels':
                    result = _process_vessel_sync(record, Vessel, db)
                elif record.table == 'cargo_tallies':
                    result = _process_cargo_tally_sync(record, CargoTally, db)
                else:
                    result = {'success': False, 'error': f'Unknown table: {record.table}'}
                
                if result['success']:
                    sync_manager.mark_as_synced(record.id, result.get('server_hash', ''))
                    processed_count += 1
                elif result.get('conflict'):
                    sync_manager.mark_as_conflict(record.id, result['server_data'])
                    conflicts.append({
                        'sync_id': record.id,
                        'table': record.table,
                        'client_data': record.data,
                        'server_data': result['server_data']
                    })
                else:
                    sync_manager.mark_as_error(record.id, result.get('error', 'Unknown error'))
                    errors.append({
                        'sync_id': record.id,
                        'error': result.get('error', 'Unknown error')
                    })
                    
            except Exception as e:
                sync_manager.mark_as_error(record.id, str(e))
                errors.append({
                    'sync_id': record.id,
                    'error': str(e)
                })
        
        return jsonify({
            'success': True,
            'processed': processed_count,
            'conflicts': len(conflicts),
            'errors': len(errors),
            'conflict_details': conflicts,
            'error_details': errors
        })
        
    except Exception as e:
        current_app.logger.error(f"Process sync batch error: {e}")
        return jsonify({'error': 'Failed to process sync batch'}), 500

@sync_bp.route('/conflicts', methods=['GET'])
@login_required
def get_conflicts():
    """Get all sync conflicts that need resolution"""
    try:
        conflicts = sync_manager.get_conflicts()
        
        conflict_data = []
        for conflict in conflicts:
            conflict_data.append({
                'sync_id': conflict.id,
                'table': conflict.table,
                'operation': conflict.operation,
                'client_data': conflict.data,
                'server_data': conflict.conflict_data,
                'timestamp': conflict.timestamp,
                'last_sync_attempt': conflict.last_sync_attempt
            })
        
        return jsonify({
            'success': True,
            'conflicts': conflict_data,
            'count': len(conflict_data)
        })
        
    except Exception as e:
        current_app.logger.error(f"Get conflicts error: {e}")
        return jsonify({'error': 'Failed to get conflicts'}), 500

@sync_bp.route('/resolve-conflict', methods=['POST'])
@login_required
def resolve_conflict():
    """Resolve a sync conflict"""
    try:
        data = request.get_json()
        sync_id = data.get('sync_id')
        resolution = data.get('resolution', 'merge')  # client_wins, server_wins, merge
        
        if not sync_id:
            return jsonify({'error': 'sync_id required'}), 400
        
        # Map string to enum
        resolution_map = {
            'client_wins': ConflictResolution.CLIENT_WINS,
            'server_wins': ConflictResolution.SERVER_WINS,
            'merge': ConflictResolution.MERGE,
            'manual': ConflictResolution.MANUAL
        }
        
        resolution_enum = resolution_map.get(resolution, ConflictResolution.MERGE)
        
        resolved_data = sync_manager.resolve_conflict(sync_id, resolution_enum)
        
        if resolved_data:
            return jsonify({
                'success': True,
                'resolved_data': resolved_data,
                'resolution_used': resolution
            })
        else:
            return jsonify({'error': 'Failed to resolve conflict'}), 400
            
    except Exception as e:
        current_app.logger.error(f"Resolve conflict error: {e}")
        return jsonify({'error': 'Failed to resolve conflict'}), 500

@sync_bp.route('/network-status', methods=['POST'])
@login_required
def update_network_status():
    """Update network connectivity status"""
    try:
        data = request.get_json()
        status = data.get('status', 'online')  # online, offline, poor
        
        if status == 'online':
            sync_scheduler.network_status.mark_online()
        elif status == 'offline':
            sync_scheduler.network_status.mark_offline()
        elif status == 'poor':
            sync_scheduler.network_status.mark_poor_connection()
        
        return jsonify({
            'success': True,
            'network_status': sync_scheduler.network_status.get_status()
        })
        
    except Exception as e:
        current_app.logger.error(f"Network status update error: {e}")
        return jsonify({'error': 'Failed to update network status'}), 500

@sync_bp.route('/cleanup', methods=['POST'])
@login_required
def cleanup_sync_records():
    """Clean up old sync records"""
    try:
        data = request.get_json() if request.get_json() else {}
        hours = data.get('older_than_hours', 24)
        
        cleaned_count = sync_manager.cleanup_synced_records(hours)
        
        return jsonify({
            'success': True,
            'cleaned_records': cleaned_count,
            'remaining_records': len(sync_manager.sync_queue)
        })
        
    except Exception as e:
        current_app.logger.error(f"Cleanup sync records error: {e}")
        return jsonify({'error': 'Failed to cleanup sync records'}), 500

@sync_bp.route('/force-sync', methods=['POST'])
@login_required
def force_sync():
    """Force an immediate sync operation"""
    try:
        if sync_scheduler.sync_in_progress:
            return jsonify({'error': 'Sync already in progress'}), 400
        
        sync_scheduler.start_sync()
        
        # Process the sync batch
        response = process_sync_batch()
        
        sync_scheduler.complete_sync(response[1] < 400)  # Success if status < 400
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Force sync error: {e}")
        sync_scheduler.complete_sync(False)
        return jsonify({'error': 'Failed to force sync'}), 500

def _process_vessel_sync(record, Vessel, db):
    """Process vessel sync record"""
    try:
        if record.operation == 'create':
            # Check if vessel already exists
            existing = Vessel.query.filter_by(id=record.data.get('id')).first()
            if existing:
                # Compare data to detect conflict
                server_hash = sync_manager._calculate_hash(existing.to_dict())
                if server_hash != record.client_hash:
                    return {
                        'success': False,
                        'conflict': True,
                        'server_data': existing.to_dict()
                    }
            
            # Create new vessel
            vessel_data = record.data.copy()
            vessel_data.pop('client_timestamp', None)
            
            vessel = Vessel(**vessel_data)
            db.session.add(vessel)
            db.session.commit()
            
            return {
                'success': True,
                'server_hash': sync_manager._calculate_hash(vessel.to_dict())
            }
            
        elif record.operation == 'update':
            vessel = Vessel.query.get(record.data.get('id'))
            if not vessel:
                return {'success': False, 'error': 'Vessel not found'}
            
            # Check for conflicts
            server_hash = sync_manager._calculate_hash(vessel.to_dict())
            if server_hash != record.client_hash:
                return {
                    'success': False,
                    'conflict': True,
                    'server_data': vessel.to_dict()
                }
            
            # Update vessel
            for key, value in record.data.items():
                if hasattr(vessel, key) and key not in ['id', 'created_at']:
                    setattr(vessel, key, value)
            
            vessel.updated_at = datetime.utcnow()
            db.session.commit()
            
            return {
                'success': True,
                'server_hash': sync_manager._calculate_hash(vessel.to_dict())
            }
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

def _process_cargo_tally_sync(record, CargoTally, db):
    """Process cargo tally sync record"""
    try:
        if record.operation == 'create':
            # Create new cargo tally
            tally_data = record.data.copy()
            tally_data.pop('client_timestamp', None)
            
            tally = CargoTally(**tally_data)
            db.session.add(tally)
            db.session.commit()
            
            return {
                'success': True,
                'server_hash': sync_manager._calculate_hash(tally.to_dict())
            }
            
        elif record.operation == 'update':
            tally = CargoTally.query.get(record.data.get('id'))
            if not tally:
                return {'success': False, 'error': 'Cargo tally not found'}
            
            # For cargo tallies, usually append-only, so conflicts are rare
            # Update tally
            for key, value in record.data.items():
                if hasattr(tally, key) and key not in ['id', 'timestamp']:
                    setattr(tally, key, value)
            
            db.session.commit()
            
            return {
                'success': True,
                'server_hash': sync_manager._calculate_hash(tally.to_dict())
            }
            
    except Exception as e:
        return {'success': False, 'error': str(e)}