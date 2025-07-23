/**
 * Client-Side Sync Manager
 * Handles offline/online data synchronization for maritime operations
 */

class ClientSyncManager {
    constructor() {
        this.isOnline = navigator.onLine;
        this.syncQueue = this.loadSyncQueue();
        this.syncInProgress = false;
        this.syncInterval = 30000; // 30 seconds
        this.maxRetries = 3;
        this.lastSyncAttempt = null;
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Start background sync scheduler
        this.startSyncScheduler();
        
        console.log('Client Sync Manager initialized');
    }
    
    setupEventListeners() {
        // Network status change events
        window.addEventListener('online', () => {
            console.log('Network: Online');
            this.isOnline = true;
            this.updateNetworkStatus('online');
            this.triggerSync();
        });
        
        window.addEventListener('offline', () => {
            console.log('Network: Offline');
            this.isOnline = false;
            this.updateNetworkStatus('offline');
        });
        
        // Page visibility changes (for background sync)
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && this.isOnline) {
                this.triggerSync();
            }
        });
        
        // Before page unload (save sync queue)
        window.addEventListener('beforeunload', () => {
            this.saveSyncQueue();
        });
    }
    
    addToSyncQueue(table, operation, data, id = null) {
        const syncRecord = {
            id: id || this.generateSyncId(),
            table: table,
            operation: operation, // create, update, delete
            data: data,
            timestamp: new Date().toISOString(),
            retryCount: 0,
            status: 'pending',
            clientHash: this.calculateHash(data)
        };
        
        // Remove existing record with same ID
        this.syncQueue = this.syncQueue.filter(record => record.id !== syncRecord.id);
        this.syncQueue.push(syncRecord);
        
        // Save to localStorage
        this.saveSyncQueue();
        
        // Trigger sync if online
        if (this.isOnline) {
            this.triggerSync();
        }
        
        console.log(`Added to sync queue: ${table} ${operation}`, syncRecord);
        return syncRecord.id;
    }
    
    async triggerSync() {
        if (this.syncInProgress || !this.isOnline || this.syncQueue.length === 0) {
            return;
        }
        
        const pendingRecords = this.syncQueue.filter(r => r.status === 'pending');
        if (pendingRecords.length === 0) {
            return;
        }
        
        console.log(`Starting sync of ${pendingRecords.length} records`);
        this.syncInProgress = true;
        this.lastSyncAttempt = new Date();
        
        try {
            // Process records in batches
            const batchSize = 5;
            for (let i = 0; i < pendingRecords.length; i += batchSize) {
                const batch = pendingRecords.slice(i, i + batchSize);
                await this.processSyncBatch(batch);
            }
            
            console.log('Sync completed successfully');
            this.dispatchSyncEvent('sync-completed', { success: true });
            
        } catch (error) {
            console.error('Sync failed:', error);
            this.handleSyncError(error);
            this.dispatchSyncEvent('sync-failed', { error: error.message });
        } finally {
            this.syncInProgress = false;
        }
    }
    
    async processSyncBatch(batch) {
        for (const record of batch) {
            try {
                record.status = 'syncing';
                
                // Send to server
                const result = await this.syncRecordToServer(record);
                
                if (result.success) {
                    record.status = 'synced';
                    record.serverHash = result.serverHash;
                } else if (result.conflict) {
                    record.status = 'conflict';
                    record.conflictData = result.serverData;
                    this.handleConflict(record);
                } else {
                    throw new Error(result.error || 'Unknown sync error');
                }
                
            } catch (error) {
                record.retryCount++;
                if (record.retryCount >= this.maxRetries) {
                    record.status = 'error';
                    console.error(`Max retries reached for record ${record.id}:`, error);
                } else {
                    record.status = 'pending';
                    console.warn(`Sync retry ${record.retryCount} for record ${record.id}:`, error);
                }
            }
        }
        
        // Save updated queue
        this.saveSyncQueue();
    }
    
    async syncRecordToServer(record) {
        const endpoint = `/sync/queue`;
        
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                table: record.table,
                operation: record.operation,
                data: record.data,
                id: record.id
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        return result;
    }
    
    async updateNetworkStatus(status) {
        try {
            await fetch('/sync/network-status', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ status: status })
            });
        } catch (error) {
            console.warn('Failed to update network status:', error);
        }
    }
    
    async getSyncStatus() {
        try {
            const response = await fetch('/sync/status', { redirect: 'follow' });
            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.warn('Failed to get sync status:', error);
        }
        return null;
    }
    
    async getConflicts() {
        try {
            const response = await fetch('/sync/conflicts', { redirect: 'follow' });
            if (response.ok) {
                const result = await response.json();
                return result.conflicts || [];
            }
        } catch (error) {
            console.warn('Failed to get conflicts:', error);
        }
        return [];
    }
    
    async resolveConflict(syncId, resolution = 'merge') {
        try {
            const response = await fetch('/sync/resolve-conflict', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    sync_id: syncId,
                    resolution: resolution
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                
                // Update local sync queue
                const record = this.syncQueue.find(r => r.id === syncId);
                if (record) {
                    record.data = result.resolved_data;
                    record.status = 'pending';
                    record.conflictData = null;
                }
                
                this.saveSyncQueue();
                this.triggerSync();
                
                return result;
            }
        } catch (error) {
            console.error('Failed to resolve conflict:', error);
        }
        return null;
    }
    
    handleConflict(record) {
        console.warn('Sync conflict detected:', record);
        
        // Dispatch conflict event for UI handling
        this.dispatchSyncEvent('sync-conflict', {
            syncId: record.id,
            table: record.table,
            clientData: record.data,
            serverData: record.conflictData
        });
        
        // Auto-resolve simple conflicts based on table type
        this.autoResolveConflict(record);
    }
    
    autoResolveConflict(record) {
        let autoResolution = null;
        
        // Auto-resolution strategies by table
        switch (record.table) {
            case 'cargo_tallies':
                // Cargo tallies are usually append-only, prefer client
                autoResolution = 'client_wins';
                break;
                
            case 'vessels':
                // Vessels prefer merge strategy
                autoResolution = 'merge';
                break;
                
            default:
                // Default to merge
                autoResolution = 'merge';
        }
        
        if (autoResolution) {
            setTimeout(() => {
                this.resolveConflict(record.id, autoResolution);
            }, 1000); // Brief delay for user notification
        }
    }
    
    handleSyncError(error) {
        // Check if it's a network error
        if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
            this.isOnline = false;
            this.updateNetworkStatus('offline');
        }
    }
    
    startSyncScheduler() {
        // Periodic sync attempts
        setInterval(() => {
            if (this.isOnline && !this.syncInProgress) {
                this.triggerSync();
            }
        }, this.syncInterval);
        
        // Initial sync if online
        if (this.isOnline) {
            setTimeout(() => this.triggerSync(), 1000);
        }
    }
    
    generateSyncId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
    }
    
    calculateHash(data) {
        // Simple hash function for conflict detection
        const str = JSON.stringify(data, Object.keys(data).sort());
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32-bit integer
        }
        return hash.toString(16);
    }
    
    loadSyncQueue() {
        try {
            const stored = localStorage.getItem('syncQueue');
            return stored ? JSON.parse(stored) : [];
        } catch (error) {
            console.warn('Failed to load sync queue:', error);
            return [];
        }
    }
    
    saveSyncQueue() {
        try {
            localStorage.setItem('syncQueue', JSON.stringify(this.syncQueue));
        } catch (error) {
            console.warn('Failed to save sync queue:', error);
        }
    }
    
    dispatchSyncEvent(eventType, data) {
        const event = new CustomEvent(eventType, { detail: data });
        window.dispatchEvent(event);
    }
    
    // Public API methods
    getSyncQueueStatus() {
        const stats = {
            total: this.syncQueue.length,
            pending: this.syncQueue.filter(r => r.status === 'pending').length,
            syncing: this.syncQueue.filter(r => r.status === 'syncing').length,
            synced: this.syncQueue.filter(r => r.status === 'synced').length,
            conflicts: this.syncQueue.filter(r => r.status === 'conflict').length,
            errors: this.syncQueue.filter(r => r.status === 'error').length
        };
        
        return {
            ...stats,
            isOnline: this.isOnline,
            syncInProgress: this.syncInProgress,
            lastSyncAttempt: this.lastSyncAttempt
        };
    }
    
    clearSyncedRecords() {
        const originalLength = this.syncQueue.length;
        this.syncQueue = this.syncQueue.filter(r => r.status !== 'synced');
        this.saveSyncQueue();
        
        const cleared = originalLength - this.syncQueue.length;
        console.log(`Cleared ${cleared} synced records`);
        return cleared;
    }
    
    forceSync() {
        if (this.syncInProgress) {
            console.warn('Sync already in progress');
            return false;
        }
        
        console.log('Forcing immediate sync');
        this.triggerSync();
        return true;
    }
}

