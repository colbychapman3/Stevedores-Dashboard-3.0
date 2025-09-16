# 📊 Render Log Monitoring Guide

## 🚀 Auto-Deploy Setup

Your repository is configured for **automatic deployment** on every push to `main` branch.

### View Deployment Logs

**Option 1: Render Dashboard**
1. Go to https://dashboard.render.com
2. Find "stevedores-dashboard-3-0" service
3. Click "Logs" tab
4. See real-time deployment and runtime logs

**Option 2: Render CLI (Recommended)**
```bash
# Install Render CLI
npm install -g @renderinc/cli

# Login to Render
render login

# View live logs (auto-refreshes)
render logs stevedores-dashboard-3-0

# View deployment logs only
render logs stevedores-dashboard-3-0 --type deploy

# Tail logs (follow new logs)
render logs stevedores-dashboard-3-0 --tail
```

**Option 3: Webhook Integration**
```bash
# Get deployment status via webhook
curl https://api.render.com/v1/services/YOUR_SERVICE_ID/deploys \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## 📋 What to Look For in Logs

**✅ Successful Deployment:**
```
🚢 STEVEDORES DASHBOARD 3.0.6-PRODUCTION-FIX STARTING...
✅ Production memory monitoring started
✅ Redis circuit breaker reset to CLOSED
✅ Worker 123 forked successfully
```

**❌ Common Issues:**
```
❌ Redis circuit breaker OPENED
❌ Memory critical: 85.2%
❌ Worker exiting (out of memory)
❌ Database connection failed
```

## 🔔 Quick Log Commands

```bash
# Check recent deployment
render logs stevedores-dashboard-3-0 --since 5m

# Filter for errors only
render logs stevedores-dashboard-3-0 | grep -E "(ERROR|CRITICAL|❌)"

# Monitor memory issues
render logs stevedores-dashboard-3-0 | grep -E "(memory|Memory|OOM)"

# Watch Redis status
render logs stevedores-dashboard-3-0 | grep -E "(Redis|redis|circuit)"
```

## ⚡ Auto-Deploy Process

Every time you push to `main`:
1. **Render detects** the push via webhook
2. **Build starts** automatically using `render.yaml`
3. **Logs appear** in real-time in dashboard/CLI
4. **Health check** runs at `/health/quick`
5. **Production traffic** switches to new deployment

**Deployment typically takes 2-3 minutes.**