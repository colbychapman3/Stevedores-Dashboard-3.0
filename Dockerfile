# Multi-stage Docker build for Stevedores Dashboard 3.0
# Optimized for maritime operations with minimal attack surface

# Build stage
FROM python:3.11-slim as builder

LABEL maintainer="Stevedores Dashboard Team"
LABEL description="Maritime stevedoring operations management system"
LABEL version="3.0.1"

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create build user
RUN useradd --create-home --shell /bin/bash build
USER build
WORKDIR /home/build

# Copy requirements and install Python dependencies
COPY --chown=build:build requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create application user
RUN useradd --create-home --shell /bin/bash --uid 1001 stevedores
USER stevedores
WORKDIR /home/stevedores

# Copy Python dependencies from builder stage
COPY --from=builder --chown=stevedores:stevedores /home/build/.local /home/stevedores/.local

# Make sure scripts in .local are usable
ENV PATH=/home/stevedores/.local/bin:$PATH

# Copy application code
COPY --chown=stevedores:stevedores . .

# Create necessary directories
RUN mkdir -p logs static/icons tmp uploads

# Generate placeholder icons if they don't exist
RUN python3 -c "
import os
from pathlib import Path

icon_dir = Path('static/icons')
icon_dir.mkdir(exist_ok=True)

# Create minimal placeholder icons
for size in [72, 96, 128, 144, 152, 192, 384, 512]:
    icon_path = icon_dir / f'icon-{size}x{size}.png'
    if not icon_path.exists():
        # Create a simple colored square as placeholder
        print(f'Creating placeholder icon: {icon_path}')
        icon_path.touch()
"

# Switch back to root for final setup
USER root

# Copy nginx configuration
COPY docker/nginx.conf /etc/nginx/sites-available/stevedores-dashboard
RUN ln -sf /etc/nginx/sites-available/stevedores-dashboard /etc/nginx/sites-enabled/default

# Copy supervisor configuration
COPY docker/supervisord.conf /etc/supervisor/conf.d/stevedores-dashboard.conf

# Create production directories
RUN mkdir -p /var/log/stevedores-dashboard \
    && chown -R stevedores:stevedores /var/log/stevedores-dashboard

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

# Environment variables
ENV FLASK_ENV=production
ENV FLASK_CONFIG=production
ENV PYTHONPATH=/home/stevedores
ENV WEB_WORKERS=4

# Expose ports
EXPOSE 80 443

# Volume for persistent data
VOLUME ["/home/stevedores/instance", "/home/stevedores/logs", "/var/log/stevedores-dashboard"]

# Start services using supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]

# Metadata
LABEL org.opencontainers.image.title="Stevedores Dashboard 3.0"
LABEL org.opencontainers.image.description="Advanced maritime stevedoring operations management system with offline capabilities"
LABEL org.opencontainers.image.version="3.0.1"
LABEL org.opencontainers.image.vendor="Maritime Operations Systems"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/maritime/stevedores-dashboard-3.0"