"""
Offline Data Manager
Handles local data storage and retrieval for offline dashboard functionality
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

class DataStatus(Enum):
    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"
    OFFLINE_ONLY = "offline_only"

class OfflineDataManager:
    """Manages offline data storage and retrieval for dashboard operations"""
    
    def __init__(self):
        self.cache_duration = {
            'vessels': 300,  # 5 minutes
            'cargo_tallies': 60,  # 1 minute (more frequent for real-time data)
            'users': 3600,  # 1 hour
            'sync_status': 30  # 30 seconds
        }
        
    def cache_vessel_data(self, vessels: List[Dict], source: str = "server") -> bool:
        """Cache vessel data for offline access"""
        try:
            cache_data = {
                'vessels': vessels,
                'timestamp': datetime.utcnow().isoformat(),
                'source': source,
                'count': len(vessels)
            }
            
            # In a real application, this would use IndexedDB or similar
            # For now, we'll simulate with in-memory storage
            return self._store_cache_data('vessels', cache_data)
            
        except Exception as e:
            print(f"Error caching vessel data: {e}")
            return False
    
    def get_cached_vessels(self, include_stale: bool = True) -> Dict[str, Any]:
        """Retrieve cached vessel data"""
        try:
            cached_data = self._get_cache_data('vessels')
            if not cached_data:
                return {
                    'vessels': [],
                    'status': DataStatus.EXPIRED,
                    'last_updated': None,
                    'count': 0
                }
            
            status = self._get_data_status('vessels', cached_data['timestamp'])
            
            if status == DataStatus.EXPIRED and not include_stale:
                return {
                    'vessels': [],
                    'status': status,
                    'last_updated': cached_data['timestamp'],
                    'count': 0
                }
            
            return {
                'vessels': cached_data['vessels'],
                'status': status,
                'last_updated': cached_data['timestamp'],
                'count': cached_data['count'],
                'source': cached_data.get('source', 'unknown')
            }
            
        except Exception as e:
            print(f"Error retrieving cached vessels: {e}")
            return {
                'vessels': [],
                'status': DataStatus.EXPIRED,
                'last_updated': None,
                'count': 0
            }
    
    def cache_cargo_tallies(self, vessel_id: int, tallies: List[Dict]) -> bool:
        """Cache cargo tally data for specific vessel"""
        try:
            cache_key = f'cargo_tallies_{vessel_id}'
            cache_data = {
                'vessel_id': vessel_id,
                'tallies': tallies,
                'timestamp': datetime.utcnow().isoformat(),
                'count': len(tallies)
            }
            
            return self._store_cache_data(cache_key, cache_data)
            
        except Exception as e:
            print(f"Error caching cargo tallies: {e}")
            return False
    
    def get_cached_cargo_tallies(self, vessel_id: int) -> Dict[str, Any]:
        """Retrieve cached cargo tally data for vessel"""
        try:
            cache_key = f'cargo_tallies_{vessel_id}'
            cached_data = self._get_cache_data(cache_key)
            
            if not cached_data:
                return {
                    'tallies': [],
                    'status': DataStatus.EXPIRED,
                    'vessel_id': vessel_id,
                    'count': 0
                }
            
            status = self._get_data_status('cargo_tallies', cached_data['timestamp'])
            
            return {
                'tallies': cached_data['tallies'],
                'status': status,
                'vessel_id': vessel_id,
                'last_updated': cached_data['timestamp'],
                'count': cached_data['count']
            }
            
        except Exception as e:
            print(f"Error retrieving cached cargo tallies: {e}")
            return {
                'tallies': [],
                'status': DataStatus.EXPIRED,
                'vessel_id': vessel_id,
                'count': 0
            }
    
    def add_offline_vessel(self, vessel_data: Dict) -> str:
        """Add a vessel created offline"""
        try:
            vessel_data['offline_created'] = True
            vessel_data['offline_id'] = self._generate_offline_id()
            vessel_data['created_at'] = datetime.utcnow().isoformat()
            vessel_data['status'] = vessel_data.get('status', 'expected')
            
            # Store in offline vessels cache
            offline_vessels = self._get_cache_data('offline_vessels') or {'vessels': []}
            offline_vessels['vessels'].append(vessel_data)
            offline_vessels['timestamp'] = datetime.utcnow().isoformat()
            offline_vessels['count'] = len(offline_vessels['vessels'])
            
            self._store_cache_data('offline_vessels', offline_vessels)
            
            return vessel_data['offline_id']
            
        except Exception as e:
            print(f"Error adding offline vessel: {e}")
            return None
    
    def get_offline_vessels(self) -> List[Dict]:
        """Get vessels created while offline"""
        try:
            cached_data = self._get_cache_data('offline_vessels')
            if cached_data:
                return cached_data.get('vessels', [])
            return []
            
        except Exception as e:
            print(f"Error retrieving offline vessels: {e}")
            return []
    
    def merge_offline_and_server_vessels(self, server_vessels: List[Dict]) -> List[Dict]:
        """Merge offline-created vessels with server data"""
        try:
            offline_vessels = self.get_offline_vessels()
            
            # Create a combined list
            merged_vessels = server_vessels.copy()
            
            # Add offline vessels that haven't been synced yet
            for offline_vessel in offline_vessels:
                # Check if this offline vessel has been synced (has a real ID)
                if not offline_vessel.get('synced', False):
                    merged_vessels.append(offline_vessel)
            
            # Sort by creation date, newest first
            merged_vessels.sort(
                key=lambda v: v.get('created_at', '1970-01-01T00:00:00'),
                reverse=True
            )
            
            return merged_vessels
            
        except Exception as e:
            print(f"Error merging vessel data: {e}")
            return server_vessels
    
    def update_vessel_progress(self, vessel_id: str, progress: float, is_offline_id: bool = False) -> bool:
        """Update vessel progress in local cache"""
        try:
            if is_offline_id:
                # Update offline vessel
                offline_data = self._get_cache_data('offline_vessels')
                if offline_data:
                    for vessel in offline_data['vessels']:
                        if vessel.get('offline_id') == vessel_id:
                            vessel['progress_percentage'] = progress
                            vessel['updated_at'] = datetime.utcnow().isoformat()
                            if progress >= 100:
                                vessel['status'] = 'operations_complete'
                            elif progress > 0:
                                vessel['status'] = 'operations_active'
                            break
                    self._store_cache_data('offline_vessels', offline_data)
                    return True
            else:
                # Update cached server vessel
                vessel_cache = self._get_cache_data('vessels')
                if vessel_cache:
                    for vessel in vessel_cache['vessels']:
                        if vessel.get('id') == int(vessel_id):
                            vessel['progress_percentage'] = progress
                            vessel['updated_at'] = datetime.utcnow().isoformat()
                            if progress >= 100:
                                vessel['status'] = 'operations_complete'
                            elif progress > 0:
                                vessel['status'] = 'operations_active'
                            break
                    self._store_cache_data('vessels', vessel_cache)
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error updating vessel progress: {e}")
            return False
    
    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get dashboard summary data for offline display"""
        try:
            vessel_data = self.get_cached_vessels()
            vessels = vessel_data['vessels']
            offline_vessels = self.get_offline_vessels()
            
            # Combine for analysis
            all_vessels = self.merge_offline_and_server_vessels(vessels)
            
            # Calculate statistics
            total_vessels = len(all_vessels)
            active_vessels = len([v for v in all_vessels if v.get('status') in ['arrived', 'berthed', 'operations_active']])
            completed_vessels = len([v for v in all_vessels if v.get('status') == 'operations_complete'])
            
            # Calculate average progress
            vessels_with_progress = [v for v in all_vessels if v.get('progress_percentage') is not None]
            avg_progress = sum(v['progress_percentage'] for v in vessels_with_progress) / len(vessels_with_progress) if vessels_with_progress else 0
            
            # Recent activity
            recent_vessels = [v for v in all_vessels if self._is_recent(v.get('updated_at', v.get('created_at')))]
            
            return {
                'total_vessels': total_vessels,
                'active_vessels': active_vessels,
                'completed_vessels': completed_vessels,
                'offline_vessels': len(offline_vessels),
                'average_progress': round(avg_progress, 1),
                'recent_activity': len(recent_vessels),
                'data_status': vessel_data['status'],
                'last_updated': vessel_data['last_updated'],
                'is_offline_mode': vessel_data['status'] in [DataStatus.STALE, DataStatus.EXPIRED, DataStatus.OFFLINE_ONLY]
            }
            
        except Exception as e:
            print(f"Error generating dashboard summary: {e}")
            return {
                'total_vessels': 0,
                'active_vessels': 0,
                'completed_vessels': 0,
                'offline_vessels': 0,
                'average_progress': 0,
                'recent_activity': 0,
                'data_status': DataStatus.EXPIRED,
                'last_updated': None,
                'is_offline_mode': True
            }
    
    def clear_cache(self, cache_type: str = None) -> bool:
        """Clear cached data"""
        try:
            if cache_type:
                return self._clear_cache_data(cache_type)
            else:
                # Clear all cache
                cache_types = ['vessels', 'offline_vessels', 'users', 'sync_status']
                for cache_type in cache_types:
                    self._clear_cache_data(cache_type)
                
                # Clear cargo tallies (multiple keys)
                # In a real implementation, this would iterate through IndexedDB
                for i in range(100):  # Assuming max 100 vessels
                    self._clear_cache_data(f'cargo_tallies_{i}')
                
                return True
                
        except Exception as e:
            print(f"Error clearing cache: {e}")
            return False
    
    def _store_cache_data(self, key: str, data: Dict) -> bool:
        """Store data in cache (simulated with in-memory storage)"""
        # In a real implementation, this would use IndexedDB
        if not hasattr(self, '_cache'):
            self._cache = {}
        
        self._cache[key] = data
        return True
    
    def _get_cache_data(self, key: str) -> Optional[Dict]:
        """Retrieve data from cache"""
        if not hasattr(self, '_cache'):
            self._cache = {}
        
        return self._cache.get(key)
    
    def _clear_cache_data(self, key: str) -> bool:
        """Clear specific cache data"""
        if not hasattr(self, '_cache'):
            self._cache = {}
        
        if key in self._cache:
            del self._cache[key]
        
        return True
    
    def _get_data_status(self, data_type: str, timestamp_str: str) -> DataStatus:
        """Determine the status of cached data"""
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            now = datetime.utcnow()
            age_seconds = (now - timestamp).total_seconds()
            
            cache_duration = self.cache_duration.get(data_type, 300)
            stale_threshold = cache_duration * 2  # Double the cache duration for stale
            
            if age_seconds <= cache_duration:
                return DataStatus.FRESH
            elif age_seconds <= stale_threshold:
                return DataStatus.STALE
            else:
                return DataStatus.EXPIRED
                
        except Exception:
            return DataStatus.EXPIRED
    
    def _generate_offline_id(self) -> str:
        """Generate a unique ID for offline-created records"""
        return f"offline_{int(datetime.utcnow().timestamp())}_{hash(str(datetime.utcnow().microsecond)) % 10000}"
    
    def _is_recent(self, timestamp_str: str, hours: int = 24) -> bool:
        """Check if a timestamp is recent (within specified hours)"""
        if not timestamp_str:
            return False
        
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            return timestamp >= cutoff
        except:
            return False

