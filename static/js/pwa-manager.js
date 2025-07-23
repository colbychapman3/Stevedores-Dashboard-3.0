/**
 * Advanced PWA Manager for Stevedores Dashboard 3.0
 * Handles service worker registration, update management, and PWA features
 */

class PWAManager {
    constructor() {
        this.serviceWorker = null;
        this.deferredPrompt = null;
        this.isInstalled = false;
        this.swRegistration = null;
        this.updateAvailable = false;
        
        this.init();
    }
    
    async init() {
        console.log('🔧 Initializing Advanced PWA Manager...');
        
        // Check PWA support
        if (!this.isPWASupported()) {
            console.warn('PWA features not fully supported in this browser');
            return;
        }
        
        // Register service worker
        await this.registerServiceWorker();
        
        // Setup PWA event listeners
        this.setupEventListeners();
        
        // Check installation status
        this.checkInstallationStatus();
        
        // Setup periodic sync if supported
        this.setupPeriodicSync();
        
        console.log('✅ PWA Manager initialized successfully');
    }
    
    isPWASupported() {
        return 'serviceWorker' in navigator && 
               'caches' in window && 
               'indexedDB' in window;
    }
    
    async registerServiceWorker() {
        if (!('serviceWorker' in navigator)) {
            console.warn('Service Workers not supported');
            return false;
        }
        
        try {
            console.log('[PWA] Registering service worker...');
            
            this.swRegistration = await navigator.serviceWorker.register('/service-worker.js', {
                scope: '/',
                updateViaCache: 'none' // Always check for updates
            });
            
            console.log('[PWA] Service worker registered successfully:', this.swRegistration.scope);
            
            // Handle service worker updates
            this.swRegistration.addEventListener('updatefound', () => {
                console.log('[PWA] Service worker update found');
                this.handleServiceWorkerUpdate();
            });
            
            // Listen for controlling service worker change
            navigator.serviceWorker.addEventListener('controllerchange', () => {
                console.log('[PWA] New service worker activated, reloading...');
                window.location.reload();
            });
            
            // Listen for messages from service worker
            navigator.serviceWorker.addEventListener('message', event => {
                this.handleServiceWorkerMessage(event.data);
            });
            
            return true;
            
        } catch (error) {
            console.error('[PWA] Service worker registration failed:', error);
            return false;
        }
    }
    
