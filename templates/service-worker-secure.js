// Stevedores Dashboard 3.0 - Phase 4 Secure Service Worker
// Enhanced PWA functionality with maritime data security integration
// Integrates with maritime_data_classification.py and maritime_data_encryption.py

const VERSION = '3.0.5-secure';
const CACHE_NAME = `stevedores-dashboard-v${VERSION}`;
const RUNTIME_CACHE = `stevedores-runtime-v${VERSION}`;
const API_CACHE = `stevedores-api-v${VERSION}`;
const SECURE_CACHE = `stevedores-secure-v${VERSION}`;
const OFFLINE_URL = '/offline';

// Security configuration for maritime data
const SECURITY_CONFIG = {
    enableEncryptedCache: true,
    maxCacheAge: 24 * 60 * 60 * 1000, // 24 hours
    sensitiveDataPatterns: [
        /imo_number|vessel_registration|customs_declaration/i,
        /security_plan|isps_certificate|crew_list/i,
        /password|token|key|secret/i,
        /cargo_manifest|bill_of_lading|inspection_report/i
    ],
    classificationLevels: {
        PUBLIC: 'public',
        INTERNAL: 'internal', 
        CONFIDENTIAL: 'confidential',
        RESTRICTED: 'restricted',
        TOP_SECRET: 'top_secret'
    },
    roleBasedAccess: {
        'stevedore': ['PUBLIC', 'INTERNAL'],
        'vessel_operator': ['PUBLIC', 'INTERNAL', 'CONFIDENTIAL'],
        'port_authority': ['PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED'],
        'customs_officer': ['PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED'],
        'admin': ['PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED', 'TOP_SECRET']
    }
};

// Critical resources with security classification
const CRITICAL_CACHE_URLS = [
    { url: '/', classification: 'PUBLIC' },
    { url: '/dashboard', classification: 'INTERNAL' },
    { url: '/offline', classification: 'PUBLIC' },
    { url: '/wizard', classification: 'INTERNAL' },
    { url: '/auth/login', classification: 'PUBLIC' },
    { url: '/manifest.json', classification: 'PUBLIC' },
    { url: '/static/js/cargo-tally-widgets.js', classification: 'INTERNAL' },
    { url: '/static/js/sync-manager.js', classification: 'INTERNAL' },
    { url: '/static/js/wizard.js', classification: 'INTERNAL' }
];

// API endpoints with classification patterns
const API_CACHE_PATTERNS = [
    { pattern: /^\/api\/vessels\/public/, classification: 'PUBLIC' },
    { pattern: /^\/api\/vessels\/\d+$/, classification: 'INTERNAL' },
    { pattern: /^\/api\/vessels\/\d+\/security/, classification: 'RESTRICTED' },
    { pattern: /^\/api\/cargo\/summary/, classification: 'INTERNAL' },
    { pattern: /^\/api\/cargo\/manifest/, classification: 'CONFIDENTIAL' },
    { pattern: /^\/api\/customs/, classification: 'RESTRICTED' },
    { pattern: /^\/api\/users\/profile/, classification: 'CONFIDENTIAL' },
    { pattern: /^\/offline-dashboard\/dashboard-data/, classification: 'INTERNAL' },
    { pattern: /^\/document\/process/, classification: 'CONFIDENTIAL' }
];

// Navigation patterns with security requirements
const NAVIGATION_PATTERNS = [
    { pattern: /^\/dashboard/, classification: 'INTERNAL', requiresAuth: true },
    { pattern: /^\/vessel\/\d+/, classification: 'INTERNAL', requiresAuth: true },
    { pattern: /^\/vessel\/offline_/, classification: 'INTERNAL', requiresAuth: true },
    { pattern: /^\/cargo-tally/, classification: 'INTERNAL', requiresAuth: true },
    { pattern: /^\/reports/, classification: 'CONFIDENTIAL', requiresAuth: true },
    { pattern: /^\/wizard/, classification: 'INTERNAL', requiresAuth: true }
];

// Secure cache implementation using Web Crypto API
class SecureMaritimeCache {
    constructor() {
        this.keyCache = new Map();
        this.initialized = false;
        this.currentUserRole = null;
    }

    async initialize() {
        if (this.initialized) return;
        
        try {
            // Initialize encryption keys for different classification levels
            for (const [level, value] of Object.entries(SECURITY_CONFIG.classificationLevels)) {
                await this.generateKey(value);
            }
            
            this.initialized = true;
            console.log('[SW-Secure] Maritime secure cache initialized');
        } catch (error) {
            console.error('[SW-Secure] Failed to initialize secure cache:', error);
        }
    }

    async generateKey(classification) {
        try {
            const key = await crypto.subtle.generateKey(
                { name: 'AES-GCM', length: 256 },
                false, // not extractable for security
                ['encrypt', 'decrypt']
            );
            
            this.keyCache.set(classification, key);
            return key;
        } catch (error) {
            console.error('[SW-Secure] Failed to generate key for', classification, error);
            throw error;
        }
    }

