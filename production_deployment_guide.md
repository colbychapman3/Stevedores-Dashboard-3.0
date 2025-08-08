# 🚢 Stevedores Dashboard 3.0 - Production Deployment Guide

## 🚨 CRITICAL FIXES APPLIED

This deployment guide covers the **5 CRITICAL production issues** that have been identified and resolved:

### ✅ Issues Fixed

1. **Redis Connection Resilience** - Circuit breaker pattern with in-memory fallback
2. **Memory Overflow Prevention** - Memory-aware worker scaling and monitoring
3. **Flask-Talisman CSP Configuration** - Proper CSP directive format and initialization
4. **Rate Limiting Fallbacks** - Graceful degradation when Redis unavailable
5. **Worker Optimization** - Container-aware worker calculation

## 🛠️ Pre-Deployment Checklist

### Environment Variables (Required)
```bash
# Security (REQUIRED)
SECRET_KEY=your-production-secret-key-min-32-chars

# Database (REQUIRED)
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Redis (Optional - fallback to memory if not provided)
REDIS_URL=redis://user:pass@host:6379/0

# Container Configuration
MEMORY_LIMIT_MB=512
WEB_WORKERS=4

# Optional: Monitoring
SENTRY_DSN=your-sentry-dsn
LOG_LEVEL=INFO
```

### Memory Configuration
- **Container Memory**: 512MB (adjust `MEMORY_LIMIT_MB`)
- **Worker Count**: Auto-calculated based on memory (max 8 workers for 512MB)
- **Per-Worker Memory**: ~64MB estimated
- **Memory Monitoring**: Enabled with 75%/85% warning/critical thresholds

## 📊 Production Architecture

```
┌─────────────────────────────────────────┐
│           Load Balancer                 │
│         /health (every 30s)            │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│           Gunicorn Master               │
│     Workers: Memory-Aware (1-8)        │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│          Flask Application              │
│    ┌─────────────────────────────────┐  │
│    │      Circuit Breakers           │  │
│    │  ┌─────────┐  ┌─────────────┐   │  │
│    │  │  Redis  │  │ Memory      │   │  │
│    │  │ Client  │  │ Monitor     │   │  │
│    │  └─────────┘  └─────────────┘   │  │
│    └─────────────────────────────────┘  │
│    ┌─────────────────────────────────┐  │
│    │      Security Middleware        │  │
│    │  ┌─────────┐  ┌─────────────┐   │  │
│    │  │  CSP    │  │ Rate        │   │  │
│    │  │ Headers │  │ Limiting    │   │  │
│    │  └─────────┘  └─────────────┘   │  │
│    └─────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## 🚀 Deployment Steps

### 1. Render.com Deployment

```bash
# Set environment variables in Render dashboard
SECRET_KEY=your-production-secret-key
DATABASE_URL=your-supabase-postgres-url
REDIS_URL=your-upstash-redis-url
MEMORY_LIMIT_MB=512
WEB_WORKERS=4
```

### 2. Docker Deployment

```bash
# Build and run with production settings
docker build -t stevedores-dashboard:3.0 .
docker run -d \
  --name stevedores-production \
  -p 8000:8000 \
  -e SECRET_KEY=your-secret \
  -e DATABASE_URL=your-db-url \
  -e REDIS_URL=your-redis-url \
  -e MEMORY_LIMIT_MB=512 \
  stevedores-dashboard:3.0
```

### 3. Manual Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Run with production configuration
export FLASK_ENV=production
export FLASK_CONFIG=render
gunicorn -c gunicorn.conf.py wsgi:application
```

## 🔍 Health Check Endpoints

### Primary Health Check (`/health`)
- **Comprehensive**: Tests all dependencies
- **Response Time**: ~100-300ms
- **Use**: Load balancer health checks

```json
{
  "status": "healthy|degraded|unhealthy",
  "timestamp": "2025-01-06T12:00:00Z",
  "checks": {
    "database": {"status": "healthy", "response_time_ms": 45.2},
    "redis": {"status": "healthy", "circuit_breaker_state": "closed"},
    "security": {"status": "healthy", "talisman_initialized": true},
    "memory": {"status": "healthy", "memory_usage_percent": 62.5}
  },
  "summary": {"total_checks": 7, "passed": 7, "failed": 0}
}
```

