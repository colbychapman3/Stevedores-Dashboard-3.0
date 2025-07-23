// Stevedores Dashboard 3.0 - Advanced PWA Service Worker
// Critical for maritime operations where connectivity is unreliable
// Enhanced with background sync, smart caching, and offline-first strategies

const VERSION = '3.0.4';
const CACHE_NAME = `stevedores-dashboard-v${VERSION}`;
const RUNTIME_CACHE = `stevedores-runtime-v${VERSION}`;
const API_CACHE = `stevedores-api-v${VERSION}`;
const OFFLINE_URL = '/offline';

// Critical resources for offline functionality
const CRITICAL_CACHE_URLS = [
    '/',
    '/dashboard',
    '/offline',
    '/wizard',
    '/auth/login',
    '/manifest.json',
    '/static/js/cargo-tally-widgets.js',
    '/static/js/sync-manager.js',
    '/static/js/wizard.js',
    '/offline-dashboard/client-data-manager.js'
];

// Static resources with longer cache lifetime
const STATIC_CACHE_PATTERNS = [
    /^\/static\/.*\.(css|js|png|jpg|jpeg|gif|svg|woff|woff2|ico)$/,
    /^\/static\/icons\/.*$/
];

// API endpoints to cache with stale-while-revalidate
const API_CACHE_PATTERNS = [
    /^\/api\/vessels/,
    /^\/offline-dashboard\/dashboard-data/,
    /^\/offline-dashboard\/vessel\/.*\/data/,
    /^\/document\/process/
];

// Navigation patterns
const NAVIGATION_PATTERNS = [
    /^\/dashboard/,
    /^\/vessel\/\d+/,
    /^\/vessel\/offline_/,
    /^\/wizard/
];

// Install event - cache critical resources for offline operation
self.addEventListener('install', event => {
    console.log(`[SW] Installing service worker v${VERSION}...`);
    
    event.waitUntil(
        Promise.all([
            // Cache critical resources
            caches.open(CACHE_NAME).then(cache => {
                console.log('[SW] Caching critical resources for offline operation');
                return cache.addAll(CRITICAL_CACHE_URLS).catch(error => {
                    console.error('[SW] Failed to cache some critical resources:', error);
                    // Continue anyway - some resources might not exist yet
                    return Promise.resolve();
                });
            }),
            
            // Initialize other caches
            caches.open(RUNTIME_CACHE),
            caches.open(API_CACHE)
        ])
        .then(() => {
            console.log('[SW] Critical resources cached, activating immediately');
            // Force activation of new service worker for maritime urgency
            return self.skipWaiting();
        })
        .catch(error => {
            console.error('[SW] Installation failed:', error);
            throw error;
        })
    );
});