    handleServiceWorkerUpdate() {
        const newWorker = this.swRegistration.installing;
        
        if (newWorker) {
            newWorker.addEventListener('statechange', () => {
                if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                    console.log('[PWA] New service worker installed, update available');
                    this.updateAvailable = true;
                    this.showUpdateNotification();
                }
            });
        }
    }
    
    showUpdateNotification() {
        // Create update notification
        const notification = document.createElement('div');
        notification.className = 'pwa-update-notification';
        notification.innerHTML = `
            <div class="notification-content">
                <div class="notification-icon">🔄</div>
                <div class="notification-text">
                    <strong>Update Available</strong>
                    <p>A new version of the app is available with improvements for maritime operations.</p>
                </div>
                <div class="notification-actions">
                    <button class="btn-update">Update Now</button>
                    <button class="btn-dismiss">Later</button>
                </div>
            </div>
        `;
        
        // Add styles
        this.injectUpdateStyles();
        
        // Add event listeners
        notification.querySelector('.btn-update').addEventListener('click', () => {
            this.applyUpdate();
        });
        
        notification.querySelector('.btn-dismiss').addEventListener('click', () => {
            notification.remove();
        });
        
        document.body.appendChild(notification);
        
        // Auto-remove after 10 seconds if not interacted with
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 10000);
    }
    
    async applyUpdate() {
        if (this.swRegistration && this.swRegistration.waiting) {
            console.log('[PWA] Applying service worker update...');
            this.swRegistration.waiting.postMessage({ type: 'SKIP_WAITING' });
        }
    }
    
    setupEventListeners() {
        // PWA install prompt
        window.addEventListener('beforeinstallprompt', (e) => {
            console.log('[PWA] Before install prompt event fired');
            e.preventDefault();
            this.deferredPrompt = e;
            this.showInstallButton();
        });
        
        // App installed
        window.addEventListener('appinstalled', (e) => {
            console.log('[PWA] App was installed');
            this.isInstalled = true;
            this.hideInstallButton();
            this.trackInstallation();
        });
        
        // Online/offline status
        window.addEventListener('online', () => {
            console.log('[PWA] App is online');
            this.handleOnlineStatus(true);
        });
        
        window.addEventListener('offline', () => {
            console.log('[PWA] App is offline');
            this.handleOnlineStatus(false);
        });
        
        // Visibility change for background sync
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && navigator.onLine) {
                this.triggerBackgroundSync();
            }
        });
    }
    
    showInstallButton() {
        // Create or show install button
        let installBtn = document.getElementById('pwa-install-btn');
        
        if (!installBtn) {
            installBtn = document.createElement('button');
            installBtn.id = 'pwa-install-btn';
            installBtn.className = 'pwa-install-button';
            installBtn.innerHTML = `
                <i class="fas fa-download"></i>
                Install App
            `;
            
            installBtn.addEventListener('click', () => {
                this.promptInstall();
            });
            
            // Add to header or appropriate location
            const header = document.querySelector('.dashboard-header') || document.body;
            header.appendChild(installBtn);
        }
        
        installBtn.style.display = 'block';
    }
    
    hideInstallButton() {
        const installBtn = document.getElementById('pwa-install-btn');
        if (installBtn) {
            installBtn.style.display = 'none';
        }
    }
    
    async promptInstall() {
        if (this.deferredPrompt) {
            console.log('[PWA] Showing install prompt');
            this.deferredPrompt.prompt();
            
            const { outcome } = await this.deferredPrompt.userChoice;
            console.log(`[PWA] User response to install prompt: ${outcome}`);
            
            this.deferredPrompt = null;
            
            if (outcome === 'accepted') {
                this.hideInstallButton();
            }
        }
    }
    
    checkInstallationStatus() {
        // Check if app is installed
        if (window.matchMedia('(display-mode: standalone)').matches ||
            window.navigator.standalone === true) {
            console.log('[PWA] App is running in installed mode');
            this.isInstalled = true;
            this.hideInstallButton();
        }
    }
    
    handleOnlineStatus(isOnline) {
        const statusIndicator = document.getElementById('connection-status');
        
        if (statusIndicator) {
            if (isOnline) {
                statusIndicator.textContent = 'Online';
                statusIndicator.className = 'status-online';
                
                // Trigger sync when coming back online
                this.triggerBackgroundSync();
            } else {
                statusIndicator.textContent = 'Offline';
                statusIndicator.className = 'status-offline';
            }
        }
        
        // Update PWA offline indicator
        this.updateOfflineBanner(!isOnline);
    }
    
    updateOfflineBanner(isOffline) {
        const offlineBanner = document.getElementById('offline-mode-banner');
        
        if (offlineBanner) {
            if (isOffline) {
                offlineBanner.classList.remove('hidden');
            } else {
                offlineBanner.classList.add('hidden');
            }
        }
    }
    
    async setupPeriodicSync() {
        if ('serviceWorker' in navigator && 'sync' in window.ServiceWorkerRegistration.prototype) {
            try {
                // Request persistent permission for background sync
                if ('permissions' in navigator) {
                    const permission = await navigator.permissions.query({
                        name: 'background-sync'
                    });
                    console.log(`[PWA] Background sync permission: ${permission.state}`);
                }
                
                // Setup periodic sync if supported
                if ('periodicSync' in window.ServiceWorkerRegistration.prototype) {
                    const status = await navigator.permissions.query({
                        name: 'periodic-background-sync'
                    });
                    
                    if (status.state === 'granted') {
                        await this.swRegistration.periodicSync.register('maritime-data-sync', {
                            minInterval: 12 * 60 * 60 * 1000 // 12 hours
                        });
                        console.log('[PWA] Periodic sync registered for maritime data');
                    }
                }
            } catch (error) {
                console.log('[PWA] Periodic sync not available:', error.message);
            }
        }
    }
    
    async triggerBackgroundSync() {
        if (this.swRegistration && 'sync' in window.ServiceWorkerRegistration.prototype) {
            try {
                // Register different sync types
                await this.swRegistration.sync.register('batch-sync');
                console.log('[PWA] Background sync triggered');
            } catch (error) {
                console.error('[PWA] Background sync registration failed:', error);
            }
        }
    }
    
    handleServiceWorkerMessage(data) {
        console.log('[PWA] Message from service worker:', data.type);
        
        switch (data.type) {
            case 'SW_ACTIVATED':
                console.log(`[PWA] Service worker v${data.version} activated`);
                break;
                
            case 'CARGO_TALLY_SYNC_COMPLETE':
                this.showSyncNotification('Cargo tallies synced', `${data.synced} items synchronized`);
                break;
                
            case 'VESSEL_DATA_SYNC_COMPLETE':
                this.showSyncNotification('Vessel data synced', `${data.synced} vessels updated`);
                break;
                
            case 'BATCH_SYNC_COMPLETE':
                const successCount = Object.values(data.results).filter(r => r.success).length;
                this.showSyncNotification('Sync complete', `${successCount}/4 operations successful`);
                break;
                
            case 'SW_ERROR':
                console.error('[PWA] Service worker error:', data.error);
                break;
                
            case 'EXPORT_REQUEST':
                this.handleExportRequest(data);
                break;
        }
    }
    
    showSyncNotification(title, message) {
        // Create temporary sync notification
        const notification = document.createElement('div');
        notification.className = 'pwa-sync-notification';
        notification.innerHTML = `
            <div class="sync-notification-content">
                <div class="sync-icon">✅</div>
                <div class="sync-text">
                    <strong>${title}</strong>
                    <p>${message}</p>
                </div>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
    
    handleExportRequest(data) {
        // Handle export request from notification
        console.log('[PWA] Export request received:', data);
        
        if (data.vessel_id) {
            // Trigger export for specific vessel
            const exportEvent = new CustomEvent('vessel-export', {
                detail: { vessel_id: data.vessel_id }
            });
            document.dispatchEvent(exportEvent);
        }
    }
    
    trackInstallation() {
        // Track PWA installation for analytics
        console.log('[PWA] Tracking app installation');
        
        // Could send analytics event here
        if (typeof gtag !== 'undefined') {
            gtag('event', 'pwa_install', {
                event_category: 'engagement',
                event_label: 'stevedores_dashboard'
            });
        }
    }
    
    injectUpdateStyles() {
        if (document.getElementById('pwa-update-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'pwa-update-styles';
        style.textContent = `
            .pwa-update-notification {
                position: fixed;
                top: 20px;
                right: 20px;
                background: white;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                max-width: 400px;
                z-index: 10000;
                border-left: 4px solid #3b82f6;
                animation: slideInRight 0.3s ease-out;
            }
            
            .notification-content {
                padding: 16px;
                display: flex;
                align-items: flex-start;
                gap: 12px;
            }
            
            .notification-icon {
                font-size: 24px;
                flex-shrink: 0;
            }
            
            .notification-text {
                flex: 1;
            }
            
            .notification-text strong {
                color: #1f2937;
                display: block;
                margin-bottom: 4px;
            }
            
            .notification-text p {
                color: #6b7280;
                font-size: 14px;
                margin: 0;
                line-height: 1.4;
            }
            
            .notification-actions {
                display: flex;
                gap: 8px;
                margin-top: 12px;
            }
            
            .btn-update {
                background: #3b82f6;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
            }
            
            .btn-dismiss {
                background: #f3f4f6;
                color: #374151;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
            }
            
            .pwa-install-button {
                background: #059669;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 14px;
                display: flex;
                align-items: center;
                gap: 8px;
                margin-left: 16px;
            }
            
            .pwa-sync-notification {
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: #10b981;
                color: white;
                padding: 12px 16px;
                border-radius: 6px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
                z-index: 10000;
                animation: slideInUp 0.3s ease-out;
            }
            
            .sync-notification-content {
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .sync-text strong {
                display: block;
                font-size: 14px;
            }
            
            .sync-text p {
                margin: 0;
                font-size: 12px;
                opacity: 0.9;
            }
            
            @keyframes slideInRight {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            
            @keyframes slideInUp {
                from { transform: translateY(100%); opacity: 0; }
                to { transform: translateY(0); opacity: 1; }
            }
        `;
        
        document.head.appendChild(style);
    }
    
    // Public API methods
    async checkForUpdates() {
        if (this.swRegistration) {
            await this.swRegistration.update();
        }
    }
    
    async clearCache() {
        if (this.swRegistration && this.swRegistration.active) {
            this.swRegistration.active.postMessage({ type: 'CLEAR_CACHE' });
        }
    }
    
    getInstallationStatus() {
        return {
            isInstalled: this.isInstalled,
            isStandalone: window.matchMedia('(display-mode: standalone)').matches,
            canInstall: !!this.deferredPrompt
        };
    }
}

// Initialize PWA Manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.pwaManager = new PWAManager();
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PWAManager;
}

console.log('✅ PWA Manager script loaded');