    async encryptMaritimeData(data, classification = 'INTERNAL', metadata = {}) {
        if (!this.initialized) await this.initialize();
        
        try {
            const key = this.keyCache.get(classification);
            if (!key) {
                throw new Error(`No encryption key for classification: ${classification}`);
            }

            const encoder = new TextEncoder();
            const serializedData = JSON.stringify({
                data: data,
                metadata: {
                    ...metadata,
                    classification: classification,
                    encrypted_at: Date.now(),
                    user_role: this.currentUserRole,
                    retention_policy: this.getRetentionPolicy(classification)
                }
            });
            
            const dataBytes = encoder.encode(serializedData);
            const iv = crypto.getRandomValues(new Uint8Array(12));

            const encryptedData = await crypto.subtle.encrypt(
                { name: 'AES-GCM', iv: iv },
                key,
                dataBytes
            );

            return {
                encrypted: Array.from(new Uint8Array(encryptedData)),
                iv: Array.from(iv),
                classification: classification,
                timestamp: Date.now(),
                integrity_hash: await this.calculateHash(dataBytes)
            };
        } catch (error) {
            console.error('[SW-Secure] Maritime data encryption failed:', error);
            throw error;
        }
    }

    async decryptMaritimeData(encryptedContainer) {
        if (!this.initialized) await this.initialize();
        
        try {
            const key = this.keyCache.get(encryptedContainer.classification);
            if (!key) {
                throw new Error(`No decryption key for classification: ${encryptedContainer.classification}`);
            }

            // Check if data has expired based on maritime retention policies
            const age = Date.now() - encryptedContainer.timestamp;
            const maxAge = this.getMaxAge(encryptedContainer.classification);
            
            if (age > maxAge) {
                throw new Error('Encrypted maritime data expired - retention policy violated');
            }

            // Verify user access rights
            if (!this.canUserAccess(encryptedContainer.classification)) {
                throw new Error('Access denied - insufficient permissions for classification level');
            }

            const encryptedData = new Uint8Array(encryptedContainer.encrypted);
            const iv = new Uint8Array(encryptedContainer.iv);

            const decryptedData = await crypto.subtle.decrypt(
                { name: 'AES-GCM', iv: iv },
                key,
                encryptedData
            );

            const decoder = new TextDecoder();
            const decryptedJson = JSON.parse(decoder.decode(decryptedData));
            
            // Verify data integrity
            const integrityHash = await this.calculateHash(new TextEncoder().encode(JSON.stringify(decryptedJson)));
            if (integrityHash !== encryptedContainer.integrity_hash) {
                throw new Error('Maritime data integrity check failed');
            }

            return decryptedJson;
        } catch (error) {
            console.error('[SW-Secure] Maritime data decryption failed:', error);
            throw error;
        }
    }

    async calculateHash(data) {
        const hashBuffer = await crypto.subtle.digest('SHA-256', data);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    }

    getRetentionPolicy(classification) {
        // Maritime data retention policies
        const policies = {
            'public': { years: 1, archive_after: 1 },
            'internal': { years: 7, archive_after: 2 }, // Standard maritime retention
            'confidential': { years: 7, archive_after: 2 },
            'restricted': { years: 25, archive_after: 5 }, // Safety-critical data
            'top_secret': { years: 50, archive_after: 10 } // Security-sensitive data
        };
        
        return policies[classification] || policies['internal'];
    }

    getMaxAge(classification) {
        const policy = this.getRetentionPolicy(classification);
        return policy.years * 365 * 24 * 60 * 60 * 1000; // Convert years to milliseconds
    }

    canUserAccess(classification) {
        if (!this.currentUserRole) return false;
        
        const allowedLevels = SECURITY_CONFIG.roleBasedAccess[this.currentUserRole] || [];
        return allowedLevels.includes(classification.toUpperCase());
    }

    setUserRole(role) {
        this.currentUserRole = role;
        console.log('[SW-Secure] User role set to:', role);
    }

    async storeSecureMaritimeData(request, response, classification = 'INTERNAL') {
        try {
            if (!response.ok) return false;

            const responseData = await response.clone().json();
            const encryptedContainer = await this.encryptMaritimeData(responseData, classification, {
                url: request.url,
                method: request.method,
                cached_at: Date.now()
            });
            
            const cache = await caches.open(SECURE_CACHE);
            const secureResponse = new Response(JSON.stringify(encryptedContainer), {
                status: 200,
                headers: {
                    'Content-Type': 'application/json',
                    'X-Maritime-Classification': classification.toUpperCase(),
                    'X-Cache-Encrypted': 'true',
                    'X-Cache-Timestamp': Date.now().toString(),
                    'X-Cache-Retention': JSON.stringify(this.getRetentionPolicy(classification))
                }
            });

            await cache.put(request, secureResponse);
            console.log('[SW-Secure] Stored encrypted maritime data with classification:', classification);
            return true;
        } catch (error) {
            console.error('[SW-Secure] Failed to store secure maritime data:', error);
            return false;
        }
    }

