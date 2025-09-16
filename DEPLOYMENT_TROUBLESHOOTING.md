# Deployment Troubleshooting Guide
## Stevedores Dashboard 3.0 Production Validation System

This guide helps troubleshoot the silent deployment failures where workers start but never become ready to serve traffic.

## Quick Diagnosis

### 1. Run Production Validation
```bash
# Comprehensive pre-deployment validation
python production_validation.py --output validation_results.json

# Quick startup validation
python startup_validator.py --exit-on-failure
```

### 2. Check Health Endpoints
```bash
# Quick health check
curl http://localhost:5000/health/quick

# Detailed system health
curl http://localhost:5000/health/detailed

# Standard health check
curl http://localhost:5000/health
```

## Common Silent Failure Patterns

### Pattern 1: Missing Environment Variables
**Symptom:** Workers start but exit after 56 seconds
**Cause:** SECRET_KEY or DATABASE_URL not set

**Solution:**
```bash
# Check environment variables
python -c "import os; print('SECRET_KEY:', 'SET' if os.environ.get('SECRET_KEY') else 'MISSING')"
python -c "import os; print('DATABASE_URL:', 'SET' if os.environ.get('DATABASE_URL') else 'MISSING')"

# Validate with production validation
python production_validation.py | grep -A5 "Environment Variables"
```

### Pattern 2: Configuration Loading Failure
**Symptom:** Import errors during configuration loading
**Cause:** render_config.py or production_config.py import failures

**Solution:**
```bash
# Test configuration imports
python -c "from render_config import config; print('render_config:', list(config.keys()))"
python -c "from production_config import config; print('production_config:', list(config.keys()))"

# Check with validation
python production_validation.py | grep -A10 "Configuration Loading"
```

### Pattern 3: Database Connectivity Issues
**Symptom:** Workers start but can't connect to database
**Cause:** Invalid DATABASE_URL, network issues, or database server problems

**Solution:**
```bash
# Test database connectivity
python -c "
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ.get('DATABASE_URL'))
with engine.connect() as conn:
    result = conn.execute(text('SELECT 1'))
    print('Database OK:', result.fetchone())
"

# Validate with enhanced checks
python production_validation.py | grep -A10 "Database Connectivity"
```

### Pattern 4: Model Import Failures
**Symptom:** Silent failure during model loading
**Cause:** Model factory functions fail to create model classes

**Solution:**
```bash
# Test model imports
python -c "
from models.user import create_user_model
from models.vessel import create_vessel_model
from models.cargo_tally import create_cargo_tally_model
print('Model factories imported successfully')
"

# Check model creation with validation
python production_validation.py | grep -A10 "Model Import"
```

### Pattern 5: Security Middleware Loading Issues
**Symptom:** Middleware initialization failures
**Cause:** Missing security modules or initialization errors

**Solution:**
```bash
# Test security imports
python -c "
from utils.security_manager import init_security_manager
from utils.jwt_auth import init_jwt_auth
from utils.audit_logger import init_audit_logger
print('Security modules imported successfully')
"

# Validate security systems
python production_validation.py | grep -A10 "Security Middleware"
```

## Environment Validation Checklist

### Critical Environment Variables
- [ ] `SECRET_KEY` - Required for Flask security
- [ ] `DATABASE_URL` - Required for database connectivity
- [ ] `FLASK_CONFIG` - Configuration selector (default: 'render')

### Optional Environment Variables
- [ ] `REDIS_URL` - For caching and sessions
- [ ] `MAIL_SERVER` - For email notifications
- [ ] `SENTRY_DSN` - For error monitoring
- [ ] `LOG_LEVEL` - Logging verbosity

### File System Permissions
- [ ] `/tmp/stevedores_uploads` - Upload directory writable
- [ ] `instance/logs` - Log directory writable
- [ ] `logs` - Application logs writable

## Resource Monitoring

### System Requirements
- **Memory:** Minimum 512MB available, warning at 85% usage
- **CPU:** Warning at 80% usage, critical at 95%
- **Disk:** Minimum 1GB free space

