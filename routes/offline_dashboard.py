"""
Offline-Capable Dashboard Routes
Provides dashboard functionality with offline data support
"""

import json
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, current_app
from flask_login import login_required, current_user
from utils.offline_data_manager import OfflineDataManager, DataStatus

# Create blueprint
offline_dashboard_bp = Blueprint('offline_dashboard', __name__)

# Initialize offline data manager
offline_data_manager = OfflineDataManager()

@offline_dashboard_bp.route('/dashboard-data', methods=['GET'])
@login_required
def get_dashboard_data():
    """Get dashboard data with offline support"""
    try:
        from app import db, Vessel, CargoTally
        
        force_offline = request.args.get('offline', 'false').lower() == 'true'
        include_stale = request.args.get('include_stale', 'true').lower() == 'true'
        
        if force_offline or not _is_online():
            # Use cached data
            vessel_data = offline_data_manager.get_cached_vessels(include_stale)
            dashboard_summary = offline_data_manager.get_dashboard_summary()
            
            return jsonify({
                'success': True,
                'mode': 'offline',
                'vessels': vessel_data['vessels'],
                'summary': dashboard_summary,
                'data_status': vessel_data['status'].value,
                'last_updated': vessel_data['last_updated'],
                'timestamp': datetime.utcnow().isoformat()
            })
        
        else:
            # Try to get fresh data from server
            try:
                vessels = Vessel.query.all()
                vessel_list = []
                for vessel in vessels:
                    try:
                        vessel_list.append(vessel.to_dict(include_progress=True))
                    except Exception as e:
                        current_app.logger.error(f"Error converting vessel {vessel.id} to dict: {e}")
                        # Skip problematic vessels rather than crashing the whole dashboard
                        continue
                
                # Cache the fresh data
                offline_data_manager.cache_vessel_data(vessel_list, "server")
                
                # Merge with offline-created vessels
                merged_vessels = offline_data_manager.merge_offline_and_server_vessels(vessel_list)
                
                # Calculate summary
                dashboard_summary = _calculate_dashboard_summary(merged_vessels)
                
                return jsonify({
                    'success': True,
                    'mode': 'online',
                    'vessels': merged_vessels,
                    'summary': dashboard_summary,
                    'data_status': 'fresh',
                    'last_updated': datetime.utcnow().isoformat(),
                    'timestamp': datetime.utcnow().isoformat()
                })
                
            except Exception as e:
                current_app.logger.error(f"Online dashboard data error: {e}")
                
                # Fall back to cached data
                vessel_data = offline_data_manager.get_cached_vessels(include_stale)
                dashboard_summary = offline_data_manager.get_dashboard_summary()
                
                return jsonify({
                    'success': True,
                    'mode': 'offline_fallback',
                    'vessels': vessel_data['vessels'],
                    'summary': dashboard_summary,
                    'data_status': vessel_data['status'].value,
                    'last_updated': vessel_data['last_updated'],
                    'timestamp': datetime.utcnow().isoformat(),
                    'error': 'Server unavailable, using cached data'
                })
        
    except Exception as e:
        current_app.logger.error(f"Dashboard data error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load dashboard data'
        }), 500