class ClientDataManager:
    """Client-side data management for offline dashboard"""
    
    @staticmethod
    def generate_client_script() -> str:
        """Generate JavaScript for client-side offline data management"""
        return '''
        class ClientOfflineDataManager {
            constructor() {
                this.dbName = 'StevedoresDashboard';
                this.dbVersion = 1;
                this.db = null;
                this.cacheDuration = {
                    vessels: 5 * 60 * 1000,      // 5 minutes
                    cargo_tallies: 60 * 1000,    // 1 minute
                    dashboard_summary: 30 * 1000  // 30 seconds
                };
                
                this.initDB();
            }
            
            async initDB() {
                return new Promise((resolve, reject) => {
                    const request = indexedDB.open(this.dbName, this.dbVersion);
                    
                    request.onerror = () => reject(request.error);
                    request.onsuccess = () => {
                        this.db = request.result;
                        resolve(this.db);
                    };
                    
                    request.onupgradeneeded = (event) => {
                        const db = event.target.result;
                        
                        // Create object stores
                        if (!db.objectStoreNames.contains('vessels')) {
                            const vesselStore = db.createObjectStore('vessels', { keyPath: 'id' });
                            vesselStore.createIndex('status', 'status', { unique: false });
                            vesselStore.createIndex('updated_at', 'updated_at', { unique: false });
                        }
                        
                        if (!db.objectStoreNames.contains('cargo_tallies')) {
                            const tallyStore = db.createObjectStore('cargo_tallies', { keyPath: 'id' });
                            tallyStore.createIndex('vessel_id', 'vessel_id', { unique: false });
                            tallyStore.createIndex('timestamp', 'timestamp', { unique: false });
                        }
                        
                        if (!db.objectStoreNames.contains('cache_metadata')) {
                            db.createObjectStore('cache_metadata', { keyPath: 'key' });
                        }
                        
                        if (!db.objectStoreNames.contains('offline_data')) {
                            db.createObjectStore('offline_data', { keyPath: 'id' });
                        }
                    };
                });
            }
            
            async cacheVessels(vessels, source = 'server') {
                try {
                    const transaction = this.db.transaction(['vessels', 'cache_metadata'], 'readwrite');
                    const vesselStore = transaction.objectStore('vessels');
                    const metaStore = transaction.objectStore('cache_metadata');
                    
                    // Clear existing vessels if from server
                    if (source === 'server') {
                        await vesselStore.clear();
                    }
                    
                    // Add vessels
                    for (const vessel of vessels) {
                        await vesselStore.put(vessel);
                    }
                    
                    // Update metadata
                    await metaStore.put({
                        key: 'vessels_cache',
                        timestamp: Date.now(),
                        source: source,
                        count: vessels.length
                    });
                    
                    console.log(`Cached ${vessels.length} vessels from ${source}`);
                    return true;
                    
                } catch (error) {
                    console.error('Error caching vessels:', error);
                    return false;
                }
            }
            
            async getCachedVessels(includeStale = true) {
                try {
                    const transaction = this.db.transaction(['vessels', 'cache_metadata'], 'readonly');
                    const vesselStore = transaction.objectStore('vessels');
                    const metaStore = transaction.objectStore('cache_metadata');
                    
                    // Get metadata
                    const metadata = await this.getFromStore(metaStore, 'vessels_cache');
                    const vessels = await this.getAllFromStore(vesselStore);
                    
                    const status = this.getDataStatus('vessels', metadata?.timestamp);
                    
                    if (status === 'expired' && !includeStale) {
                        return {
                            vessels: [],
                            status: status,
                            lastUpdated: metadata?.timestamp,
                            count: 0
                        };
                    }
                    
                    return {
                        vessels: vessels || [],
                        status: status,
                        lastUpdated: metadata?.timestamp,
                        count: vessels?.length || 0,
                        source: metadata?.source || 'unknown'
                    };
                    
                } catch (error) {
                    console.error('Error getting cached vessels:', error);
                    return {
                        vessels: [],
                        status: 'error',
                        lastUpdated: null,
                        count: 0
                    };
                }
            }
            
            async addOfflineVessel(vesselData) {
                try {
                    vesselData.offline_created = true;
                    vesselData.offline_id = this.generateOfflineId();
                    vesselData.created_at = new Date().toISOString();
                    vesselData.status = vesselData.status || 'expected';
                    
                    const transaction = this.db.transaction(['offline_data'], 'readwrite');
                    const store = transaction.objectStore('offline_data');
                    
                    await store.put({
                        id: vesselData.offline_id,
                        type: 'vessel',
                        data: vesselData,
                        created_at: Date.now()
                    });
                    
                    console.log('Added offline vessel:', vesselData.offline_id);
                    return vesselData.offline_id;
                    
                } catch (error) {
                    console.error('Error adding offline vessel:', error);
                    return null;
                }
            }
            
            async getOfflineVessels() {
                try {
                    const transaction = this.db.transaction(['offline_data'], 'readonly');
                    const store = transaction.objectStore('offline_data');
                    const allOfflineData = await this.getAllFromStore(store);
                    
                    return allOfflineData
                        .filter(item => item.type === 'vessel')
                        .map(item => item.data);
                        
                } catch (error) {
                    console.error('Error getting offline vessels:', error);
                    return [];
                }
            }
            
            async getDashboardSummary() {
                try {
                    const vesselData = await this.getCachedVessels();
                    const offlineVessels = await this.getOfflineVessels();
                    
                    // Merge data
                    const allVessels = [...vesselData.vessels, ...offlineVessels];
                    
                    // Calculate statistics
                    const totalVessels = allVessels.length;
                    const activeVessels = allVessels.filter(v => 
                        ['arrived', 'berthed', 'operations_active'].includes(v.status)
                    ).length;
                    const completedVessels = allVessels.filter(v => v.status === 'operations_complete').length;
                    
                    const avgProgress = allVessels.length > 0 ?
                        allVessels.reduce((sum, v) => sum + (v.progress_percentage || 0), 0) / allVessels.length : 0;
                    
                    return {
                        total_vessels: totalVessels,
                        active_vessels: activeVessels,
                        completed_vessels: completedVessels,
                        offline_vessels: offlineVessels.length,
                        average_progress: Math.round(avgProgress * 10) / 10,
                        data_status: vesselData.status,
                        last_updated: vesselData.lastUpdated,
                        is_offline_mode: ['stale', 'expired', 'error'].includes(vesselData.status)
                    };
                    
                } catch (error) {
                    console.error('Error generating dashboard summary:', error);
                    return {
                        total_vessels: 0,
                        active_vessels: 0,
                        completed_vessels: 0,
                        offline_vessels: 0,
                        average_progress: 0,
                        data_status: 'error',
                        last_updated: null,
                        is_offline_mode: true
                    };
                }
            }
            
            getDataStatus(dataType, timestamp) {
                if (!timestamp) return 'expired';
                
                const age = Date.now() - timestamp;
                const cacheDuration = this.cacheDuration[dataType] || 5 * 60 * 1000;
                const staleThreshold = cacheDuration * 2;
                
                if (age <= cacheDuration) return 'fresh';
                else if (age <= staleThreshold) return 'stale';
                else return 'expired';
            }
            
            generateOfflineId() {
                return `offline_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            }
            
            // Helper methods for IndexedDB operations
            getFromStore(store, key) {
                return new Promise((resolve, reject) => {
                    const request = store.get(key);
                    request.onsuccess = () => resolve(request.result);
                    request.onerror = () => reject(request.error);
                });
            }
            
            getAllFromStore(store) {
                return new Promise((resolve, reject) => {
                    const request = store.getAll();
                    request.onsuccess = () => resolve(request.result);
                    request.onerror = () => reject(request.error);
                });
            }
        }
        
        // Initialize global offline data manager
        window.offlineDataManager = new ClientOfflineDataManager();
        console.log('✅ Client Offline Data Manager initialized');
        '''