// Vessel-specific sync helpers
class VesselSyncHelper {
    static syncVesselCreation(vesselData) {
        if (window.syncManager) {
            return window.syncManager.addToSyncQueue('vessels', 'create', vesselData);
        }
        console.warn('Sync manager not available');
        return null;
    }
    
    static syncVesselUpdate(vesselId, vesselData) {
        if (window.syncManager) {
            return window.syncManager.addToSyncQueue('vessels', 'update', { ...vesselData, id: vesselId }, vesselId);
        }
        console.warn('Sync manager not available');
        return null;
    }
    
    static syncCargoTally(tallyData) {
        if (window.syncManager) {
            return window.syncManager.addToSyncQueue('cargo_tallies', 'create', tallyData);
        }
        console.warn('Sync manager not available');
        return null;
    }
}

// Initialize sync manager when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Only initialize if user is authenticated (check for auth indicator)
    if (document.body.classList.contains('authenticated') || document.querySelector('[data-user-id]')) {
        window.syncManager = new ClientSyncManager();
        window.VesselSyncHelper = VesselSyncHelper;
        
        console.log('✅ Client sync manager initialized');
        
        // Setup sync status display
        setupSyncStatusDisplay();
    }
});

// Sync status display helpers
function setupSyncStatusDisplay() {
    // Create sync status indicator
    const syncIndicator = document.createElement('div');
    syncIndicator.id = 'sync-indicator';
    syncIndicator.className = 'sync-indicator';
    syncIndicator.innerHTML = `
        <div class="sync-status">
            <span class="sync-icon">🔄</span>
            <span class="sync-text">Synced</span>
            <span class="sync-count" style="display: none;">0</span>
        </div>
    `;
    
    // Add to page (in header or corner)
    const header = document.querySelector('header') || document.body;
    header.appendChild(syncIndicator);
    
    // Update indicator on sync events
    window.addEventListener('sync-completed', () => {
        updateSyncIndicator('synced', '✅');
    });
    
    window.addEventListener('sync-failed', () => {
        updateSyncIndicator('error', '❌');
    });
    
    window.addEventListener('sync-conflict', (event) => {
        updateSyncIndicator('conflict', '⚠️');
        showConflictNotification(event.detail);
    });
    
    // Update indicator every few seconds
    setInterval(updateSyncStatusIndicator, 5000);
}