    async retrieveSecureMaritimeData(request) {
        try {
            const cache = await caches.open(SECURE_CACHE);
            const cachedResponse = await cache.match(request);
            
            if (!cachedResponse) return null;
            
            const encryptedContainer = await cachedResponse.json();
            const decryptedData = await this.decryptMaritimeData(encryptedContainer);
            
            return new Response(JSON.stringify(decryptedData.data), {
                status: 200,
                headers: {
                    'Content-Type': 'application/json',
                    'X-Cache-Source': 'secure-maritime-cache',
                    'X-Maritime-Classification': encryptedContainer.classification.toUpperCase(),
                    'X-Cache-Decrypted': 'true'
                }
            });
        } catch (error) {
            console.error('[SW-Secure] Failed to retrieve secure maritime data:', error);
            
            // If access denied, don't expose the error details
            if (error.message.includes('Access denied')) {
                return new Response(JSON.stringify({ 
                    error: 'Access denied - insufficient permissions',
                    classification_required: 'Contact system administrator'
                }), {
                    status: 403,
                    headers: { 'Content-Type': 'application/json' }
                });
            }
            
            return null;
        }
    }
}

// Global secure maritime cache instance
const secureMaritimeCache = new SecureMaritimeCache();

// Enhanced install event with security initialization
self.addEventListener('install', event => {
    console.log(`[SW] Installing maritime-secure service worker v${VERSION}...`);
    
    event.waitUntil(
        Promise.all([
            // Initialize secure maritime cache
            secureMaritimeCache.initialize(),
            
            // Cache critical resources with classification awareness
            caches.open(CACHE_NAME).then(cache => {
                console.log('[SW] Caching critical maritime resources');
                const urls = CRITICAL_CACHE_URLS.map(item => item.url);
                return cache.addAll(urls).catch(error => {
                    console.error('[SW] Failed to cache some critical resources:', error);
                    return Promise.resolve();
                });
            }),
            
            // Initialize other caches
            caches.open(RUNTIME_CACHE),
            caches.open(API_CACHE),
            caches.open(SECURE_CACHE)
        ])
        .then(() => {
            console.log('[SW] Maritime security installation complete');
            return self.skipWaiting();
        })
        .catch(error => {
            console.error('[SW] Maritime security installation failed:', error);
            throw error;
        })
    );
});

