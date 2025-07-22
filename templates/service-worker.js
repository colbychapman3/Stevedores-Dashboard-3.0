// Stevedores Dashboard 3.0 - Service Worker for Offline Operations
// Critical for ship operations where connectivity is unreliable

const CACHE_NAME = 'stevedores-dashboard-v3.0.0';
const OFFLINE_URL = '/offline';

// Resources to cache for offline functionality
const STATIC_CACHE_URLS = [
    '/',
    '/dashboard',
    '/offline',
    '/static/css/main.css',
    '/static/js/app.js',
    '/static/js/offline-db.js',
    '/static/js/widgets.js',
    '/auth/login',
    '/manifest.json'
];

// Dynamic cache patterns
const CACHE_PATTERNS = [
    /^\/static\/.*\.(css|js|png|jpg|jpeg|gif|svg|woff|woff2)$/,
    /^\/api\/vessels\/\d+$/,
    /^\/dashboard/
];

// Install event - cache essential resources
self.addEventListener('install', event => {
    console.log('[SW] Installing service worker...');
    
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[SW] Caching app shell and essential resources');
                return cache.addAll(STATIC_CACHE_URLS);
            })
            .then(() => {
                // Force activation of new service worker
                return self.skipWaiting();
            })
            .catch(error => {
                console.error('[SW] Failed to cache resources:', error);
            })
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
    console.log('[SW] Activating service worker...');
    
    event.waitUntil(
        caches.keys()
            .then(cacheNames => {
                return Promise.all(
                    cacheNames.map(cacheName => {
                        if (cacheName !== CACHE_NAME) {
                            console.log('[SW] Deleting old cache:', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            })
            .then(() => {
                // Ensure service worker controls all clients immediately
                return self.clients.claim();
            })
    );
});

// Fetch event - handle requests with cache-first strategy for offline capability
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Skip non-GET requests
    if (request.method !== 'GET') {
        return;
    }
    
    // Handle different types of requests
    if (isAPIRequest(url)) {
        event.respondWith(handleAPIRequest(request));
    } else if (isStaticResource(url)) {
        event.respondWith(handleStaticResource(request));
    } else if (isNavigationRequest(request)) {
        event.respondWith(handleNavigationRequest(request));
    }
});

// Check if request is an API call
function isAPIRequest(url) {
    return url.pathname.startsWith('/api/');
}

// Check if request is for static resources
function isStaticResource(url) {
    return CACHE_PATTERNS.some(pattern => pattern.test(url.pathname));
}

// Check if request is a navigation request
function isNavigationRequest(request) {
    return request.mode === 'navigate' || 
           (request.method === 'GET' && 
            request.headers.get('accept').includes('text/html'));
}

// Handle API requests - network first, cache fallback
async function handleAPIRequest(request) {
    const cache = await caches.open(CACHE_NAME);
    
    try {
        // Try network first for fresh data
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            // Cache successful responses for offline fallback
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.log('[SW] API network failed, trying cache:', request.url);
        
        // Network failed, try cache
        const cachedResponse = await cache.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // No cache available, return offline indicator
        return new Response(
            JSON.stringify({ 
                error: 'Offline - data not available',
                offline: true,
                timestamp: new Date().toISOString()
            }), 
            {
                status: 503,
                headers: { 'Content-Type': 'application/json' }
            }
        );
    }
}

// Handle static resources - cache first
async function handleStaticResource(request) {
    const cache = await caches.open(CACHE_NAME);
    
    // Try cache first
    const cachedResponse = await cache.match(request);
    if (cachedResponse) {
        return cachedResponse;
    }
    
    try {
        // Cache miss, fetch from network
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.log('[SW] Static resource unavailable:', request.url);
        
        // Could return a fallback resource here if needed
        return new Response('Resource unavailable offline', {
            status: 503,
            headers: { 'Content-Type': 'text/plain' }
        });
    }
}

// Handle navigation requests - network first, cache fallback, offline page
async function handleNavigationRequest(request) {
    const cache = await caches.open(CACHE_NAME);
    
    try {
        // Try network first
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            // Cache successful page responses
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.log('[SW] Navigation network failed, trying cache:', request.url);
        
        // Network failed, try cache
        const cachedResponse = await cache.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // No cache available, show offline page
        const offlineResponse = await cache.match(OFFLINE_URL);
        return offlineResponse || new Response('Offline - page not available', {
            status: 503,
            headers: { 'Content-Type': 'text/html' }
        });
    }
}

// Background sync for when connection returns
self.addEventListener('sync', event => {
    console.log('[SW] Background sync triggered:', event.tag);
    
    if (event.tag === 'cargo-tally-sync') {
        event.waitUntil(syncCargoTallies());
    } else if (event.tag === 'vessel-data-sync') {
        event.waitUntil(syncVesselData());
    }
});

// Sync cargo tallies when connection returns
async function syncCargoTallies() {
    console.log('[SW] Syncing cargo tallies...');
    
    try {
        // This would interact with IndexedDB to get unsynced tallies
        const response = await fetch('/api/sync/cargo-tallies', {
            method: 'POST'
        });
        
        if (response.ok) {
            console.log('[SW] Cargo tallies synced successfully');
            // Notify main thread of successful sync
            self.clients.matchAll().then(clients => {
                clients.forEach(client => {
                    client.postMessage({
                        type: 'SYNC_COMPLETE',
                        data: 'cargo-tallies'
                    });
                });
            });
        }
    } catch (error) {
        console.error('[SW] Failed to sync cargo tallies:', error);
    }
}

// Sync vessel data when connection returns
async function syncVesselData() {
    console.log('[SW] Syncing vessel data...');
    
    try {
        const response = await fetch('/api/sync/vessels', {
            method: 'POST'
        });
        
        if (response.ok) {
            console.log('[SW] Vessel data synced successfully');
        }
    } catch (error) {
        console.error('[SW] Failed to sync vessel data:', error);
    }
}

// Push notifications for manager updates
self.addEventListener('push', event => {
    if (!event.data) {
        return;
    }
    
    const data = event.data.json();
    
    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: '/static/icons/icon-192x192.png',
            badge: '/static/icons/icon-192x192.png',
            tag: 'stevedores-update',
            requireInteraction: true,
            data: data.data
        })
    );
});

// Handle notification clicks
self.addEventListener('notificationclick', event => {
    event.notification.close();
    
    event.waitUntil(
        clients.openWindow('/dashboard')
    );
});

console.log('[SW] Stevedores Dashboard 3.0 Service Worker loaded');