function updateSyncStatusIndicator() {
    if (!window.syncManager) return;
    
    const status = window.syncManager.getSyncQueueStatus();
    const indicator = document.getElementById('sync-indicator');
    
    if (!indicator) return;
    
    const icon = indicator.querySelector('.sync-icon');
    const text = indicator.querySelector('.sync-text');
    const count = indicator.querySelector('.sync-count');
    
    if (status.syncInProgress) {
        icon.textContent = '🔄';
        text.textContent = 'Syncing...';
        indicator.className = 'sync-indicator syncing';
    } else if (status.conflicts > 0) {
        icon.textContent = '⚠️';
        text.textContent = 'Conflicts';
        count.textContent = status.conflicts;
        count.style.display = 'inline';
        indicator.className = 'sync-indicator conflict';
    } else if (status.errors > 0) {
        icon.textContent = '❌';
        text.textContent = 'Sync Error';
        count.textContent = status.errors;
        count.style.display = 'inline';
        indicator.className = 'sync-indicator error';
    } else if (status.pending > 0) {
        icon.textContent = '⏳';
        text.textContent = 'Pending';
        count.textContent = status.pending;
        count.style.display = 'inline';
        indicator.className = 'sync-indicator pending';
    } else {
        icon.textContent = status.isOnline ? '✅' : '📶';
        text.textContent = status.isOnline ? 'Synced' : 'Offline';
        count.style.display = 'none';
        indicator.className = `sync-indicator ${status.isOnline ? 'synced' : 'offline'}`;
    }
}

function showConflictNotification(conflictData) {
    // Simple conflict notification (could be enhanced with modal)
    const notification = document.createElement('div');
    notification.className = 'conflict-notification';
    notification.innerHTML = `
        <div class="conflict-content">
            <strong>Sync Conflict Detected</strong>
            <p>Data conflict in ${conflictData.table}. Auto-resolving...</p>
            <button onclick="this.parentElement.parentElement.remove()">Dismiss</button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

console.log('✅ Sync Manager loaded');