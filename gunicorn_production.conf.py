"""
Production Gunicorn configuration for Stevedores Dashboard 3.0.
Optimized for memory constraints and high availability.
"""

import os
import multiprocessing
from utils.memory_monitor_production import calculate_optimal_workers

# Memory-aware worker calculation
MEMORY_LIMIT_MB = int(os.getenv('MEMORY_LIMIT_MB', 512))
workers = calculate_optimal_workers(MEMORY_LIMIT_MB)

# Worker configuration
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
worker_tmp_dir = "/dev/shm"

# Preload for memory efficiency
preload_app = True

# Timeout settings
timeout = 30
keepalive = 2

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Bind configuration
bind = f"0.0.0.0:{os.getenv('PORT', 8000)}"

# Process naming
proc_name = "stevedores-dashboard-3.0"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Memory optimization
def when_ready(server):
    """Called when the server is started."""
    server.log.info("🚢 Stevedores Dashboard 3.0 production server started")
    server.log.info(f"Workers: {workers}, Memory limit: {MEMORY_LIMIT_MB}MB")

def worker_int(worker):
    """Called when a worker receives the INT or QUIT signal."""
    worker.log.info("Worker received INT/QUIT signal")

def on_exit(server):
    """Called when the server is stopped."""
    server.log.info("🚢 Stevedores Dashboard 3.0 production server stopped")

# Production hooks
def post_fork(server, worker):
    """Called after worker fork."""
    server.log.info(f"Worker {worker.pid} forked")
    
    # Start memory monitoring in worker
    try:
        from utils.memory_monitor_production import start_production_monitoring
        start_production_monitoring()
    except ImportError:
        pass

def worker_exit(server, worker):
    """Called when a worker is exiting."""
    server.log.info(f"Worker {worker.pid} exiting")

# Performance settings
sendfile = True
tcp_nopush = True
tcp_nodelay = True