// Activate event - clean up old caches and take control
self.addEventListener('activate', event => {
    console.log(`[SW] Activating service worker v${VERSION}...`);
    
    const currentCaches = [CACHE_NAME, RUNTIME_CACHE, API_CACHE];
    
    event.waitUntil(
        Promise.all([
            // Clean up old caches
            caches.keys().then(cacheNames => {
                return Promise.all(
                    cacheNames.map(cacheName => {
                        if (!currentCaches.includes(cacheName)) {
                            console.log('[SW] Deleting outdated cache:', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            }),
            
            // Initialize offline data store if needed
            initializeOfflineData()
        ])
        .then(() => {
            console.log('[SW] Service worker activated and controlling all clients');
            // Take control of all clients immediately for maritime operations
            return self.clients.claim();
        })
        .then(() => {
            // Notify clients of activation
            return notifyClients({
                type: 'SW_ACTIVATED',
                version: VERSION,
                timestamp: new Date().toISOString()
            });
        })
    );
});

// Advanced fetch handler with multiple caching strategies
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Skip non-GET requests, external domains, and critical init endpoints
    if (request.method !== 'GET' || url.origin !== location.origin || url.pathname === '/init-database') {
        return;
    }
    
    // Route requests to appropriate handlers based on type
    if (isAPIRequest(url)) {
        event.respondWith(handleAPIRequest(request, url));
    } else if (isStaticResource(url)) {
        event.respondWith(handleStaticResource(request, url));
    } else if (isNavigationRequest(request, url)) {
        event.respondWith(handleNavigationRequest(request, url));
    } else {
        // Default: network first with cache fallback
        event.respondWith(handleGenericRequest(request, url));
    }
});

// Enhanced request type detection
function isAPIRequest(url) {
    return API_CACHE_PATTERNS.some(pattern => pattern.test(url.pathname));
}

function isStaticResource(url) {
    return STATIC_CACHE_PATTERNS.some(pattern => pattern.test(url.pathname));
}

function isNavigationRequest(request, url) {
    return request.mode === 'navigate' || 
           (request.method === 'GET' && 
            request.headers.get('accept')?.includes('text/html')) ||
           NAVIGATION_PATTERNS.some(pattern => pattern.test(url.pathname));
}

// Maritime-critical: Initialize offline data structures
async function initializeOfflineData() {
    try {
        // This would integrate with IndexedDB to ensure offline data integrity
        console.log('[SW] Initializing offline data structures for maritime operations');
        return Promise.resolve();
    } catch (error) {
        console.error('[SW] Failed to initialize offline data:', error);
        return Promise.resolve(); // Don't fail activation
    }
}

// Notify all clients of service worker events
async function notifyClients(message) {
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
        client.postMessage(message);
    });
}

// Advanced API request handler with stale-while-revalidate
async function handleAPIRequest(request, url) {
    const apiCache = await caches.open(API_CACHE);
    const runtimeCache = await caches.open(RUNTIME_CACHE);
    
    try {
        // For critical maritime data: network first with cache fallback
        if (url.pathname.includes('dashboard-data') || url.pathname.includes('vessel')) {
            return await networkFirstStrategy(request, apiCache, {
                timeout: 3000, // 3 second timeout for ship operations
                fallbackResponse: createOfflineAPIResponse()
            });
        }
        
        // For other API calls: stale-while-revalidate
        return await staleWhileRevalidateStrategy(request, apiCache);
        
    } catch (error) {
        console.error('[SW] API request handler failed:', error);
        return createOfflineAPIResponse();
    }
}

// Network-first strategy with timeout for critical operations
async function networkFirstStrategy(request, cache, options = {}) {
    const timeout = options.timeout || 5000;
    
    try {
        // Race network request against timeout
        const networkResponse = await Promise.race([
            fetch(request, { redirect: 'follow' }),
            new Promise((_, reject) => 
                setTimeout(() => reject(new Error('Network timeout')), timeout)
            )
        ]);
        
        if (networkResponse.ok) {
            // Cache fresh response
            cache.put(request.clone(), networkResponse.clone());
            
            // Add maritime-specific headers
            const response = networkResponse.clone();
            response.headers.set('sw-cache-status', 'network-fresh');
            response.headers.set('sw-timestamp', new Date().toISOString());
            
            return response;
        }
        
        throw new Error(`HTTP ${networkResponse.status}`);
        
    } catch (error) {
        console.log(`[SW] Network failed for ${request.url}, trying cache`);
        
        // Network failed, try cache
        const cachedResponse = await cache.match(request);
        if (cachedResponse) {
            const response = cachedResponse.clone();
            response.headers.set('sw-cache-status', 'cache-hit');
            return response;
        }
        
        // Return fallback or create offline response
        return options.fallbackResponse || createOfflineAPIResponse();
    }
}

// Stale-while-revalidate strategy for less critical data
async function staleWhileRevalidateStrategy(request, cache) {
    const cachedResponse = await cache.match(request);
    
    // Always try to fetch fresh data in background
    const fetchPromise = fetch(request, { redirect: 'follow' }).then(response => {
        if (response.ok) {
            cache.put(request.clone(), response.clone());
        }
        return response;
    }).catch(error => {
        console.log(`[SW] Background fetch failed for ${request.url}:`, error);
    });
    
    // Return cached data immediately if available
    if (cachedResponse) {
        // Non-blocking background update
        fetchPromise.catch(() => {}); // Ignore background failures
        
        const response = cachedResponse.clone();
        response.headers.set('sw-cache-status', 'stale-while-revalidate');
        return response;
    }
    
    // No cache available, wait for network
    try {
        const networkResponse = await fetchPromise;
        if (networkResponse && networkResponse.ok) {
            return networkResponse;
        }
    } catch (error) {
        // Ignore - will fall through to offline response
    }
    
    return createOfflineAPIResponse();
}

// Create consistent offline API responses
function createOfflineAPIResponse() {
    return new Response(
        JSON.stringify({ 
            success: false,
            error: 'Offline - data not available',
            offline: true,
            mode: 'offline',
            timestamp: new Date().toISOString(),
            sw_version: VERSION
        }), 
        {
            status: 503,
            statusText: 'Service Unavailable - Offline',
            headers: { 
                'Content-Type': 'application/json',
                'sw-cache-status': 'offline-fallback',
                'sw-offline': 'true'
            }
        }
    );
}

// Enhanced static resource handler with long-term caching
async function handleStaticResource(request, url) {
    const cache = await caches.open(CACHE_NAME);
    const runtimeCache = await caches.open(RUNTIME_CACHE);
    
    // For versioned static assets: cache first (immutable)
    if (url.pathname.includes('.js') || url.pathname.includes('.css') || 
        url.pathname.includes('/icons/')) {
        
        const cachedResponse = await cache.match(request);
        if (cachedResponse) {
            // Return cached version immediately for performance
            return cachedResponse;
        }
    }
    
    try {
        // Fetch from network
        const networkResponse = await fetch(request, { redirect: 'follow' });
        
        if (networkResponse.ok) {
            // Cache static resources for offline use
            const responseToCache = networkResponse.clone();
            
            // Use appropriate cache based on resource type
            if (url.pathname.includes('/icons/') || url.pathname.match(/\.(js|css|woff|woff2)$/)) {
                cache.put(request, responseToCache);
            } else {
                runtimeCache.put(request, responseToCache);
            }
        }
        
        return networkResponse;
        
    } catch (error) {
        console.log('[SW] Static resource network failed:', request.url);
        
        // Try fallback caches
        const cachedResponse = await cache.match(request) || 
                             await runtimeCache.match(request);
        
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // Return appropriate fallback based on resource type
        if (url.pathname.endsWith('.js')) {
            return new Response('// Offline fallback script\nconsole.log("Resource unavailable offline");', {
                status: 503,
                headers: { 'Content-Type': 'application/javascript' }
            });
        } else if (url.pathname.endsWith('.css')) {
            return new Response('/* Offline fallback styles */', {
                status: 503,
                headers: { 'Content-Type': 'text/css' }
            });
        }
        
        return new Response('Resource unavailable offline', {
            status: 503,
            headers: { 'Content-Type': 'text/plain' }
        });
    }
}

// Enhanced navigation handler for maritime PWA
async function handleNavigationRequest(request, url) {
    const cache = await caches.open(CACHE_NAME);
    const runtimeCache = await caches.open(RUNTIME_CACHE);
    
    try {
        // For critical pages: network first with fast timeout
        const timeoutPromise = new Promise((_, reject) => 
            setTimeout(() => reject(new Error('Navigation timeout')), 2000)
        );
        
        const networkResponse = await Promise.race([
            fetch(request, { redirect: 'follow' }),
            timeoutPromise
        ]);
        
        if (networkResponse.ok) {
            // Cache navigation responses for offline use
            runtimeCache.put(request, networkResponse.clone());
            return networkResponse;
        }
        
        throw new Error(`HTTP ${networkResponse.status}`);
        
    } catch (error) {
        console.log(`[SW] Navigation network failed for ${request.url}:`, error.message);
        
        // Try cached version first
        let cachedResponse = await runtimeCache.match(request) || 
                           await cache.match(request);
        
        if (cachedResponse) {
            console.log(`[SW] Serving cached navigation for ${request.url}`);
            return cachedResponse;
        }
        
        // For vessel pages, try to serve the generic vessel details page
        if (url.pathname.startsWith('/vessel/')) {
            cachedResponse = await runtimeCache.match('/vessel/details') ||
                           await cache.match('/vessel/details');
            if (cachedResponse) {
                return cachedResponse;
            }
        }
        
        // For dashboard routes, try to serve cached dashboard
        if (url.pathname.startsWith('/dashboard')) {
            cachedResponse = await runtimeCache.match('/dashboard') ||
                           await cache.match('/dashboard');
            if (cachedResponse) {
                return cachedResponse;
            }
        }
        
        // Last resort: offline page
        const offlineResponse = await cache.match(OFFLINE_URL);
        if (offlineResponse) {
            return offlineResponse;
        }
        
        // Create fallback offline page
        return createOfflineNavigationFallback();
    }
}

// Generic request handler for uncategorized requests
async function handleGenericRequest(request, url) {
    const runtimeCache = await caches.open(RUNTIME_CACHE);
    
    try {
        const networkResponse = await fetch(request, { redirect: 'follow' });
        
        if (networkResponse.ok) {
            // Cache for potential offline use
            runtimeCache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
        
    } catch (error) {
        console.log(`[SW] Generic request failed for ${request.url}`);
        
        // Try cache
        const cachedResponse = await runtimeCache.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // Return appropriate error
        return new Response('Request failed - offline', {
            status: 503,
            headers: { 'Content-Type': 'text/plain' }
        });
    }
}

// Create fallback offline navigation page
function createOfflineNavigationFallback() {
    const html = `
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Offline - Stevedores Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5; }
            .container { max-width: 500px; margin: 0 auto; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .icon { font-size: 4rem; color: #f59e0b; margin-bottom: 20px; }
            h1 { color: #1f2937; margin-bottom: 16px; }
            p { color: #6b7280; line-height: 1.6; }
            .button { display: inline-block; background: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">⚓</div>
            <h1>Offline Mode</h1>
            <p>You're currently offline. The Stevedores Dashboard is optimized for maritime operations with limited connectivity.</p>
            <p>Your work will be saved locally and synchronized when connection returns.</p>
            <a href="/dashboard" class="button">Return to Dashboard</a>
        </div>
        <script>
            // Auto-reload when connection returns
            window.addEventListener('online', () => {
                window.location.reload();
            });
        </script>
    </body>
    </html>
    `;
    
    return new Response(html, {
        status: 503,
        statusText: 'Offline',
        headers: { 'Content-Type': 'text/html' }
    });
}

// Enhanced background sync with retry logic and batching
self.addEventListener('sync', event => {
    console.log(`[SW] Background sync triggered: ${event.tag}`);
    
    // Handle different sync types for maritime operations
    switch (event.tag) {
        case 'cargo-tally-sync':
            event.waitUntil(syncCargoTallies());
            break;
        case 'vessel-data-sync':
            event.waitUntil(syncVesselData());
            break;
        case 'document-sync':
            event.waitUntil(syncDocuments());
            break;
        case 'wizard-data-sync':
            event.waitUntil(syncWizardData());
            break;
        case 'batch-sync':
            event.waitUntil(performBatchSync());
            break;
        default:
            console.warn(`[SW] Unknown sync tag: ${event.tag}`);
    }
});

// Advanced cargo tally sync with retry and error handling
async function syncCargoTallies() {
    console.log('[SW] Starting cargo tally sync...');
    
    try {
        // Get pending tallies from sync queue
        const response = await fetch('/sync/pending-cargo-tallies', { redirect: 'follow' });
        
        if (!response.ok) {
            throw new Error(`Failed to get pending tallies: ${response.status}`);
        }
        
        const { pending_tallies } = await response.json();
        
        if (!pending_tallies || pending_tallies.length === 0) {
            console.log('[SW] No cargo tallies to sync');
            return;
        }
        
        console.log(`[SW] Syncing ${pending_tallies.length} cargo tallies`);
        
        // Process tallies in batches to avoid overwhelming the server
        const batchSize = 5;
        let syncedCount = 0;
        let failedCount = 0;
        
        for (let i = 0; i < pending_tallies.length; i += batchSize) {
            const batch = pending_tallies.slice(i, i + batchSize);
            
            try {
                const batchResponse = await fetch('/sync/cargo-tallies-batch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tallies: batch }),
                    redirect: 'follow'
                });
                
                if (batchResponse.ok) {
                    syncedCount += batch.length;
                    console.log(`[SW] Synced batch of ${batch.length} tallies`);
                } else {
                    failedCount += batch.length;
                    console.error(`[SW] Batch sync failed: ${batchResponse.status}`);
                }
                
            } catch (error) {
                failedCount += batch.length;
                console.error('[SW] Batch sync error:', error);
            }
        }
        
        // Notify clients of sync results
        await notifyClients({
            type: 'CARGO_TALLY_SYNC_COMPLETE',
            synced: syncedCount,
            failed: failedCount,
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('[SW] Cargo tally sync failed:', error);
        await notifyClients({
            type: 'CARGO_TALLY_SYNC_FAILED',
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
}

// Vessel data sync with intelligent merging
async function syncVesselData() {
    console.log('[SW] Starting vessel data sync...');
    
    try {
        const response = await fetch('/sync/vessel-updates', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            redirect: 'follow'
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log(`[SW] Vessel sync complete: ${result.synced_count} vessels updated`);
            
            await notifyClients({
                type: 'VESSEL_DATA_SYNC_COMPLETE',
                synced: result.synced_count,
                conflicts: result.conflicts || 0,
                timestamp: new Date().toISOString()
            });
        } else {
            throw new Error(`Vessel sync failed: ${response.status}`);
        }
        
    } catch (error) {
        console.error('[SW] Vessel data sync failed:', error);
    }
}

// Document processing sync
async function syncDocuments() {
    console.log('[SW] Starting document sync...');
    
    try {
        const response = await fetch('/sync/pending-documents', {
            method: 'POST',
            redirect: 'follow'
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log(`[SW] Document sync complete: ${result.processed_count} documents`);
        }
        
    } catch (error) {
        console.error('[SW] Document sync failed:', error);
    }
}

// Wizard data sync for offline vessel creation
async function syncWizardData() {
    console.log('[SW] Starting wizard data sync...');
    
    try {
        const response = await fetch('/sync/offline-vessels', {
            method: 'POST',
            redirect: 'follow'
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log(`[SW] Wizard sync complete: ${result.created_count} vessels created`);
            
            await notifyClients({
                type: 'WIZARD_DATA_SYNC_COMPLETE',
                created: result.created_count,
                timestamp: new Date().toISOString()
            });
        }
        
    } catch (error) {
        console.error('[SW] Wizard data sync failed:', error);
    }
}

// Perform comprehensive batch sync of all pending data
async function performBatchSync() {
    console.log('[SW] Starting comprehensive batch sync...');
    
    const syncResults = {
        cargo_tallies: { success: false, count: 0 },
        vessels: { success: false, count: 0 },
        documents: { success: false, count: 0 },
        wizard_data: { success: false, count: 0 }
    };
    
    try {
        // Run all syncs in parallel for efficiency
        const [cargoResult, vesselResult, docResult, wizardResult] = await Promise.allSettled([
            syncCargoTallies(),
            syncVesselData(), 
            syncDocuments(),
            syncWizardData()
        ]);
        
        // Process results
        syncResults.cargo_tallies.success = cargoResult.status === 'fulfilled';
        syncResults.vessels.success = vesselResult.status === 'fulfilled';
        syncResults.documents.success = docResult.status === 'fulfilled';
        syncResults.wizard_data.success = wizardResult.status === 'fulfilled';
        
        const successCount = Object.values(syncResults).filter(r => r.success).length;
        
        console.log(`[SW] Batch sync complete: ${successCount}/4 sync operations succeeded`);
        
        await notifyClients({
            type: 'BATCH_SYNC_COMPLETE',
            results: syncResults,
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('[SW] Batch sync failed:', error);
    }
}

// Enhanced push notifications for maritime operations
self.addEventListener('push', event => {
    if (!event.data) {
        console.warn('[SW] Push event received but no data present');
        return;
    }
    
    try {
        const data = event.data.json();
        console.log('[SW] Push notification received:', data.type);
        
        // Different notification types for maritime operations
        const notificationOptions = {
            icon: '/static/icons/icon-192x192.png',
            badge: '/static/icons/badge-72x72.png',
            vibrate: [200, 100, 200],
            requireInteraction: false,
            actions: []
        };
        
        // Customize notification based on type
        switch (data.type) {
            case 'vessel_arrival':
                notificationOptions.tag = 'vessel-arrival';
                notificationOptions.requireInteraction = true;
                notificationOptions.actions = [
                    { action: 'view', title: 'View Vessel' },
                    { action: 'dismiss', title: 'Dismiss' }
                ];
                break;
                
            case 'cargo_complete':
                notificationOptions.tag = 'cargo-complete';
                notificationOptions.actions = [
                    { action: 'view-progress', title: 'View Progress' },
                    { action: 'export-data', title: 'Export Data' }
                ];
                break;
                
            case 'sync_required':
                notificationOptions.tag = 'sync-required';
                notificationOptions.requireInteraction = true;
                break;
                
            default:
                notificationOptions.tag = 'stevedores-update';
        }
        
        event.waitUntil(
            self.registration.showNotification(data.title, {
                body: data.body,
                data: data,
                ...notificationOptions
            })
        );
        
    } catch (error) {
        console.error('[SW] Failed to process push notification:', error);
    }
});

// Enhanced notification click handling
self.addEventListener('notificationclick', event => {
    console.log('[SW] Notification clicked:', event.action, event.notification.tag);
    event.notification.close();
    
    const data = event.notification.data;
    let targetUrl = '/dashboard';
    
    // Handle different actions
    switch (event.action) {
        case 'view':
            targetUrl = data.vessel_id ? `/vessel/${data.vessel_id}` : '/dashboard';
            break;
        case 'view-progress':
            targetUrl = '/dashboard';
            break;
        case 'export-data':
            // Handle export action - could trigger a postMessage to client
            event.waitUntil(
                notifyClients({
                    type: 'EXPORT_REQUEST',
                    vessel_id: data.vessel_id,
                    timestamp: new Date().toISOString()
                })
            );
            return;
        case 'dismiss':
            return; // Just close the notification
        default:
            // Default click behavior
            targetUrl = data.url || '/dashboard';
    }
    
    // Open or focus the appropriate window
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then(clientList => {
                // Try to find an existing window to focus
                for (let client of clientList) {
                    if (client.url.includes('/dashboard') && 'focus' in client) {
                        return client.focus();
                    }
                }
                
                // Open new window if none found
                if (clients.openWindow) {
                    return clients.openWindow(targetUrl);
                }
            })
    );
});

// Periodic background sync for continuous operation
self.addEventListener('periodicsync', event => {
    console.log('[SW] Periodic sync triggered:', event.tag);
    
    if (event.tag === 'maritime-data-sync') {
        event.waitUntil(performPeriodicSync());
    }
});

// Perform periodic sync for critical maritime data
async function performPeriodicSync() {
    console.log('[SW] Starting periodic maritime sync...');
    
    try {
        // Only sync if the user has been active recently
        const clients = await self.clients.matchAll();
        const hasActiveClients = clients.length > 0;
        
        if (!hasActiveClients) {
            console.log('[SW] No active clients, skipping periodic sync');
            return;
        }
        
        // Perform lightweight sync of critical data
        const syncPromises = [
            syncCriticalVesselData(),
            syncUrgentCargoTallies()
        ];
        
        await Promise.allSettled(syncPromises);
        
        console.log('[SW] Periodic sync completed');
        
    } catch (error) {
        console.error('[SW] Periodic sync failed:', error);
    }
}

// Sync only critical vessel data during periodic sync
async function syncCriticalVesselData() {
    try {
        const response = await fetch('/sync/critical-vessels', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            redirect: 'follow'
        });
        
        if (response.ok) {
            const result = await response.json();
            if (result.urgent_updates > 0) {
                await notifyClients({
                    type: 'CRITICAL_VESSEL_UPDATES',
                    count: result.urgent_updates,
                    timestamp: new Date().toISOString()
                });
            }
        }
    } catch (error) {
        console.error('[SW] Critical vessel sync failed:', error);
    }
}

// Sync urgent cargo tallies during periodic sync
async function syncUrgentCargoTallies() {
    try {
        const response = await fetch('/sync/urgent-tallies', {
            method: 'POST',
            redirect: 'follow'
        });
        
        if (response.ok) {
            const result = await response.json();
            if (result.synced_count > 0) {
                console.log(`[SW] Synced ${result.synced_count} urgent cargo tallies`);
            }
        }
    } catch (error) {
        console.error('[SW] Urgent tally sync failed:', error);
    }
}

// Advanced error handling for uncaught service worker errors
self.addEventListener('error', event => {
    console.error('[SW] Uncaught error:', event.error);
    
    // Notify clients of service worker error
    notifyClients({
        type: 'SW_ERROR',
        error: event.error?.message || 'Unknown service worker error',
        timestamp: new Date().toISOString()
    }).catch(() => {
        // Ignore notification failures during error handling
    });
});

// Handle unhandled promise rejections
self.addEventListener('unhandledrejection', event => {
    console.error('[SW] Unhandled promise rejection:', event.reason);
    
    // Prevent the error from being logged to console again
    event.preventDefault();
    
    notifyClients({
        type: 'SW_PROMISE_REJECTION',
        error: event.reason?.message || 'Unknown promise rejection',
        timestamp: new Date().toISOString()
    }).catch(() => {
        // Ignore notification failures during error handling
    });
});

// Service Worker performance monitoring
const SW_PERFORMANCE = {
    startTime: Date.now(),
    requestCount: 0,
    cacheHits: 0,
    cacheMisses: 0,
    syncOperations: 0
};

// Log performance metrics periodically
setInterval(() => {
    const uptime = Date.now() - SW_PERFORMANCE.startTime;
    const hitRate = SW_PERFORMANCE.requestCount > 0 ? 
        (SW_PERFORMANCE.cacheHits / SW_PERFORMANCE.requestCount * 100).toFixed(1) : 0;
    
    console.log(`[SW] Performance - Uptime: ${Math.round(uptime/1000)}s, Requests: ${SW_PERFORMANCE.requestCount}, Cache Hit Rate: ${hitRate}%, Syncs: ${SW_PERFORMANCE.syncOperations}`);
}, 300000); // Log every 5 minutes

// Service Worker lifecycle logging
console.log(`[SW] Stevedores Dashboard 3.0 Advanced Service Worker v${VERSION} loaded`);
console.log('[SW] Features: Advanced Caching, Background Sync, Push Notifications, Periodic Sync');
console.log('[SW] Optimized for maritime operations with unreliable connectivity');

// Global scope cleanup and resource management
self.addEventListener('beforeinstallprompt', event => {
    console.log('[SW] Before install prompt event fired');
});

// Export performance tracking for debugging
self.getServiceWorkerStats = () => {
    return {
        version: VERSION,
        uptime: Date.now() - SW_PERFORMANCE.startTime,
        performance: SW_PERFORMANCE,
        cacheNames: [CACHE_NAME, RUNTIME_CACHE, API_CACHE],
        timestamp: new Date().toISOString()
    };
};