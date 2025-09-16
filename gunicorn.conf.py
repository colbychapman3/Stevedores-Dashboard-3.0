"""
Gunicorn Configuration for Stevedores Dashboard 3.0 Production
Optimized for maritime operations with high availability
"""

import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', 8000)}"
backlog = 2048

# Worker processes - ENHANCED: Memory-aware worker calculation with monitoring integration
# Container memory limit awareness (default 512MB)
container_memory_mb = int(os.environ.get('MEMORY_LIMIT_MB', 512))

# Dynamic worker calculation based on memory monitoring
def calculate_optimal_workers():
    """Calculate optimal workers using memory monitor if available"""
    try:
        # Try to use memory monitor for dynamic calculation
        from utils.memory_monitor import MemoryMonitor
        monitor = MemoryMonitor()
        optimal = monitor.calculate_optimal_workers()
        print(f"   Memory monitor optimal workers: {optimal}")
        return optimal
    except:
        # Fallback to static calculation
        memory_per_worker_mb = 48  # Conservative estimate for 512MB containers
        max_workers_by_memory = max(1, (container_memory_mb - 128) // memory_per_worker_mb)
        cpu_workers = multiprocessing.cpu_count() * 2 + 1
        return min(max_workers_by_memory, cpu_workers, 6)  # Cap at 6 for 512MB

# Use dynamic calculation
calculated_workers = calculate_optimal_workers()

# Allow override but with safety limits
workers = int(os.environ.get('WEB_WORKERS', calculated_workers))
workers = max(1, min(workers, 6))  # Hard limit for 512MB containers

worker_class = 'sync'  # Standard worker for Render deployment
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

print(f"🔧 Gunicorn worker configuration:")
print(f"   Container Memory: {container_memory_mb}MB")
print(f"   Calculated Workers: {calculated_workers}")
print(f"   Final Workers: {workers}")

# Timeout configuration (important for maritime operations)
timeout = 120  # 2 minutes for long-running operations
keepalive = 5
graceful_timeout = 30

# Logging
accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('LOG_LEVEL', 'info').lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'stevedores-dashboard-3.0'

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# SSL (if certificates are provided)
keyfile = os.environ.get('SSL_KEYFILE')
certfile = os.environ.get('SSL_CERTFILE')

# Preload application for better performance
preload_app = True

# Worker lifecycle hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("🚢 Stevedores Dashboard 3.0 - Master process starting")
    server.log.info(f"⚓ Workers: {workers}, Worker class: {worker_class}")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("🔄 Reloading workers...")

def worker_int(worker):
    """Called just after a worker has been signalled."""
    worker.log.info(f"Worker {worker.pid} received INT signal")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    server.log.info(f"🔧 Worker {worker.age} pre-fork")

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info(f"✅ Worker {worker.pid} forked successfully")

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    worker.log.info(f"🚀 Worker {worker.pid} initialized - Maritime operations ready")
    
    # Initialize memory monitoring for this worker
    try:
        from utils.memory_monitor import init_memory_monitor
        monitor = init_memory_monitor(
            warning_threshold=75.0,    # 75% for 512MB containers
            critical_threshold=85.0    # 85% critical threshold
        )
        worker.log.info(f"💾 Memory monitor initialized for worker {worker.pid} "
                       f"(Limit: {monitor.memory_limit / (1024**2):.0f}MB)")
        
        # Register worker-specific cleanup callback
        def worker_cleanup():
            worker.log.info(f"Worker {worker.pid} cleanup callback executed")
        
        monitor.register_cleanup_callback(worker_cleanup)
        
    except Exception as e:
        worker.log.error(f"Failed to initialize memory monitor for worker {worker.pid}: {e}")

def worker_abort(worker):
    """Called when a worker receives the SIGABRT signal."""
    worker.log.error(f"❌ Worker {worker.pid} aborted")
    
    # Log memory state on abort for debugging
    try:
        from utils.memory_monitor import get_memory_monitor
        monitor = get_memory_monitor()
        if monitor:
            usage = monitor.get_memory_usage()
            worker.log.error(f"Memory state at abort: {usage.get('container', {}).get('percent', 0):.1f}%")
    except:
        pass

def when_ready(server):
    """Called just after the server is started."""
    server.log.info("⚓ Stevedores Dashboard 3.0 production server ready!")
    server.log.info(f"🌐 Listening on {bind}")
    server.log.info("🚢 Maritime operations system fully operational")

def on_exit(server):
    """Called just before exiting."""
    server.log.info("🛑 Stevedores Dashboard 3.0 shutting down...")
    
    # Log final memory statistics
    try:
        from utils.memory_monitor import get_memory_monitor
        monitor = get_memory_monitor()
        if monitor:
            monitor.stop_monitoring()
            final_usage = monitor.get_memory_usage()
            server.log.info(f"Final memory usage: {final_usage.get('container', {}).get('percent', 0):.1f}%")
            server.log.info(f"Total GC operations: {monitor.gc_frequency}")
            server.log.info(f"Total memory alerts: {len(monitor.alert_history)}")
    except Exception as e:
        server.log.warning(f"Failed to get final memory stats: {e}")
    
    server.log.info("⚓ Maritime operations system offline")

def worker_exit(server, worker):
    """Called when a worker is exiting."""
    server.log.info(f"👋 Worker {worker.pid} exiting gracefully")
    
    # Stop memory monitoring for this worker
    try:
        from utils.memory_monitor import get_memory_monitor
        monitor = get_memory_monitor()
        if monitor:
            monitor.stop_monitoring()
            server.log.info(f"Memory monitoring stopped for worker {worker.pid}")
    except:
        pass

# Performance tuning
worker_tmp_dir = '/dev/shm'  # Use RAM for worker temp files
tmp_upload_dir = None

# Graceful handling of worker failures
max_requests_jitter = 50
preload_app = True
daemon = False

# Environment variables for application
raw_env = [
    'FLASK_ENV=production',
    'FLASK_CONFIG=production',
    f'PWA_CACHE_VERSION=3.0.1',
]

# Add any additional environment variables
for key, value in os.environ.items():
    if key.startswith(('DATABASE_', 'REDIS_', 'MAIL_', 'VAPID_', 'SENTRY_')):
        raw_env.append(f'{key}={value}')

# Memory-aware worker restart configuration
# Restart workers after this many requests (prevent memory leaks)
max_requests = int(os.environ.get('MAX_REQUESTS', 800))  # Lower for containers
max_requests_jitter = int(os.environ.get('MAX_REQUESTS_JITTER', 100))

# Memory-based worker timeout (allow more time for memory cleanup)
worker_timeout = int(os.environ.get('WORKER_TIMEOUT', 90))  # Longer for memory operations

# Increase worker memory limit
worker_rlimit_nofile = 1024
worker_rlimit_core = 0

# Security headers middleware
def post_worker_init(worker):
    """Initialize worker with security middleware"""
    from werkzeug.middleware.proxy_fix import ProxyFix
    
    # Trust proxy headers (for load balancers)
    worker.wsgi = ProxyFix(worker.wsgi, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    
    worker.log.info(f"🔒 Worker {worker.pid} security middleware initialized")