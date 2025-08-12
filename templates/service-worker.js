// Stevedores Dashboard 3.0 - Simplified PWA Service Worker
// Maritime operations optimized for connectivity issues

const VERSION = '3.0.6-REDIRECT-FIX';
const CACHE_NAME = `stevedores-dashboard-v${VERSION}`;
const RUNTIME_CACHE = `stevedores-runtime-v${VERSION}`;

// Critical resources for offline functionality
const CRITICAL_CACHE_URLS = [
    '/',
    '/dashboard',
    '/static/css/tailwind.min.css',
    '/static/js/sync-manager.js',
    '/static/js/pwa-manager.js'
];

// Install event - cache critical resources
self.addEventListener('install', event => {
    console.log(`[SW] Installing service worker v${VERSION}...`);
    
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            console.log('[SW] Caching critical resources');
            return cache.addAll(CRITICAL_CACHE_URLS).catch(error => {
                console.error('[SW] Failed to cache some resources:', error);
                return Promise.resolve(); // Continue anyway
            });
        }).then(() => {
            console.log('[SW] Installation complete, activating');
            return self.skipWaiting();
        }).catch(error => {
            console.error('[SW] Installation failed:', error);
        })
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
    console.log(`[SW] Activating service worker v${VERSION}...`);
    
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME && cacheName !== RUNTIME_CACHE) {
                        console.log('[SW] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => {
            console.log('[SW] Service worker activated');
            return self.clients.claim();
        })
    );
});

// Fetch event - simple network first with cache fallback
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Skip non-GET requests and external domains
    if (request.method !== 'GET' || url.origin !== location.origin) {
        return;
    }
    
    // Skip authentication routes
    if (url.pathname.startsWith('/auth/') || url.pathname.startsWith('/init-database')) {
        return;
    }
    
    event.respondWith(
        fetch(request).then(response => {
            // If successful, cache the response
            if (response.ok) {
                const responseClone = response.clone();
                caches.open(RUNTIME_CACHE).then(cache => {
                    cache.put(request, responseClone);
                });
            }
            return response;
        }).catch(() => {
            // Network failed, try cache
            return caches.match(request).then(cachedResponse => {
                if (cachedResponse) {
                    console.log('[SW] Serving from cache:', request.url);
                    return cachedResponse;
                }
                
                // Return offline fallback for navigation requests
                if (request.mode === 'navigate') {
                    return caches.match('/dashboard') || 
                           new Response('Offline - Please check your connection', {
                               status: 503,
                               headers: { 'Content-Type': 'text/plain' }
                           });
                }
                
                return new Response('Offline', { status: 503 });
            });
        })
    );
});

// Background sync for cargo tally data
self.addEventListener('sync', event => {
    console.log(`[SW] Background sync: ${event.tag}`);
    
    if (event.tag === 'cargo-tally-sync') {
        event.waitUntil(syncCargoTallies());
    }
});

// Simple cargo tally sync
async function syncCargoTallies() {
    try {
        const response = await fetch('/sync/pending-cargo-tallies');
        if (response.ok) {
            const data = await response.json();
            console.log(`[SW] Synced cargo tallies: ${data.synced_count || 0}`);
            
            // Notify clients
            const clients = await self.clients.matchAll();
            clients.forEach(client => {
                client.postMessage({
                    type: 'SYNC_COMPLETE',
                    data: data
                });
            });
        }
    } catch (error) {
        console.error('[SW] Sync failed:', error);
    }
}

// Error handling
self.addEventListener('error', event => {
    console.error('[SW] Service worker error:', event.error);
});

console.log(`[SW] Stevedores Dashboard Service Worker v${VERSION} loaded`);
console.log('[SW] Ready for maritime operations with offline support');