### Check Resources
```bash
# Monitor during startup
python production_validation.py | grep -A10 "Resource Monitoring"

# System metrics
python -c "
import psutil
print(f'Memory: {psutil.virtual_memory().percent}%')
print(f'CPU: {psutil.cpu_percent()}%')
print(f'Disk: {psutil.disk_usage(\"/\").percent}%')
"
```

## Advanced Troubleshooting

### Enable Debug Logging
```bash
# Set debug environment
export FLASK_ENV=development
export LOG_LEVEL=DEBUG

# Run with enhanced logging
python wsgi.py
```

### Check WSGI Startup
```bash
# Monitor WSGI startup logs
python wsgi.py 2>&1 | tee startup_logs.txt

# Check for specific errors
grep -i "error\|fail\|critical" startup_logs.txt
```

### Database Troubleshooting
```bash
# Test database connection with timeout
python -c "
import os
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
try:
    engine = create_engine(os.environ.get('DATABASE_URL'), pool_pre_ping=True)
    with engine.connect() as conn:
        print('Database connection successful')
except OperationalError as e:
    print(f'Database connection failed: {e}')
"

# Check database schema
python -c "
from app import app, db
with app.app_context():
    print('Tables:', db.engine.table_names())
"
```

## Production Deployment Validation

### Pre-deployment Checklist
1. **Run validation suite:**
   ```bash
   python startup_validator.py --exit-on-failure
   ```

2. **Test WSGI application:**
   ```bash
   python wsgi.py &
   PID=$!
   sleep 5
   curl -f http://localhost:5000/health/quick || echo "Health check failed"
   kill $PID
   ```

3. **Validate configuration:**
   ```bash
   python production_validation.py --output pre_deploy_validation.json
   ```

### Post-deployment Verification
1. **Health check endpoints:**
   ```bash
   curl -f https://your-app.com/health/quick
   curl -f https://your-app.com/health/detailed
   ```

2. **Monitor logs:**
   ```bash
   # Check for startup completion
   grep "Application ready to serve requests" logs/
   
   # Check for errors
   grep -i "error\|fail\|critical" logs/
   ```

3. **Test core functionality:**
   ```bash
   # Test authentication
   curl -f https://your-app.com/auth/login
   
   # Test dashboard
   curl -f https://your-app.com/dashboard
   ```

## Emergency Recovery

### Graceful Degradation Mode
If some features fail, the application continues with reduced functionality:

- **Security manager fails:** Authentication still works via Flask-Login
- **JWT manager fails:** Basic session authentication available
- **Audit logger fails:** Application continues without audit trails
- **Database retry fails:** Basic database connectivity maintained

### Error Recovery Steps
1. **Check validation results:**
   ```bash
   python production_validation.py | grep "FAIL\|CRITICAL"
   ```

2. **Fix critical issues first:**
   - Missing SECRET_KEY
   - Invalid DATABASE_URL
   - Configuration import failures

3. **Restart with enhanced logging:**
   ```bash
   export LOG_LEVEL=DEBUG
   python wsgi.py
   ```

4. **Monitor startup progression:**
   ```bash
   tail -f startup_logs.txt | grep -E "(✅|❌|⚠️)"
   ```

## Support Information

### Log Analysis
- **WSGI logs:** Startup and configuration issues
- **Application logs:** Runtime errors and warnings
- **Health check logs:** System status and diagnostics
- **Validation logs:** Pre-deployment issue detection

### Performance Metrics
- **Startup time:** Should complete in < 30 seconds
- **Memory usage:** Should stabilize < 200MB for small deployments
- **Database connection time:** Should be < 1000ms

### Contact Points
- **Validation failures:** Check `validation_results.json`
- **Health check failures:** Use `/health/detailed` endpoint
- **Startup failures:** Review WSGI startup logs
- **Runtime issues:** Monitor application logs

---

**Remember:** The production validation system is designed to catch issues before they cause silent failures. Always run validation before deployment and monitor health endpoints after deployment.