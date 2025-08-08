"""
PWA Security Policies for Stevedores Dashboard 3.0
Content Security Policy and security configurations for offline PWA functionality
"""

import logging
from typing import Dict, Any, List, Optional
from flask import current_app, request, g
from dataclasses import dataclass

from .security_config import SecurityConfig

logger = logging.getLogger(__name__)

@dataclass
class PWASecurityConfig:
    """PWA-specific security configuration"""
    
    # CSP directives for offline functionality
    offline_cache_sources: List[str]
    worker_sources: List[str]
    indexed_db_allowed: bool
    web_crypto_allowed: bool
    
    # Offline authentication settings
    offline_token_storage: str  # 'indexeddb', 'localstorage', 'memory'
    token_encryption_enabled: bool
    offline_session_timeout: int  # minutes
    
    # Sync security settings
    sync_encryption_required: bool
    background_sync_allowed: bool
    periodic_sync_allowed: bool
    
    # Maritime-specific policies
    location_access_required: bool
    camera_access_for_cargo: bool
    offline_compliance_mode: bool

class PWASecurityPolicyManager:
    """Enhanced PWA security policy manager for maritime operations"""
    
    def __init__(self):
        self.base_config = SecurityConfig()
        self.pwa_config = self._load_pwa_config()
        
        # Maritime-specific security policies
        self.maritime_policies = {
            'cargo_photo_capture': {
                'camera_required': True,
                'geolocation_required': True,
                'offline_storage_encrypted': True,
                'compliance_audit': True
            },
            'vessel_tracking': {
                'geolocation_required': True,
                'background_sync_critical': True,
                'offline_cache_persistent': True,
                'data_classification': 'restricted'
            },
            'damage_reporting': {
                'offline_priority': 'critical',
                'immediate_sync_required': True,
                'photo_evidence_required': True,
                'location_verification': True
            },
            'customs_documentation': {
                'encryption_required': True,
                'audit_trail_mandatory': True,
                'offline_access_restricted': True,
                'compliance_retention': '7_years'
            }
        }
        
        logger.info("PWA security policy manager initialized")
    
    def _load_pwa_config(self) -> PWASecurityConfig:
        """Load PWA-specific security configuration"""
        
        # Default secure configuration for maritime operations
        return PWASecurityConfig(
            offline_cache_sources=[
                "'self'",
                "data:",
                "blob:",
                "https://fonts.googleapis.com",
                "https://fonts.gstatic.com",
                "*.maritime-cdn.com"  # Maritime-specific CDN
            ],
            worker_sources=[
                "'self'",
                "blob:",
                "'unsafe-inline'"  # Needed for dynamic worker creation
            ],
            indexed_db_allowed=True,
            web_crypto_allowed=True,
            offline_token_storage='indexeddb',
            token_encryption_enabled=True,
            offline_session_timeout=480,  # 8 hours for maritime shifts
            sync_encryption_required=True,
            background_sync_allowed=True,
            periodic_sync_allowed=True,
            location_access_required=True,  # Critical for maritime operations
            camera_access_for_cargo=True,
            offline_compliance_mode=True
        )
    
    def get_enhanced_csp_policy(self, route_context: Optional[str] = None) -> Dict[str, str]:
        """
        Generate enhanced CSP policy for PWA with maritime-specific requirements
        
        Args:
            route_context: Current route context for specialized policies
            
        Returns:
            Dict containing CSP directives
        """
        try:
            # Base CSP from security config
            base_csp = self.base_config.get_csp_policy()
            
            # Enhanced PWA CSP directives
            pwa_csp = {
                # Script sources - allow service worker and crypto operations
                'script-src': " ".join([
                    "'self'",
                    "'unsafe-inline'",  # Needed for service worker registration
                    "'unsafe-eval'",    # Needed for some PWA libraries (consider removing)
                    "blob:",            # For dynamic worker scripts
                    "data:",            # For inline scripts
                    "https://cdn.jsdelivr.net",  # For PWA libraries
                    "'sha256-" + self._calculate_sw_hash() + "'"  # Service worker hash
                ]),
                
                # Style sources - enhanced for offline styling
                'style-src': " ".join([
                    "'self'",
                    "'unsafe-inline'",
                    "https://fonts.googleapis.com",
                    "data:",
                    "blob:"
                ]),
                
                # Connect sources - API and sync endpoints
                'connect-src': " ".join([
                    "'self'",
                    "wss:",              # WebSocket for real-time updates
                    "https:",            # HTTPS APIs
                    "data:",
                    "blob:",
                    "*.maritime-api.com",  # Maritime data providers
                    "*.weather-api.com"    # Weather data for maritime operations
                ]),
                
                # Image sources - cargo photos and maritime imagery
                'img-src': " ".join([
                    "'self'",
                    "data:",
                    "blob:",
                    "https:",
                    "*.maritime-imagery.com",
                    "*.satellite-tracking.com"
                ]),
                
                # Font sources
                'font-src': " ".join([
                    "'self'",
                    "data:",
                    "https://fonts.gstatic.com"
                ]),
                
                # Media sources - for cargo inspection videos
                'media-src': " ".join([
                    "'self'",
                    "blob:",
                    "data:",
                    "mediastream:"  # For camera access
                ]),
                
                # Worker sources - service workers and shared workers
                'worker-src': " ".join(self.pwa_config.worker_sources),
                
                # Child sources - for iframes if needed
                'child-src': " ".join([
                    "'self'",
                    "blob:"
                ]),
                
                # Frame sources
                'frame-src': " ".join([
                    "'self'",
                    "blob:",
                    "data:",
                    "https://maps.google.com",     # Port maps
                    "https://marine-charts.com"   # Maritime charts
                ]),
                
                # Object sources - restrict plugins
                'object-src': "'none'",
                
                # Base URI restrictions
                'base-uri': "'self'",
                
                # Form action restrictions
                'form-action': "'self'",
                
                # Frame ancestors - prevent clickjacking
                'frame-ancestors': "'none'",
                
                # Manifest source
                'manifest-src': "'self'",
                
                # Upgrade insecure requests
                'upgrade-insecure-requests': '',
                
                # Block all mixed content
                'block-all-mixed-content': ''
            }
            
            # Route-specific CSP modifications
            if route_context:
                pwa_csp = self._apply_route_specific_csp(pwa_csp, route_context)
            
            # Merge with base CSP (PWA takes precedence)
            final_csp = {**base_csp, **pwa_csp}
            
            logger.debug(f"Generated enhanced CSP policy for route: {route_context}")
            return final_csp
            
        except Exception as e:
            logger.error(f"Failed to generate enhanced CSP policy: {e}")
            # Return restrictive fallback policy
            return {
                'default-src': "'self'",
                'script-src': "'self'",
                'style-src': "'self' 'unsafe-inline'",
                'img-src': "'self' data:",
                'connect-src': "'self'",
                'font-src': "'self'",
                'object-src': "'none'",
                'base-uri': "'self'",
                'form-action': "'self'",
                'frame-ancestors': "'none'"
            }
    
    def _calculate_sw_hash(self) -> str:
        """Calculate hash of service worker for CSP"""
        try:
            import hashlib
            import os
            
            sw_path = os.path.join('templates', 'service-worker.js')
            if os.path.exists(sw_path):
                with open(sw_path, 'rb') as f:
                    sw_content = f.read()
                return hashlib.sha256(sw_content).hexdigest()[:16]
            
            # Fallback hash for development
            return "dev-service-worker-hash"
            
        except Exception as e:
            logger.warning(f"Failed to calculate service worker hash: {e}")
            return "fallback-sw-hash"
    
    def _apply_route_specific_csp(self, csp: Dict[str, str], route_context: str) -> Dict[str, str]:
        """Apply route-specific CSP modifications"""
        
        try:
            # Cargo photography routes need camera access
            if route_context in ['cargo-photos', 'damage-inspection']:
                csp['media-src'] += " mediastream:"
                csp['img-src'] += " blob: data:"
                
            # Vessel tracking needs geolocation and background sync
            elif route_context in ['vessel-tracking', 'port-operations']:
                csp['connect-src'] += " *.gps-tracking.com *.port-authority.gov"
                
            # Document processing needs broader file access
            elif route_context in ['document-upload', 'manifest-processing']:
                csp['connect-src'] += " *.customs-api.gov *.shipping-docs.com"
                
            # Offline dashboard needs broader permissions
            elif route_context == 'offline-dashboard':
                # More permissive for offline functionality
                csp['script-src'] += " 'unsafe-eval'"  # For dynamic code generation
                csp['connect-src'] += " blob: data:"
                
            return csp
            
        except Exception as e:
            logger.warning(f"Failed to apply route-specific CSP: {e}")
            return csp
    
    def get_security_headers(self, route_context: Optional[str] = None) -> Dict[str, str]:
        """
        Generate comprehensive security headers for PWA
        
        Args:
            route_context: Current route context
            
        Returns:
            Dict containing security headers
        """
        try:
            # Base security headers
            headers = {
                # CSP header
                'Content-Security-Policy': self._format_csp_header(
                    self.get_enhanced_csp_policy(route_context)
                ),
                
                # HSTS - Enhanced for maritime critical operations
                'Strict-Transport-Security': 'max-age=63072000; includeSubDomains; preload',
                
                # X-Frame-Options - Prevent clickjacking
                'X-Frame-Options': 'DENY',
                
                # X-Content-Type-Options - Prevent MIME sniffing
                'X-Content-Type-Options': 'nosniff',
                
                # X-XSS-Protection - Enable XSS filtering
                'X-XSS-Protection': '1; mode=block',
                
                # Referrer Policy - Control referrer information
                'Referrer-Policy': 'strict-origin-when-cross-origin',
                
                # Permissions Policy - Control browser features
                'Permissions-Policy': self._get_permissions_policy(),
                
                # Feature Policy (fallback for older browsers)
                'Feature-Policy': self._get_feature_policy(),
                
                # Cross-Origin Policies
                'Cross-Origin-Embedder-Policy': 'require-corp',
                'Cross-Origin-Opener-Policy': 'same-origin',
                'Cross-Origin-Resource-Policy': 'same-origin',
                
                # Cache Control for PWA resources
                'Cache-Control': self._get_cache_control(route_context),
                
                # Maritime-specific headers
                'X-Maritime-PWA': 'stevedores-dashboard-3.0',
                'X-Offline-Capable': 'true',
                'X-Sync-Enabled': 'encrypted'
            }
            
            # Add route-specific headers
            if route_context:
                headers.update(self._get_route_specific_headers(route_context))
            
            return headers
            
        except Exception as e:
            logger.error(f"Failed to generate security headers: {e}")
            return {}
    
    def _format_csp_header(self, csp_policy: Dict[str, str]) -> str:
        """Format CSP policy as header string"""
        try:
            csp_parts = []
            for directive, sources in csp_policy.items():
                if sources:
                    csp_parts.append(f"{directive} {sources}")
                else:
                    csp_parts.append(directive)
            
            return "; ".join(csp_parts)
            
        except Exception as e:
            logger.error(f"Failed to format CSP header: {e}")
            return "default-src 'self'"
    
    def _get_permissions_policy(self) -> str:
        """Generate Permissions Policy header for maritime PWA"""
        
        policies = [
            # Camera access for cargo inspection
            "camera=(self)",
            
            # Geolocation for vessel tracking
            "geolocation=(self)",
            
            # Microphone for voice notes (restricted)
            "microphone=()",
            
            # Accelerometer for device orientation
            "accelerometer=(self)",
            
            # Gyroscope for stability monitoring
            "gyroscope=(self)",
            
            # Magnetometer for compass functionality
            "magnetometer=(self)",
            
            # Ambient light sensor
            "ambient-light-sensor=(self)",
            
            # Battery status for offline planning
            "battery=(self)",
            
            # Clipboard for data copying
            "clipboard-read=(self)",
            "clipboard-write=(self)",
            
            # Display capture (restricted)
            "display-capture=()",
            
            # Encrypted media (not needed)
            "encrypted-media=()",
            
            # Fullscreen for maritime charts
            "fullscreen=(self)",
            
            # Gamepad (not needed)
            "gamepad=()",
            
            # MIDI (not needed)
            "midi=()",
            
            # Notifications for maritime alerts
            "notifications=(self)",
            
            # Payment (not needed for this PWA)
            "payment=()",
            
            # Picture-in-picture (restricted)
            "picture-in-picture=()",
            
            # Speaker selection
            "speaker-selection=(self)",
            
            # Sync background for critical operations
            "sync-xhr=(self)",
            
            # USB (not needed)
            "usb=()",
            
            # Web share for data export
            "web-share=(self)",
            
            # XR/VR (not needed)
            "xr-spatial-tracking=()"
        ]
        
        return ", ".join(policies)
    
    def _get_feature_policy(self) -> str:
        """Generate Feature Policy header (fallback for older browsers)"""
        
        policies = [
            "camera 'self'",
            "geolocation 'self'",
            "microphone 'none'",
            "accelerometer 'self'",
            "gyroscope 'self'",
            "magnetometer 'self'",
            "ambient-light-sensor 'self'",
            "battery 'self'",
            "notifications 'self'",
            "payment 'none'",
            "usb 'none'"
        ]
        
        return "; ".join(policies)
    
    def _get_cache_control(self, route_context: Optional[str]) -> str:
        """Generate cache control header based on route context"""
        
        # Static assets - long cache
        if route_context in ['static-assets', 'service-worker']:
            return "public, max-age=31536000, immutable"
        
        # API responses - short cache with revalidation
        elif route_context in ['api-response']:
            return "private, max-age=300, must-revalidate"
        
        # Critical maritime data - no cache
        elif route_context in ['vessel-status', 'emergency-data']:
            return "no-cache, no-store, must-revalidate"
        
        # Default PWA cache
        else:
            return "public, max-age=3600, must-revalidate"
    
    def _get_route_specific_headers(self, route_context: str) -> Dict[str, str]:
        """Get headers specific to route context"""
        
        headers = {}
        
        # Cargo photo routes
        if route_context in ['cargo-photos', 'damage-inspection']:
            headers.update({
                'X-Camera-Required': 'true',
                'X-Location-Required': 'true',
                'X-Offline-Storage': 'encrypted'
            })
        
        # Vessel tracking routes
        elif route_context in ['vessel-tracking', 'port-operations']:
            headers.update({
                'X-Realtime-Updates': 'critical',
                'X-Background-Sync': 'required',
                'X-Location-Precision': 'high'
            })
        
        # Document processing routes
        elif route_context in ['document-upload', 'manifest-processing']:
            headers.update({
                'X-File-Encryption': 'required',
                'X-Compliance-Audit': 'mandatory',
                'X-Retention-Period': '7-years'
            })
        
        # Emergency routes
        elif route_context in ['emergency-reporting', 'distress-calls']:
            headers.update({
                'X-Priority': 'critical',
                'X-Immediate-Sync': 'required',
                'X-Offline-Fallback': 'disabled'
            })
        
        return headers
    
    def validate_pwa_security(self, request_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate PWA security requirements for maritime operations
        
        Args:
            request_context: Current request context
            
        Returns:
            Dict containing validation results
        """
        try:
            validation = {
                'valid': True,
                'warnings': [],
                'errors': [],
                'maritime_compliance': True,
                'offline_capable': True
            }
            
            # Check HTTPS requirement
            if not request_context.get('is_secure', False):
                validation['errors'].append('HTTPS required for PWA functionality')
                validation['valid'] = False
            
            # Check service worker support
            if not request_context.get('service_worker_supported', True):
                validation['warnings'].append('Service worker not supported - offline functionality limited')
                validation['offline_capable'] = False
            
            # Check required APIs for maritime operations
            required_apis = ['indexeddb', 'crypto', 'cache', 'background_sync']
            missing_apis = []
            
            for api in required_apis:
                if not request_context.get(f'{api}_supported', True):
                    missing_apis.append(api)
            
            if missing_apis:
                validation['warnings'].append(f'Missing API support: {", ".join(missing_apis)}')
                if 'crypto' in missing_apis:
                    validation['maritime_compliance'] = False
            
            # Check location access for vessel tracking
            if request_context.get('route_context') in ['vessel-tracking', 'port-operations']:
                if not request_context.get('geolocation_available', True):
                    validation['errors'].append('Geolocation required for vessel tracking')
                    validation['valid'] = False
            
            # Check camera access for cargo inspection
            if request_context.get('route_context') in ['cargo-photos', 'damage-inspection']:
                if not request_context.get('camera_available', True):
                    validation['warnings'].append('Camera access recommended for cargo inspection')
            
            # Check offline storage capacity
            storage_quota = request_context.get('storage_quota', 0)
            if storage_quota < 50 * 1024 * 1024:  # 50MB minimum
                validation['warnings'].append('Low storage quota - offline functionality may be limited')
            
            return validation
            
        except Exception as e:
            logger.error(f"Failed to validate PWA security: {e}")
            return {
                'valid': False,
                'errors': [f'Validation error: {str(e)}'],
                'warnings': [],
                'maritime_compliance': False,
                'offline_capable': False
            }
    
    def get_maritime_policy(self, operation_type: str) -> Dict[str, Any]:
        """
        Get maritime-specific security policy for operation type
        
        Args:
            operation_type: Type of maritime operation
            
        Returns:
            Dict containing maritime security policy
        """
        try:
            base_policy = {
                'encryption_required': True,
                'audit_required': True,
                'offline_allowed': True,
                'sync_priority': 'normal',
                'retention_period': '7_years',
                'compliance_flags': ['maritime', 'operational']
            }
            
            # Get specific policy
            specific_policy = self.maritime_policies.get(operation_type, {})
            
            # Merge policies
            policy = {**base_policy, **specific_policy}
            
            # Add timestamp and validation
            policy['policy_version'] = '3.0.0'
            policy['generated_at'] = logger.handlers[0].formatter.formatTime(logger.makeRecord(
                'pwa_security', logging.INFO, '', 0, '', (), None
            )) if logger.handlers else 'unknown'
            
            return policy
            
        except Exception as e:
            logger.error(f"Failed to get maritime policy for {operation_type}: {e}")
            return base_policy
    
    def apply_security_headers(self, response, route_context: Optional[str] = None):
        """
        Apply security headers to Flask response
        
        Args:
            response: Flask response object
            route_context: Current route context
        """
        try:
            headers = self.get_security_headers(route_context)
            
            for header_name, header_value in headers.items():
                response.headers[header_name] = header_value
            
            logger.debug(f"Applied {len(headers)} security headers")
            
        except Exception as e:
            logger.error(f"Failed to apply security headers: {e}")

# Global PWA security policy manager
pwa_security = PWASecurityPolicyManager()

def get_pwa_security_manager() -> PWASecurityPolicyManager:
    """Get the global PWA security policy manager"""
    return pwa_security

def apply_pwa_security_headers(response, route_context: Optional[str] = None):
    """
    Convenience function to apply PWA security headers
    
    Args:
        response: Flask response object
        route_context: Current route context
    """
    pwa_security.apply_security_headers(response, route_context)

def validate_maritime_pwa_request(request_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Convenience function to validate maritime PWA request
    
    Args:
        request_data: Request context data
        
    Returns:
        Dict containing validation results
    """
    if request_data is None:
        # Build request context from Flask request
        request_data = {
            'is_secure': request.is_secure if request else False,
            'user_agent': request.headers.get('User-Agent', '') if request else '',
            'route_context': getattr(g, 'route_context', None) if g else None
        }
    
    return pwa_security.validate_pwa_security(request_data)