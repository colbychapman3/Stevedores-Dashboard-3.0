"""
Gunicorn Configuration for Stevedores Dashboard 3.0 Production
Optimized for maritime operations with high availability
"""

import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', 8000)}"
backlog = 2048

# Worker processes
workers = int(os.environ.get('WEB_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'gevent'  # Async worker for better I/O handling
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

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

def worker_abort(worker):
    """Called when a worker receives the SIGABRT signal."""
    worker.log.error(f"❌ Worker {worker.pid} aborted")

def when_ready(server):
    """Called just after the server is started."""
    server.log.info("⚓ Stevedores Dashboard 3.0 production server ready!")
    server.log.info(f"🌐 Listening on {bind}")
    server.log.info("🚢 Maritime operations system fully operational")

def on_exit(server):
    """Called just before exiting."""
    server.log.info("🛑 Stevedores Dashboard 3.0 shutting down...")
    server.log.info("⚓ Maritime operations system offline")

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

# Restart workers after this many requests (prevent memory leaks)
max_requests = 1000
max_requests_jitter = 100

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