### Quick Health Check (`/health/quick`)
- **Fast**: Uses cached results
- **Response Time**: ~5-10ms
- **Use**: High-frequency monitoring

## 📈 Monitoring & Alerting

### Memory Monitoring
- **Warning**: 75% memory usage (384MB of 512MB)
- **Critical**: 85% memory usage (435MB of 512MB)
- **Action**: Automatic garbage collection, worker restart

### Redis Circuit Breaker
- **Failure Threshold**: 5 consecutive failures
- **Recovery Timeout**: 60 seconds
- **Fallback**: In-memory caching

### Rate Limiting
- **Default Limits**: 1000/hour, 100/minute
- **Storage**: Redis with memory fallback
- **Graceful**: No user-facing errors on Redis failure

## 🔒 Security Configuration

### Flask-Talisman (Content Security Policy)
```python
CSP = {
    'default-src': "'self'",
    'script-src': ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"],
    'style-src': ["'self'", "'unsafe-inline'"],
    'img-src': ["'self'", "data:", "https:"]
}
```

### Security Headers
- HTTPS enforcement (production)
- HSTS: 1 year
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff

## 🚨 Troubleshooting

### Issue: Redis Connection Errors
```bash
# Check Redis connectivity
curl -X GET "http://your-app/health" | jq '.checks.redis'

# Expected fallback behavior:
{
  "status": "error",
  "fallback": "in-memory",
  "circuit_breaker_state": "open"
}
```

### Issue: Memory Overflow
```bash
# Check memory usage
curl -X GET "http://your-app/health" | jq '.checks.memory'

# Force garbage collection via monitoring endpoint
# (Implementation in production_monitoring.py)
```

### Issue: Worker Spawning
```bash
# Check worker count calculation
docker logs container-name | grep "worker configuration"

# Expected output:
# Container Memory: 512MB
# Max Workers by Memory: 8
# Final Workers: 4
```

### Issue: CSP Errors
```bash
# Check security middleware
curl -X GET "http://your-app/health" | jq '.checks.security'

# Expected:
{
  "status": "healthy",
  "talisman_initialized": true,
  "csp_enabled": true
}
```

## 📊 Performance Benchmarks

### Expected Performance (512MB container)
- **Response Time**: < 200ms (95th percentile)
- **Throughput**: 100+ requests/second
- **Memory Usage**: < 400MB steady state
- **CPU Usage**: < 70% under normal load

### Load Testing
```bash
# Test with ab (Apache Bench)
ab -n 1000 -c 10 http://your-app/health/quick

# Expected results:
# Requests per second: 200+ [#/sec]
# Time per request: < 50ms [ms]
# Failed requests: 0
```

## 🔧 Maintenance

### Log Monitoring
```bash
# Key log patterns to monitor
grep "CRITICAL\|ERROR" logs/stevedores_dashboard.log
grep "Circuit breaker OPEN" logs/stevedores_dashboard.log
grep "Memory usage high" logs/stevedores_dashboard.log
```

### Graceful Shutdown
```bash
# Send SIGTERM for graceful shutdown
kill -TERM $(pgrep -f gunicorn)

# Wait for workers to finish requests (max 30 seconds)
# Memory monitor automatically stops
```

### Database Maintenance
```bash
# Health check includes connection pool status
curl -X GET "http://your-app/health" | jq '.checks.database.pool_size'
```

## ✅ Production Readiness Checklist

- [ ] SECRET_KEY environment variable set (32+ characters)
- [ ] DATABASE_URL pointing to production database
- [ ] REDIS_URL configured (optional)
- [ ] Memory limits configured (MEMORY_LIMIT_MB)
- [ ] HTTPS certificates installed
- [ ] Load balancer health checks configured
- [ ] Monitoring alerts set up
- [ ] Backup procedures tested
- [ ] Rollback plan documented
- [ ] Performance benchmarks completed

## 🎯 Success Metrics

**Deployment is successful when:**
1. `/health` returns 200 status with all checks passing
2. Application handles 100+ concurrent users without errors
3. Memory usage remains under 85% threshold
4. Redis failures don't cause application errors
5. Security headers present in all responses

---
*Stevedores Dashboard 3.0 - Production Ready Maritime Operations Platform*