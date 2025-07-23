/**
 * Offline Cargo Tally Widget System
 * Real-time cargo tracking widgets with offline support
 */

class CargoTallyWidget {
    constructor(containerId, vesselId, options = {}) {
        this.containerId = containerId;
        this.vesselId = vesselId;
        this.isOfflineId = String(vesselId).startsWith('offline_');
        this.options = {
            autoRefresh: true,
            refreshInterval: 10000, // 10 seconds
            allowInput: true,
            showHistory: true,
            maxHistoryItems: 10,
            ...options
        };
        
        this.tallies = [];
        this.isLoading = false;
        this.lastUpdate = null;
        this.refreshTimer = null;
        
        this.init();
    }
    
    init() {
        this.render();
        this.setupEventListeners();
        this.loadTallies();
        
        if (this.options.autoRefresh) {
            this.startAutoRefresh();
        }
        
        console.log(`✅ Cargo tally widget initialized for vessel ${this.vesselId}`);
    }
    
    render() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error(`Container ${this.containerId} not found`);
            return;
        }
        
        container.innerHTML = `
            <div class="cargo-tally-widget">
                <!-- Widget Header -->
                <div class="widget-header">
                    <div class="widget-title">
                        <i class="fas fa-boxes"></i>
                        <span>Cargo Tally</span>
                        <div class="status-indicator" id="tally-status-${this.containerId}">
                            <i class="fas fa-circle"></i>
                        </div>
                    </div>
                    <div class="widget-actions">
                        <button class="btn-refresh" id="refresh-${this.containerId}" title="Refresh">
                            <i class="fas fa-sync-alt"></i>
                        </button>
                        <button class="btn-settings" id="settings-${this.containerId}" title="Settings">
                            <i class="fas fa-cog"></i>
                        </button>
                    </div>
                </div>
                
                <!-- Quick Entry Form -->
                ${this.options.allowInput ? this.renderQuickEntry() : ''}
                
                <!-- Tally Summary -->
                <div class="tally-summary">
                    <div class="summary-item">
                        <span class="label">Loaded:</span>
                        <span class="value" id="loaded-count-${this.containerId}">0</span>
                    </div>
                    <div class="summary-item">
                        <span class="label">Discharged:</span>
                        <span class="value" id="discharged-count-${this.containerId}">0</span>
                    </div>
                    <div class="summary-item">
                        <span class="label">Net:</span>
                        <span class="value net-total" id="net-count-${this.containerId}">0</span>
                    </div>
                </div>
                
                <!-- Progress Bar -->
                <div class="progress-section">
                    <div class="progress-label">
                        <span>Vessel Progress</span>
                        <span class="progress-percentage" id="progress-${this.containerId}">0%</span>
                    </div>
                    <div class="progress-bar-container">
                        <div class="progress-bar" id="progress-bar-${this.containerId}" style="width: 0%"></div>
                    </div>
                </div>
                
                <!-- Recent Tallies -->
                ${this.options.showHistory ? this.renderHistorySection() : ''}
                
                <!-- Loading Overlay -->
                <div class="loading-overlay" id="loading-${this.containerId}" style="display: none;">
                    <div class="loading-spinner">
                        <i class="fas fa-spinner fa-spin"></i>
                        <span>Loading...</span>
                    </div>
                </div>
            </div>
        `;
        
        this.applyStyles();
    }
    
    renderQuickEntry() {
        return `
            <div class="quick-entry-form">
                <div class="form-row">
                    <select id="tally-type-${this.containerId}" class="tally-select">
                        <option value="loaded">Loaded</option>
                        <option value="discharged">Discharged</option>
                    </select>
                    <input type="number" id="tally-count-${this.containerId}" 
                           class="tally-input" placeholder="Count" min="1" max="999">
                    <input type="text" id="tally-location-${this.containerId}" 
                           class="tally-input" placeholder="Location">
                    <button id="add-tally-${this.containerId}" class="btn-add-tally">
                        <i class="fas fa-plus"></i>
                    </button>
                </div>
                <div class="form-row">
                    <input type="text" id="tally-notes-${this.containerId}" 
                           class="tally-input-full" placeholder="Notes (optional)">
                </div>
            </div>
        `;
    }
    
    renderHistorySection() {
        return `
            <div class="tally-history">
                <div class="history-header">
                    <span>Recent Tallies</span>
                    <span class="last-updated" id="last-updated-${this.containerId}">Never</span>
                </div>
                <div class="history-list" id="history-list-${this.containerId}">
                    <!-- History items will be populated dynamically -->
                </div>
            </div>
        `;
    }
    
    setupEventListeners() {
        // Add tally button
        const addButton = document.getElementById(`add-tally-${this.containerId}`);
        if (addButton) {
            addButton.addEventListener('click', () => this.addTally());
        }
        
        // Enter key on inputs
        const inputs = document.querySelectorAll(`#${this.containerId} input`);
        inputs.forEach(input => {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.addTally();
                }
            });
        });
        
        // Refresh button
        const refreshButton = document.getElementById(`refresh-${this.containerId}`);
        if (refreshButton) {
            refreshButton.addEventListener('click', () => this.loadTallies(true));
        }
        
        // Settings button
        const settingsButton = document.getElementById(`settings-${this.containerId}`);
        if (settingsButton) {
            settingsButton.addEventListener('click', () => this.showSettings());
        }
    }
    
    async loadTallies(force = false) {
        if (this.isLoading && !force) return;
        
        this.setLoading(true);
        this.updateStatusIndicator('loading');
        
        try {
            const url = `/offline-dashboard/vessel/${this.vesselId}/data`;
            const response = await fetch(url, { redirect: 'follow' });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                this.tallies = data.cargo_tallies || [];
                this.updateDisplay();
                this.updateStatusIndicator('synced');
                this.lastUpdate = new Date();
            } else {
                throw new Error(data.error || 'Failed to load tallies');
            }
            
        } catch (error) {
            console.error('Error loading tallies:', error);
            this.updateStatusIndicator('error');
            
            // Try to load from local cache
            await this.loadFromCache();
        } finally {
            this.setLoading(false);
        }
    }
    
    async loadFromCache() {
        if (window.offlineDataManager) {
            try {
                const cachedData = await window.offlineDataManager.getCachedCargoTallies(this.vesselId);
                if (cachedData && cachedData.length > 0) {
                    this.tallies = cachedData;
                    this.updateDisplay();
                    this.updateStatusIndicator('offline');
                    console.log('Loaded tallies from cache');
                }
            } catch (error) {
                console.error('Error loading from cache:', error);
            }
        }
    }
    
    async addTally() {
        const tallyType = document.getElementById(`tally-type-${this.containerId}`).value;
        const count = document.getElementById(`tally-count-${this.containerId}`).value;
        const location = document.getElementById(`tally-location-${this.containerId}`).value;
        const notes = document.getElementById(`tally-notes-${this.containerId}`).value;
        
        if (!count || count <= 0) {
            this.showMessage('Please enter a valid count', 'error');
            return;
        }
        
        const tallyData = {
            vessel_id: this.isOfflineId ? this.vesselId : parseInt(this.vesselId),
            tally_type: tallyType,
            cargo_count: parseInt(count),
            location: location || '',
            notes: notes || '',
            timestamp: new Date().toISOString(),
            shift_period: this.getCurrentShift()
        };
        
        try {
            // Add to UI immediately (optimistic update)
            this.addTallyToDisplay(tallyData);
            this.clearForm();
            this.updateStatusIndicator('syncing');
            
            if (navigator.onLine && !this.isOfflineId) {
                // Try server first
                const response = await fetch(`/api/vessels/${this.vesselId}/cargo-tally`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(tallyData),
                    redirect: 'follow'
                });
                
                if (response.ok) {
                    const result = await response.json();
                    this.updateVesselProgress(result.new_progress);
                    this.updateStatusIndicator('synced');
                    this.showMessage('Tally added successfully', 'success');
                } else {
                    throw new Error('Server update failed');
                }
            } else {
                // Add to sync queue
                if (window.VesselSyncHelper) {
                    window.VesselSyncHelper.syncCargoTally(tallyData);
                }
                this.updateStatusIndicator('offline');
                this.showMessage('Tally saved offline', 'info');
            }
            
        } catch (error) {
            console.error('Error adding tally:', error);
            
            // Add to sync queue for later
            if (window.VesselSyncHelper) {
                window.VesselSyncHelper.syncCargoTally(tallyData);
            }
            
            this.updateStatusIndicator('offline');
            this.showMessage('Tally saved offline', 'info');
        }
    }
    
    addTallyToDisplay(tallyData) {
        // Add to tallies array
        this.tallies.unshift({
            ...tallyData,
            id: Date.now(), // Temporary ID for display
            synced: false
        });
        
        // Limit history
        if (this.tallies.length > this.options.maxHistoryItems) {
            this.tallies = this.tallies.slice(0, this.options.maxHistoryItems);
        }
        
        this.updateDisplay();
    }
    
    updateDisplay() {
        this.updateSummary();
        this.updateHistory();
        this.updateLastUpdated();
    }
    
    updateSummary() {
        const loaded = this.tallies.filter(t => t.tally_type === 'loaded')
            .reduce((sum, t) => sum + (t.cargo_count || 0), 0);
        const discharged = this.tallies.filter(t => t.tally_type === 'discharged')
            .reduce((sum, t) => sum + (t.cargo_count || 0), 0);
        const net = loaded - discharged;
        
        document.getElementById(`loaded-count-${this.containerId}`).textContent = loaded;
        document.getElementById(`discharged-count-${this.containerId}`).textContent = discharged;
        document.getElementById(`net-count-${this.containerId}`).textContent = net;
        
        // Update net color
        const netElement = document.getElementById(`net-count-${this.containerId}`);
        netElement.className = `value net-total ${net >= 0 ? 'positive' : 'negative'}`;
    }
    
    updateHistory() {
        if (!this.options.showHistory) return;
        
        const historyList = document.getElementById(`history-list-${this.containerId}`);
        if (!historyList) return;
        
        if (this.tallies.length === 0) {
            historyList.innerHTML = '<div class="no-history">No tallies recorded yet</div>';
            return;
        }
        
        historyList.innerHTML = this.tallies.map(tally => `
            <div class="history-item ${tally.synced === false ? 'pending' : ''}">
                <div class="history-main">
                    <span class="tally-type ${tally.tally_type}">${tally.tally_type}</span>
                    <span class="tally-count">${tally.cargo_count}</span>
                    <span class="tally-location">${tally.location || 'No location'}</span>
                    <span class="tally-time">${this.formatTime(tally.timestamp)}</span>
                </div>
                ${tally.notes ? `<div class="tally-notes">${tally.notes}</div>` : ''}
                ${tally.synced === false ? '<div class="sync-pending"><i class="fas fa-clock"></i> Pending sync</div>' : ''}
            </div>
        `).join('');
    }
    
    updateVesselProgress(newProgress) {
        if (newProgress !== undefined && newProgress !== null) {
            const progressElement = document.getElementById(`progress-${this.containerId}`);
            const progressBar = document.getElementById(`progress-bar-${this.containerId}`);
            
            if (progressElement && progressBar) {
                progressElement.textContent = `${Math.round(newProgress)}%`;
                progressBar.style.width = `${newProgress}%`;
                
                // Update progress bar color based on completion
                progressBar.className = 'progress-bar';
                if (newProgress >= 100) {
                    progressBar.classList.add('complete');
                } else if (newProgress >= 75) {
                    progressBar.classList.add('high');
                } else if (newProgress >= 50) {
                    progressBar.classList.add('medium');
                }
            }
        }
    }
    
    updateLastUpdated() {
        const lastUpdatedElement = document.getElementById(`last-updated-${this.containerId}`);
        if (lastUpdatedElement) {
            if (this.lastUpdate) {
                lastUpdatedElement.textContent = this.formatTime(this.lastUpdate.toISOString());
            } else {
                lastUpdatedElement.textContent = 'Never';
            }
        }
    }
    
    updateStatusIndicator(status) {
        const indicator = document.getElementById(`tally-status-${this.containerId}`);
        if (!indicator) return;
        
        const statusMap = {
            'synced': { color: '#10b981', icon: 'fas fa-check-circle' },
            'syncing': { color: '#f59e0b', icon: 'fas fa-sync-alt fa-spin' },
            'offline': { color: '#6b7280', icon: 'fas fa-wifi-slash' },
            'loading': { color: '#3b82f6', icon: 'fas fa-spinner fa-spin' },
            'error': { color: '#ef4444', icon: 'fas fa-exclamation-triangle' }
        };
        
        const config = statusMap[status] || statusMap['error'];
        indicator.style.color = config.color;
        indicator.innerHTML = `<i class="${config.icon}"></i>`;
    }
    
    setLoading(loading) {
        this.isLoading = loading;
        const overlay = document.getElementById(`loading-${this.containerId}`);
        if (overlay) {
            overlay.style.display = loading ? 'flex' : 'none';
        }
        
        const refreshButton = document.getElementById(`refresh-${this.containerId}`);
        if (refreshButton) {
            const icon = refreshButton.querySelector('i');
            if (loading) {
                icon.classList.add('fa-spin');
            } else {
                icon.classList.remove('fa-spin');
            }
        }
    }
    
    clearForm() {
        document.getElementById(`tally-count-${this.containerId}`).value = '';
        document.getElementById(`tally-location-${this.containerId}`).value = '';
        document.getElementById(`tally-notes-${this.containerId}`).value = '';
        document.getElementById(`tally-count-${this.containerId}`).focus();
    }
    
    getCurrentShift() {
        const hour = new Date().getHours();
        if (hour >= 6 && hour < 14) return 'morning';
        if (hour >= 14 && hour < 22) return 'afternoon';
        return 'night';
    }
    
    formatTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        return date.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit',
            hour12: false
        });
    }
    
    showMessage(message, type = 'info') {
        // Simple message display (could be enhanced with toast notifications)
        console.log(`[${type.toUpperCase()}] ${message}`);
        
        // Create temporary message element
        const messageEl = document.createElement('div');
        messageEl.className = `tally-message message-${type}`;
        messageEl.textContent = message;
        
        const container = document.getElementById(this.containerId);
        container.appendChild(messageEl);
        
        // Remove after 3 seconds
        setTimeout(() => {
            if (messageEl.parentNode) {
                messageEl.remove();
            }
        }, 3000);
    }
    
    showSettings() {
        // Simple settings modal (could be enhanced)
        const settings = {
            autoRefresh: this.options.autoRefresh,
            refreshInterval: this.options.refreshInterval / 1000,
            maxHistoryItems: this.options.maxHistoryItems
        };
        
        console.log('Widget settings:', settings);
        // In a full implementation, this would show a settings modal
    }
    
    startAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
        }
        
        this.refreshTimer = setInterval(() => {
            if (navigator.onLine && !document.hidden) {
                this.loadTallies();
            }
        }, this.options.refreshInterval);
    }
    
    stopAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }
    
    destroy() {
        this.stopAutoRefresh();
        const container = document.getElementById(this.containerId);
        if (container) {
            container.innerHTML = '';
        }
    }
    
    applyStyles() {
        if (document.getElementById('cargo-tally-widget-styles')) {
            return; // Styles already applied
        }
        
        const styles = document.createElement('style');
        styles.id = 'cargo-tally-widget-styles';
        styles.textContent = `
            .cargo-tally-widget {
                background: white;
                border-radius: 0.5rem;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                position: relative;
                overflow: hidden;
            }
            
            .widget-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 1rem;
                border-bottom: 1px solid #e5e7eb;
                background: #f8fafc;
            }
            
            .widget-title {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                font-weight: 600;
                color: #374151;
            }
            
            .status-indicator {
                color: #10b981;
                font-size: 0.75rem;
            }
            
            .widget-actions {
                display: flex;
                gap: 0.25rem;
            }
            
            .widget-actions button {
                background: none;
                border: none;
                padding: 0.25rem;
                border-radius: 0.25rem;
                color: #6b7280;
                cursor: pointer;
                transition: all 0.2s;
            }
            
            .widget-actions button:hover {
                background: #e5e7eb;
                color: #374151;
            }
            
            .quick-entry-form {
                padding: 1rem;
                background: #fefefe;
                border-bottom: 1px solid #e5e7eb;
            }
            
            .form-row {
                display: flex;
                gap: 0.5rem;
                margin-bottom: 0.5rem;
            }
            
            .form-row:last-child {
                margin-bottom: 0;
            }
            
            .tally-select, .tally-input {
                padding: 0.5rem;
                border: 1px solid #d1d5db;
                border-radius: 0.375rem;
                font-size: 0.875rem;
            }
            
            .tally-select {
                min-width: 100px;
            }
            
            .tally-input {
                flex: 1;
                min-width: 60px;
            }
            
            .tally-input-full {
                flex: 1;
                padding: 0.5rem;
                border: 1px solid #d1d5db;
                border-radius: 0.375rem;
                font-size: 0.875rem;
            }
            
            .btn-add-tally {
                background: #3b82f6;
                color: white;
                border: none;
                padding: 0.5rem 0.75rem;
                border-radius: 0.375rem;
                cursor: pointer;
                transition: background 0.2s;
            }
            
            .btn-add-tally:hover {
                background: #2563eb;
            }
            
            .tally-summary {
                display: flex;
                justify-content: space-around;
                padding: 1rem;
                background: #f9fafb;
            }
            
            .summary-item {
                text-align: center;
            }
            
            .summary-item .label {
                display: block;
                font-size: 0.75rem;
                color: #6b7280;
                margin-bottom: 0.25rem;
            }
            
            .summary-item .value {
                display: block;
                font-size: 1.5rem;
                font-weight: bold;
                color: #374151;
            }
            
            .net-total.positive {
                color: #10b981;
            }
            
            .net-total.negative {
                color: #ef4444;
            }
            
            .progress-section {
                padding: 1rem;
            }
            
            .progress-label {
                display: flex;
                justify-content: space-between;
                margin-bottom: 0.5rem;
                font-size: 0.875rem;
                color: #374151;
            }
            
            .progress-bar-container {
                background: #e5e7eb;
                border-radius: 0.25rem;
                height: 0.5rem;
                overflow: hidden;
            }
            
            .progress-bar {
                height: 100%;
                background: #3b82f6;
                transition: all 0.3s ease;
            }
            
            .progress-bar.medium {
                background: #f59e0b;
            }
            
            .progress-bar.high {
                background: #10b981;
            }
            
            .progress-bar.complete {
                background: #059669;
            }
            
            .tally-history {
                border-top: 1px solid #e5e7eb;
            }
            
            .history-header {
                display: flex;
                justify-content: space-between;
                padding: 0.75rem 1rem;
                background: #f8fafc;
                font-size: 0.875rem;
                color: #374151;
                border-bottom: 1px solid #e5e7eb;
            }
            
            .last-updated {
                color: #6b7280;
                font-size: 0.75rem;
            }
            
            .history-list {
                max-height: 300px;
                overflow-y: auto;
            }
            
            .no-history {
                padding: 2rem;
                text-align: center;
                color: #6b7280;
                font-size: 0.875rem;
            }
            
            .history-item {
                padding: 0.75rem 1rem;
                border-bottom: 1px solid #f3f4f6;
            }
            
            .history-item:last-child {
                border-bottom: none;
            }
            
            .history-item.pending {
                background: #fef3c7;
                border-left: 3px solid #f59e0b;
            }
            
            .history-main {
                display: flex;
                align-items: center;
                gap: 0.75rem;
                font-size: 0.875rem;
            }
            
            .tally-type {
                padding: 0.125rem 0.5rem;
                border-radius: 0.25rem;
                font-size: 0.75rem;
                font-weight: 500;
                text-transform: uppercase;
            }
            
            .tally-type.loaded {
                background: #d1fae5;
                color: #065f46;
            }
            
            .tally-type.discharged {
                background: #fee2e2;
                color: #991b1b;
            }
            
            .tally-count {
                font-weight: 600;
                color: #374151;
            }
            
            .tally-location {
                color: #6b7280;
                flex: 1;
            }
            
            .tally-time {
                color: #9ca3af;
                font-size: 0.75rem;
            }
            
            .tally-notes {
                margin-top: 0.25rem;
                font-size: 0.75rem;
                color: #6b7280;
                font-style: italic;
            }
            
            .sync-pending {
                margin-top: 0.25rem;
                font-size: 0.75rem;
                color: #92400e;
                display: flex;
                align-items: center;
                gap: 0.25rem;
            }
            
            .loading-overlay {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(255, 255, 255, 0.9);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10;
            }
            
            .loading-spinner {
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 0.5rem;
                color: #6b7280;
            }
            
            .tally-message {
                position: absolute;
                top: 1rem;
                right: 1rem;
                padding: 0.5rem 1rem;
                border-radius: 0.375rem;
                font-size: 0.875rem;
                z-index: 20;
                animation: slideIn 0.3s ease;
            }
            
            .message-success {
                background: #d1fae5;
                color: #065f46;
                border: 1px solid #a7f3d0;
            }
            
            .message-error {
                background: #fee2e2;
                color: #991b1b;
                border: 1px solid #fca5a5;
            }
            
            .message-info {
                background: #dbeafe;
                color: #1e40af;
                border: 1px solid #93c5fd;
            }
            
            @keyframes slideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
        `;
        
        document.head.appendChild(styles);
    }
}

// Factory function for easy widget creation
window.createCargoTallyWidget = function(containerId, vesselId, options) {
    return new CargoTallyWidget(containerId, vesselId, options);
};

// Auto-initialize widgets on page load
document.addEventListener('DOMContentLoaded', function() {
    // Find all elements with data-cargo-tally-widget attribute
    const widgetElements = document.querySelectorAll('[data-cargo-tally-widget]');
    
    widgetElements.forEach(element => {
        const vesselId = element.getAttribute('data-vessel-id');
        const options = {};
        
        // Parse options from data attributes
        if (element.hasAttribute('data-auto-refresh')) {
            options.autoRefresh = element.getAttribute('data-auto-refresh') === 'true';
        }
        if (element.hasAttribute('data-allow-input')) {
            options.allowInput = element.getAttribute('data-allow-input') === 'true';
        }
        if (element.hasAttribute('data-show-history')) {
            options.showHistory = element.getAttribute('data-show-history') === 'true';
        }
        
        if (vesselId) {
            new CargoTallyWidget(element.id, vesselId, options);
        }
    });
});

console.log('✅ Cargo Tally Widget System loaded');