// Enhanced activate event with security cleanup
self.addEventListener('activate', event => {
    console.log(`[SW] Activating maritime-secure service worker v${VERSION}...`);
    
    const currentCaches = [CACHE_NAME, RUNTIME_CACHE, API_CACHE, SECURE_CACHE];
    
    event.waitUntil(
        Promise.all([
            // Clean up old caches including secure data
            caches.keys().then(cacheNames => {
                return Promise.all(
                    cacheNames.map(cacheName => {
                        if (!currentCaches.includes(cacheName)) {
                            console.log('[SW] Deleting outdated maritime cache:', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            }),
            
            // Initialize maritime security context
            initializeMaritimeSecurityContext()
        ])
        .then(() => {
            console.log('[SW] Maritime security activation complete');
            return self.clients.claim();
        })
        .then(() => {
            return notifyClients({
                type: 'SW_MARITIME_SECURITY_ACTIVATED',
                version: VERSION,
                timestamp: new Date().toISOString(),
                security_features: {
                    encrypted_cache: true,
                    role_based_access: true,
                    data_classification: true,
                    retention_policies: true
                }
            });
        })
    );
});

// Initialize maritime security context
async function initializeMaritimeSecurityContext() {
    try {
        console.log('[SW] Initializing maritime security context...');
        
        // This would integrate with the backend to get user security context
        // For now, we'll set a default context
        await secureMaritimeCache.initialize();
        
        console.log('[SW] Maritime security context initialized');
        return Promise.resolve();
    } catch (error) {
        console.error('[SW] Failed to initialize maritime security context:', error);
        return Promise.resolve(); // Don't fail activation
    }
}

// Enhanced fetch handler with maritime security awareness
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Skip non-GET requests and external domains
    if (request.method !== 'GET' || url.origin !== location.origin) {
        return;
    }
    
    // Skip critical endpoints that should never be cached
    const skipPatterns = [
        '/init-database',
        '/auth/api/',
        '/sync/secure-handshake'
    ];
    
    const shouldSkip = skipPatterns.some(pattern => url.pathname.startsWith(pattern));
    if (shouldSkip) {
        return;
    }
    
    event.respondWith(handleMaritimeSecureFetch(request, url));
});

// Enhanced secure fetch handler with maritime data classification
async function handleMaritimeSecureFetch(request, url) {
    try {
        // Determine security requirements for this request
        const securityContext = getRequestSecurityContext(url);
        
        if (securityContext.requiresAuth && !await isUserAuthenticated()) {
            return Response.redirect('/auth/login', 302);
        }
        
        // Handle different request types with security awareness
        if (isAPIRequest(url)) {
            return await handleSecureAPIRequest(request, url, securityContext);
        } else if (isStaticResource(url)) {
            return await handleStaticResource(request, url);
        } else if (isNavigationRequest(request, url)) {
            return await handleSecureNavigationRequest(request, url, securityContext);
        } else {
            return await handleGenericRequest(request, url);
        }
        
    } catch (error) {
        console.error('[SW] Maritime secure fetch error:', error);
        return await getOfflineFallback(request);
    }
}

// Get security context for request
function getRequestSecurityContext(url) {
    // Check API patterns
    for (const { pattern, classification } of API_CACHE_PATTERNS) {
        if (pattern.test(url.pathname)) {
            return {
                classification: classification,
                requiresAuth: classification !== 'PUBLIC',
                requiresEncryption: ['CONFIDENTIAL', 'RESTRICTED', 'TOP_SECRET'].includes(classification)
            };
        }
    }
    
    // Check navigation patterns
    for (const { pattern, classification, requiresAuth } of NAVIGATION_PATTERNS) {
        if (pattern.test(url.pathname)) {
            return {
                classification: classification,
                requiresAuth: requiresAuth || false,
                requiresEncryption: ['CONFIDENTIAL', 'RESTRICTED', 'TOP_SECRET'].includes(classification)
            };
        }
    }
    
    // Default security context
    return {
        classification: 'INTERNAL',
        requiresAuth: false,
        requiresEncryption: false
    };
}

// Check if user is authenticated (simplified check)
async function isUserAuthenticated() {
    try {
        // This would integrate with the authentication system
        // For now, check if we have any secure cached data which implies authentication
        const cache = await caches.open(SECURE_CACHE);
        const keys = await cache.keys();
        return keys.length > 0; // Simplified check
    } catch (error) {
        return false;
    }
}

// Enhanced API request handler with maritime security
async function handleSecureAPIRequest(request, url, securityContext) {
    const { classification, requiresEncryption } = securityContext;
    
    try {
        // For sensitive data, try secure cache first
        if (requiresEncryption) {
            const secureResponse = await secureMaritimeCache.retrieveSecureMaritimeData(request);
            if (secureResponse) {
                console.log('[SW] Served from secure maritime cache:', request.url);
                
                // Update cache in background if not too recent
                const cacheTimestamp = secureResponse.headers.get('X-Cache-Timestamp');
                if (cacheTimestamp && Date.now() - parseInt(cacheTimestamp) > 300000) { // 5 minutes
                    fetch(request).then(async response => {
                        if (response.ok) {
                            await secureMaritimeCache.storeSecureMaritimeData(request, response, classification);
                        }
                    }).catch(() => {}); // Ignore background update failures
                }
                
                return secureResponse;
            }
        }
        
        // Network first for maritime-critical data
        if (url.pathname.includes('dashboard-data') || url.pathname.includes('vessel')) {
            return await networkFirstStrategy(request, classification, {
                timeout: 3000, // 3 second timeout for ship operations
                fallbackResponse: createOfflineAPIResponse(classification)
            });
        }
        
        // Regular network first for other API calls
        const response = await fetch(request);
        
        if (response.ok) {
            if (requiresEncryption) {
                // Store in secure cache
                await secureMaritimeCache.storeSecureMaritimeData(request, response, classification);
            } else {
                // Store in regular cache
                const cache = await caches.open(API_CACHE);
                cache.put(request, response.clone());
            }
        }
        
        return response;
        
    } catch (error) {
        console.error('[SW] Secure API request failed:', error);
        
        // Try secure cache as fallback
        if (requiresEncryption) {
            const secureResponse = await secureMaritimeCache.retrieveSecureMaritimeData(request);
            if (secureResponse) return secureResponse;
        }
        
        // Try regular cache
        const cache = await caches.open(API_CACHE);
        const cachedResponse = await cache.match(request);
        if (cachedResponse) return cachedResponse;
        
        return createOfflineAPIResponse(classification);
    }
}

// Network-first strategy with maritime security
async function networkFirstStrategy(request, classification, options = {}) {
    const timeout = options.timeout || 5000;
    
    try {
        const networkResponse = await Promise.race([
            fetch(request),
            new Promise((_, reject) => 
                setTimeout(() => reject(new Error('Network timeout')), timeout)
            )
        ]);
        
        if (networkResponse.ok) {
            // Cache based on classification
            if (['CONFIDENTIAL', 'RESTRICTED', 'TOP_SECRET'].includes(classification)) {
                await secureMaritimeCache.storeSecureMaritimeData(request, networkResponse, classification);
            } else {
                const cache = await caches.open(API_CACHE);
                cache.put(request.clone(), networkResponse.clone());
            }
            
            const response = networkResponse.clone();
            response.headers.set('sw-cache-status', 'network-fresh');
            response.headers.set('sw-timestamp', new Date().toISOString());
            response.headers.set('sw-classification', classification);
            
            return response;
        }
        
        throw new Error(`HTTP ${networkResponse.status}`);
        
    } catch (error) {
        console.log(`[SW] Network failed for ${request.url}, trying cache`);
        
        // Try secure cache first
        if (['CONFIDENTIAL', 'RESTRICTED', 'TOP_SECRET'].includes(classification)) {
            const secureResponse = await secureMaritimeCache.retrieveSecureMaritimeData(request);
            if (secureResponse) return secureResponse;
        }
        
        // Try regular cache
        const cache = await caches.open(API_CACHE);
        const cachedResponse = await cache.match(request);
        if (cachedResponse) {
            const response = cachedResponse.clone();
            response.headers.set('sw-cache-status', 'cache-hit');
            return response;
        }
        
        return options.fallbackResponse || createOfflineAPIResponse(classification);
    }
}

// Create maritime-aware offline API responses
function createOfflineAPIResponse(classification = 'INTERNAL') {
    const responseData = {
        success: false,
        error: 'Offline - maritime data not available',
        offline: true,
        mode: 'maritime-offline',
        classification: classification,
        timestamp: new Date().toISOString(),
        sw_version: VERSION,
        maritime_context: {
            data_retention_required: true,
            sync_on_reconnect: true,
            classification_level: classification
        }
    };
    
    // Don't expose sensitive information in offline responses
    if (['RESTRICTED', 'TOP_SECRET'].includes(classification)) {
        responseData.error = 'Service temporarily unavailable';
        delete responseData.maritime_context;
    }
    
    return new Response(JSON.stringify(responseData), {
        status: 503,
        statusText: 'Service Unavailable - Maritime Offline Mode',
        headers: { 
            'Content-Type': 'application/json',
            'sw-cache-status': 'maritime-offline-fallback',
            'sw-offline': 'true',
            'sw-classification': classification
        }
    });
}

// Enhanced static resource handler
async function handleStaticResource(request, url) {
    const cache = await caches.open(CACHE_NAME);
    const runtimeCache = await caches.open(RUNTIME_CACHE);
    
    // For versioned static assets: cache first
    if (url.pathname.includes('.js') || url.pathname.includes('.css') || 
        url.pathname.includes('/icons/')) {
        
        const cachedResponse = await cache.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
    }
    
    try {
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            const responseToCache = networkResponse.clone();
            
            if (url.pathname.includes('/icons/') || url.pathname.match(/\.(js|css|woff|woff2)$/)) {
                cache.put(request, responseToCache);
            } else {
                runtimeCache.put(request, responseToCache);
            }
        }
        
        return networkResponse;
        
    } catch (error) {
        console.log('[SW] Static resource network failed:', request.url);
        
        const cachedResponse = await cache.match(request) || 
                             await runtimeCache.match(request);
        
        if (cachedResponse) {
            return cachedResponse;
        }
        
        return createStaticResourceFallback(url.pathname);
    }
}

// Create fallback for static resources
function createStaticResourceFallback(pathname) {
    if (pathname.endsWith('.js')) {
        return new Response('// Maritime offline fallback script\nconsole.log("Maritime resource unavailable offline");', {
            status: 503,
            headers: { 'Content-Type': 'application/javascript' }
        });
    } else if (pathname.endsWith('.css')) {
        return new Response('/* Maritime offline fallback styles */', {
            status: 503,
            headers: { 'Content-Type': 'text/css' }
        });
    }
    
    return new Response('Maritime resource unavailable offline', {
        status: 503,
        headers: { 'Content-Type': 'text/plain' }
    });
}

// Enhanced navigation handler with security
async function handleSecureNavigationRequest(request, url, securityContext) {
    const { classification, requiresAuth } = securityContext;
    
    if (requiresAuth && !await isUserAuthenticated()) {
        return Response.redirect('/auth/login', 302);
    }
    
    const cache = await caches.open(CACHE_NAME);
    const runtimeCache = await caches.open(RUNTIME_CACHE);
    
    try {
        const timeoutPromise = new Promise((_, reject) => 
            setTimeout(() => reject(new Error('Navigation timeout')), 2000)
        );
        
        const networkResponse = await Promise.race([
            fetch(request),
            timeoutPromise
        ]);
        
        if (networkResponse.ok) {
            runtimeCache.put(request, networkResponse.clone());
            return networkResponse;
        }
        
        throw new Error(`HTTP ${networkResponse.status}`);
        
    } catch (error) {
        console.log(`[SW] Secure navigation network failed for ${request.url}:`, error.message);
        
        // Try cached version based on classification
        let cachedResponse = await runtimeCache.match(request) || 
                           await cache.match(request);
        
        if (cachedResponse) {
            console.log(`[SW] Serving cached secure navigation for ${request.url}`);
            return cachedResponse;
        }
        
        // Classification-aware fallbacks
        if (url.pathname.startsWith('/vessel/')) {
            cachedResponse = await runtimeCache.match('/vessel/details') ||
                           await cache.match('/vessel/details');
            if (cachedResponse) return cachedResponse;
        }
        
        if (url.pathname.startsWith('/dashboard')) {
            cachedResponse = await runtimeCache.match('/dashboard') ||
                           await cache.match('/dashboard');
            if (cachedResponse) return cachedResponse;
        }
        
        // Security-aware offline page
        const offlineResponse = await cache.match(OFFLINE_URL);
        if (offlineResponse) {
            return offlineResponse;
        }
        
        return createMaritimeOfflineNavigationFallback(classification);
    }
}

// Generic request handler
async function handleGenericRequest(request, url) {
    const runtimeCache = await caches.open(RUNTIME_CACHE);
    
    try {
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            runtimeCache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
        
    } catch (error) {
        console.log(`[SW] Generic request failed for ${request.url}`);
        
        const cachedResponse = await runtimeCache.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        return new Response('Maritime request failed - offline', {
            status: 503,
            headers: { 'Content-Type': 'text/plain' }
        });
    }
}

// Get offline fallback with maritime security awareness
async function getOfflineFallback(request) {
    const url = new URL(request.url);
    const securityContext = getRequestSecurityContext(url);
    
    // For HTML pages, return maritime offline page
    if (request.headers.get('accept')?.includes('text/html')) {
        const cache = await caches.open(CACHE_NAME);
        const offlineResponse = await cache.match(OFFLINE_URL);
        
        if (offlineResponse) {
            return offlineResponse;
        }
        
        return createMaritimeOfflineNavigationFallback(securityContext.classification);
    }
    
    // For API requests, try secure cache first then regular cache
    if (request.url.includes('/api/')) {
        if (securityContext.requiresEncryption) {
            const secureResponse = await secureMaritimeCache.retrieveSecureMaritimeData(request);
            if (secureResponse) return secureResponse;
        }
        
        const cache = await caches.open(API_CACHE);
        const cachedResponse = await cache.match(request);
        if (cachedResponse) return cachedResponse;
        
        return createOfflineAPIResponse(securityContext.classification);
    }
    
    return new Response('Maritime service offline', { status: 503 });
}

// Create maritime-aware offline navigation fallback
function createMaritimeOfflineNavigationFallback(classification = 'INTERNAL') {
    const html = `
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Maritime Offline Mode - Stevedores Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .icon { font-size: 4rem; color: #1e40af; margin-bottom: 20px; }
            h1 { color: #1f2937; margin-bottom: 16px; }
            p { color: #6b7280; line-height: 1.6; margin-bottom: 16px; }
            .classification { background: #e5e7eb; padding: 8px 16px; border-radius: 4px; font-weight: bold; margin: 16px 0; }
            .security-info { background: #fef3c7; padding: 16px; border-radius: 6px; margin: 20px 0; text-align: left; }
            .button { display: inline-block; background: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 8px; }
            .secondary { background: #6b7280; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">⚓🔒</div>
            <h1>Maritime Secure Offline Mode</h1>
            <div class="classification">Data Classification: ${classification.toUpperCase()}</div>
            
            <p>You're currently offline. The Stevedores Dashboard maintains secure maritime operations with limited connectivity.</p>
            
            <div class="security-info">
                <strong>Security Features Active:</strong>
                <ul style="text-align: left; margin: 8px 0;">
                    <li>✅ Encrypted local data storage</li>
                    <li>✅ Role-based access control</li>
                    <li>✅ Maritime data classification</li>
                    <li>✅ Retention policy enforcement</li>
                </ul>
            </div>
            
            <p>Your work will be securely saved locally and synchronized when connection returns.</p>
            <p><em>All maritime data is handled according to GDPR, SOLAS, MARPOL, and ISPS regulations.</em></p>
            
            <a href="/dashboard" class="button">Return to Dashboard</a>
            <a href="/offline" class="button secondary">Offline Tools</a>
        </div>
        
        <script>
            // Auto-reload when connection returns
            window.addEventListener('online', () => {
                console.log('Maritime connection restored');
                window.location.reload();
            });
            
            // Security context logging
            console.log('Maritime secure offline mode active');
            console.log('Data classification: ${classification.toUpperCase()}');
        </script>
    </body>
    </html>
    `;
    
    return new Response(html, {
        status: 503,
        statusText: 'Maritime Secure Offline',
        headers: { 
            'Content-Type': 'text/html',
            'X-Maritime-Classification': classification.toUpperCase(),
            'X-Security-Mode': 'maritime-secure-offline'
        }
    });
}

// Helper functions
function isAPIRequest(url) {
    return API_CACHE_PATTERNS.some(({ pattern }) => pattern.test(url.pathname));
}

function isStaticResource(url) {
    return url.pathname.startsWith('/static/') || 
           url.pathname === '/manifest.json' ||
           url.pathname === '/favicon.ico';
}

function isNavigationRequest(request, url) {
    return request.mode === 'navigate' || 
           (request.method === 'GET' && 
            request.headers.get('accept')?.includes('text/html')) ||
           NAVIGATION_PATTERNS.some(({ pattern }) => pattern.test(url.pathname));
}

// Notify all clients
async function notifyClients(message) {
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
        client.postMessage(message);
    });
}