@offline_dashboard_bp.route('/vessel/<vessel_id>/data', methods=['GET'])
@login_required
def get_vessel_data(vessel_id):
    """Get individual vessel data with offline support"""
    try:
        from app import db, Vessel, CargoTally
        
        is_offline_id = vessel_id.startswith('offline_')
        force_offline = request.args.get('offline', 'false').lower() == 'true'
        
        if is_offline_id:
            # Get offline vessel
            offline_vessels = offline_data_manager.get_offline_vessels()
            vessel = next((v for v in offline_vessels if v.get('offline_id') == vessel_id), None)
            
            if not vessel:
                return jsonify({'error': 'Vessel not found'}), 404
            
            # Get cached cargo tallies (if any)
            tally_data = offline_data_manager.get_cached_cargo_tallies(vessel_id)
            
            return jsonify({
                'success': True,
                'mode': 'offline',
                'vessel': vessel,
                'cargo_tallies': tally_data['tallies'],
                'is_offline_vessel': True,
                'timestamp': datetime.utcnow().isoformat()
            })
        
        elif force_offline or not _is_online():
            # Use cached data for server vessel
            vessel_data = offline_data_manager.get_cached_vessels()
            vessel = next((v for v in vessel_data['vessels'] if v.get('id') == int(vessel_id)), None)
            
            if not vessel:
                return jsonify({'error': 'Vessel not found in cache'}), 404
            
            tally_data = offline_data_manager.get_cached_cargo_tallies(int(vessel_id))
            
            return jsonify({
                'success': True,
                'mode': 'offline',
                'vessel': vessel,
                'cargo_tallies': tally_data['tallies'],
                'is_offline_vessel': False,
                'data_status': vessel_data['status'].value,
                'timestamp': datetime.utcnow().isoformat()
            })
        
        else:
            # Get fresh data from server
            try:
                vessel = Vessel.query.get_or_404(vessel_id)
                cargo_tallies = CargoTally.query.filter_by(vessel_id=vessel_id).order_by(
                    CargoTally.timestamp.desc()
                ).limit(20).all()
                
                vessel_dict = vessel.to_dict(include_progress=True)
                tally_list = [tally.to_dict() for tally in cargo_tallies]
                
                # Cache the data
                offline_data_manager.cache_cargo_tallies(int(vessel_id), tally_list)
                
                return jsonify({
                    'success': True,
                    'mode': 'online',
                    'vessel': vessel_dict,
                    'cargo_tallies': tally_list,
                    'is_offline_vessel': False,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
            except Exception as e:
                current_app.logger.error(f"Online vessel data error: {e}")
                
                # Fall back to cached data
                vessel_data = offline_data_manager.get_cached_vessels()
                vessel = next((v for v in vessel_data['vessels'] if v.get('id') == int(vessel_id)), None)
                
                if not vessel:
                    return jsonify({'error': 'Vessel not found'}), 404
                
                tally_data = offline_data_manager.get_cached_cargo_tallies(int(vessel_id))
                
                return jsonify({
                    'success': True,
                    'mode': 'offline_fallback',
                    'vessel': vessel,
                    'cargo_tallies': tally_data['tallies'],
                    'is_offline_vessel': False,
                    'error': 'Server unavailable, using cached data',
                    'timestamp': datetime.utcnow().isoformat()
                })
        
    except Exception as e:
        current_app.logger.error(f"Vessel data error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load vessel data'
        }), 500

@offline_dashboard_bp.route('/vessel/<vessel_id>/update-progress', methods=['POST'])
@login_required
def update_vessel_progress(vessel_id):
    """Update vessel progress with offline support"""
    try:
        data = request.get_json()
        if not data or 'progress' not in data:
            return jsonify({'error': 'Progress value required'}), 400
        
        progress = float(data['progress'])
        is_offline_id = vessel_id.startswith('offline_')
        
        if is_offline_id:
            # Update offline vessel
            success = offline_data_manager.update_vessel_progress(vessel_id, progress, is_offline_id=True)
            
            if success:
                return jsonify({
                    'success': True,
                    'mode': 'offline',
                    'vessel_id': vessel_id,
                    'new_progress': progress,
                    'timestamp': datetime.utcnow().isoformat()
                })
            else:
                return jsonify({'error': 'Failed to update offline vessel'}), 500
        
        elif not _is_online():
            # Update cached vessel data
            success = offline_data_manager.update_vessel_progress(vessel_id, progress, is_offline_id=False)
            
            if success:
                # Also add to sync queue for when online
                try:
                    from routes.sync_routes import sync_manager
                    sync_manager.add_to_sync_queue('vessels', 'update', {
                        'id': int(vessel_id),
                        'progress_percentage': progress,
                        'updated_at': datetime.utcnow().isoformat()
                    })
                except ImportError:
                    pass  # Sync manager not available
                
                return jsonify({
                    'success': True,
                    'mode': 'offline',
                    'vessel_id': vessel_id,
                    'new_progress': progress,
                    'queued_for_sync': True,
                    'timestamp': datetime.utcnow().isoformat()
                })
            else:
                return jsonify({'error': 'Failed to update vessel progress'}), 500
        
        else:
            # Update server directly
            try:
                from app import db, Vessel
                
                vessel = Vessel.query.get_or_404(vessel_id)
                vessel.update_progress(progress)
                
                # Update cache as well
                offline_data_manager.update_vessel_progress(vessel_id, progress, is_offline_id=False)
                
                return jsonify({
                    'success': True,
                    'mode': 'online',
                    'vessel_id': vessel_id,
                    'new_progress': progress,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
            except Exception as e:
                current_app.logger.error(f"Online progress update error: {e}")
                
                # Fall back to offline update
                success = offline_data_manager.update_vessel_progress(vessel_id, progress, is_offline_id=False)
                
                if success:
                    try:
                        from routes.sync_routes import sync_manager
                        sync_manager.add_to_sync_queue('vessels', 'update', {
                            'id': int(vessel_id),
                            'progress_percentage': progress,
                            'updated_at': datetime.utcnow().isoformat()
                        })
                    except ImportError:
                        pass  # Sync manager not available
                
                return jsonify({
                    'success': True,
                    'mode': 'offline_fallback',
                    'vessel_id': vessel_id,
                    'new_progress': progress,
                    'queued_for_sync': True,
                    'error': 'Server unavailable, cached locally',
                    'timestamp': datetime.utcnow().isoformat()
                })
        
    except Exception as e:
        current_app.logger.error(f"Progress update error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to update vessel progress'
        }), 500

@offline_dashboard_bp.route('/cache/refresh', methods=['POST'])
@login_required
def refresh_cache():
    """Manually refresh cached data"""
    try:
        from app import db, Vessel, CargoTally
        
        cache_type = request.get_json().get('type', 'all') if request.get_json() else 'all'
        
        refreshed = []
        
        if cache_type in ['all', 'vessels']:
            try:
                vessels = Vessel.query.all()
                vessel_list = []
                for vessel in vessels:
                    try:
                        vessel_list.append(vessel.to_dict(include_progress=True))
                    except Exception as e:
                        current_app.logger.error(f"Error converting vessel {vessel.id} to dict in cache refresh: {e}")
                        continue
                
                if offline_data_manager.cache_vessel_data(vessel_list, "server"):
                    refreshed.append('vessels')
            except Exception as e:
                current_app.logger.error(f"Error refreshing vessels cache: {e}")
        
        if cache_type in ['all', 'cargo_tallies']:
            try:
                # Refresh cargo tallies for all cached vessels
                vessel_data = offline_data_manager.get_cached_vessels()
                for vessel in vessel_data['vessels']:
                    vessel_id = vessel.get('id')
                    if vessel_id:
                        tallies = CargoTally.query.filter_by(vessel_id=vessel_id).order_by(
                            CargoTally.timestamp.desc()
                        ).limit(20).all()
                        
                        tally_list = [tally.to_dict() for tally in tallies]
                        offline_data_manager.cache_cargo_tallies(vessel_id, tally_list)
                
                refreshed.append('cargo_tallies')
            except Exception as e:
                current_app.logger.error(f"Error refreshing cargo tallies cache: {e}")
        
        return jsonify({
            'success': True,
            'refreshed': refreshed,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Cache refresh error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to refresh cache'
        }), 500

@offline_dashboard_bp.route('/cache/clear', methods=['POST'])
@login_required
def clear_cache():
    """Clear cached data"""
    try:
        cache_type = request.get_json().get('type') if request.get_json() else None
        
        success = offline_data_manager.clear_cache(cache_type)
        
        return jsonify({
            'success': success,
            'cleared': cache_type or 'all',
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Cache clear error: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to clear cache'
        }), 500

@offline_dashboard_bp.route('/client-data-manager.js')
def client_data_manager_script():
    """Serve client-side data manager JavaScript"""
    try:
        from utils.offline_data_manager import ClientDataManager
        
        js_code = ClientDataManager.generate_client_script()
        
        from flask import Response
        response = Response(js_code, mimetype='application/javascript')
        response.headers['Cache-Control'] = 'public, max-age=3600'
        return response
        
    except Exception as e:
        current_app.logger.error(f"Client data manager script error: {e}")
        return jsonify({'error': 'Failed to generate client data manager'}), 500

def _is_online() -> bool:
    """Check if application is online (simplified check)"""
    # In a real implementation, this could check network connectivity
    # For now, we'll assume online unless explicitly testing offline
    return True

def _calculate_dashboard_summary(vessels: list) -> dict:
    """Calculate dashboard summary from vessel list"""
    total_vessels = len(vessels)
    active_vessels = len([v for v in vessels if v.get('status') in ['arrived', 'berthed', 'operations_active']])
    completed_vessels = len([v for v in vessels if v.get('status') == 'operations_complete'])
    offline_vessels = len([v for v in vessels if v.get('offline_created')])
    
    # Calculate average progress
    vessels_with_progress = [v for v in vessels if v.get('progress_percentage') is not None]
    avg_progress = sum(v['progress_percentage'] for v in vessels_with_progress) / len(vessels_with_progress) if vessels_with_progress else 0
    
    return {
        'total_vessels': total_vessels,
        'active_vessels': active_vessels,
        'completed_vessels': completed_vessels,
        'offline_vessels': offline_vessels,
        'average_progress': round(avg_progress, 1),
        'data_status': 'fresh',
        'is_offline_mode': False
    }