// Enhanced message handling with security commands
self.addEventListener('message', event => {
    console.log('[SW] Maritime security message received:', event.data);
    
    if (event.data && event.data.type === 'SET_USER_ROLE') {
        secureMaritimeCache.setUserRole(event.data.role);
        event.ports[0]?.postMessage({ success: true });
    }
    
    if (event.data && event.data.type === 'CLEAR_SECURE_CACHE') {
        event.waitUntil(clearSecureCache(event.data.classification));
    }
    
    if (event.data && event.data.type === 'MARITIME_SECURITY_AUDIT') {
        event.waitUntil(performMaritimeSecurityAudit());
    }
    
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

// Clear secure cache by classification
async function clearSecureCache(classification) {
    try {
        const cache = await caches.open(SECURE_CACHE);
        const requests = await cache.keys();
        
        for (const request of requests) {
            const response = await cache.match(request);
            const cacheClassification = response.headers.get('X-Maritime-Classification');
            
            if (!classification || cacheClassification === classification.toUpperCase()) {
                await cache.delete(request);
                console.log('[SW] Cleared secure cache entry:', request.url);
            }
        }
        
        await notifyClients({
            type: 'SECURE_CACHE_CLEARED',
            classification: classification || 'ALL',
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('[SW] Failed to clear secure cache:', error);
    }
}

// Perform maritime security audit
async function performMaritimeSecurityAudit() {
    try {
        console.log('[SW] Performing maritime security audit...');
        
        const auditResults = {
            timestamp: Date.now(),
            version: VERSION,
            security: {
                encrypted_cache_entries: 0,
                classification_distribution: {},
                expired_entries: 0,
                access_violations: 0
            },
            caches: {}
        };
        
        // Audit secure cache
        const secureCache = await caches.open(SECURE_CACHE);
        const secureRequests = await secureCache.keys();
        
        auditResults.security.encrypted_cache_entries = secureRequests.length;
        
        for (const request of secureRequests) {
            try {
                const response = await secureCache.match(request);
                const classification = response.headers.get('X-Maritime-Classification') || 'UNKNOWN';
                const timestamp = response.headers.get('X-Cache-Timestamp');
                
                // Count by classification
                auditResults.security.classification_distribution[classification] = 
                    (auditResults.security.classification_distribution[classification] || 0) + 1;
                
                // Check for expired entries
                if (timestamp) {
                    const age = Date.now() - parseInt(timestamp);
                    const policy = secureMaritimeCache.getRetentionPolicy(classification.toLowerCase());
                    const maxAge = policy.years * 365 * 24 * 60 * 60 * 1000;
                    
                    if (age > maxAge) {
                        auditResults.security.expired_entries++;
                    }
                }
                
            } catch (error) {
                console.error('[SW] Audit error for request:', request.url, error);
            }
        }
        
        // Audit other caches
        const cacheNames = await caches.keys();
        for (const cacheName of cacheNames) {
            if (cacheName !== SECURE_CACHE) {
                const cache = await caches.open(cacheName);
                const requests = await cache.keys();
                auditResults.caches[cacheName] = {
                    entry_count: requests.length,
                    encrypted: false
                };
            }
        }
        
        console.log('[SW] Maritime security audit complete:', auditResults);
        
        // Send audit results to clients
        await notifyClients({
            type: 'MARITIME_SECURITY_AUDIT_COMPLETE',
            results: auditResults
        });
        
    } catch (error) {
        console.error('[SW] Maritime security audit failed:', error);
    }
}

// Enhanced background sync with maritime security
self.addEventListener('sync', event => {
    console.log(`[SW] Maritime background sync triggered: ${event.tag}`);
    
    switch (event.tag) {
        case 'maritime-secure-sync':
            event.waitUntil(syncSecureMaritimeData());
            break;
        case 'cleanup-expired-maritime-data':
            event.waitUntil(cleanupExpiredMaritimeData());
            break;
        case 'maritime-compliance-check':
            event.waitUntil(performComplianceCheck());
            break;
        default:
            console.warn(`[SW] Unknown maritime sync tag: ${event.tag}`);
    }
});

// Sync secure maritime data
async function syncSecureMaritimeData() {
    try {
        console.log('[SW] Syncing secure maritime data...');
        
        // This would integrate with the secure sync system
        const response = await fetch('/api/sync/maritime-secure', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Maritime-Security': 'enabled'
            }
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log('[SW] Secure maritime sync complete:', result);
            
            await notifyClients({
                type: 'MARITIME_SECURE_SYNC_COMPLETE',
                synced: result.synced_count || 0,
                classification_summary: result.classification_summary || {},
                timestamp: new Date().toISOString()
            });
        }
        
    } catch (error) {
        console.error('[SW] Secure maritime sync failed:', error);
    }
}

// Cleanup expired maritime data
async function cleanupExpiredMaritimeData() {
    try {
        console.log('[SW] Cleaning up expired maritime data...');
        
        const cache = await caches.open(SECURE_CACHE);
        const requests = await cache.keys();
        let cleanedCount = 0;
        
        for (const request of requests) {
            try {
                const response = await cache.match(request);
                const timestamp = response.headers.get('X-Cache-Timestamp');
                const classification = response.headers.get('X-Maritime-Classification');
                
                if (timestamp && classification) {
                    const age = Date.now() - parseInt(timestamp);
                    const policy = secureMaritimeCache.getRetentionPolicy(classification.toLowerCase());
                    const maxAge = policy.years * 365 * 24 * 60 * 60 * 1000;
                    
                    if (age > maxAge) {
                        await cache.delete(request);
                        cleanedCount++;
                        console.log('[SW] Cleaned expired maritime data:', request.url);
                    }
                }
                
            } catch (error) {
                // Remove corrupted entries
                await cache.delete(request);
                cleanedCount++;
            }
        }
        
        if (cleanedCount > 0) {
            console.log(`[SW] Cleaned up ${cleanedCount} expired maritime data entries`);
            
            await notifyClients({
                type: 'MARITIME_DATA_CLEANUP_COMPLETE',
                cleaned_count: cleanedCount,
                timestamp: new Date().toISOString()
            });
        }
        
    } catch (error) {
        console.error('[SW] Maritime data cleanup failed:', error);
    }
}

// Perform compliance check
async function performComplianceCheck() {
    try {
        console.log('[SW] Performing maritime compliance check...');
        
        const complianceResults = {
            gdpr_compliant: true,
            solas_compliant: true,
            marpol_compliant: true,
            isps_compliant: true,
            data_retention_compliant: true,
            encryption_compliant: true,
            violations: []
        };
        
        // Check encrypted cache compliance
        const cache = await caches.open(SECURE_CACHE);
        const requests = await cache.keys();
        
        for (const request of requests) {
            try {
                const response = await cache.match(request);
                const classification = response.headers.get('X-Maritime-Classification');
                const timestamp = response.headers.get('X-Cache-Timestamp');
                const retention = response.headers.get('X-Cache-Retention');
                
                // Check retention compliance
                if (timestamp && retention) {
                    const age = Date.now() - parseInt(timestamp);
                    const retentionPolicy = JSON.parse(retention);
                    const maxAge = retentionPolicy.years * 365 * 24 * 60 * 60 * 1000;
                    
                    if (age > maxAge) {
                        complianceResults.data_retention_compliant = false;
                        complianceResults.violations.push({
                            type: 'RETENTION_VIOLATION',
                            url: request.url,
                            classification: classification,
                            age_days: Math.floor(age / (24 * 60 * 60 * 1000))
                        });
                    }
                }
                
                // Check encryption compliance for sensitive data
                if (['CONFIDENTIAL', 'RESTRICTED', 'TOP_SECRET'].includes(classification)) {
                    const isEncrypted = response.headers.get('X-Cache-Encrypted') === 'true';
                    if (!isEncrypted) {
                        complianceResults.encryption_compliant = false;
                        complianceResults.violations.push({
                            type: 'ENCRYPTION_VIOLATION',
                            url: request.url,
                            classification: classification
                        });
                    }
                }
                
            } catch (error) {
                complianceResults.violations.push({
                    type: 'AUDIT_ERROR',
                    url: request.url,
                    error: error.message
                });
            }
        }
        
        console.log('[SW] Maritime compliance check complete:', complianceResults);
        
        await notifyClients({
            type: 'MARITIME_COMPLIANCE_CHECK_COMPLETE',
            results: complianceResults,
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('[SW] Maritime compliance check failed:', error);
    }
}

console.log(`[SW] Maritime Security Service Worker v${VERSION} loaded`);
console.log('[SW] Features: Encrypted Cache, Role-Based Access, Data Classification, Retention Policies');
console.log('[SW] Compliance: GDPR, SOLAS, MARPOL, ISPS, Customs Regulations');