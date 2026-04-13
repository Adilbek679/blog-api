# ---------------------------------------------------------------------------
# Blog API — Dockerfile
# Base image: python:3.12-slim (minimal Debian-based image)
# ---------------------------------------------------------------------------

FROM python:3.12-slim

# Set environment variables:
# PYTHONDONTWRITEBYTECODE — prevents .pyc files
# PYTHONUNBUFFERED       — forces stdout/stderr to be unbuffered (better logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System dependencies:
# gettext  — required by Django's compilemessages command
# curl     — used in entrypoint to wait for Redis
# gcc      — needed to compile some Python C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    gettext \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user to run the application.
# Running as root inside a container is a security risk.
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Set working directory.
WORKDIR /app

# Install Python dependencies first (before copying code) so that Docker
# can cache this layer — rebuilds are faster when only code changes.
COPY requirements/base.txt requirements/base.txt
COPY requirements/prod.txt requirements/prod.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements/prod.txt

# Copy project source code.
COPY . .

# Create directories that the app writes to at runtime.
RUN mkdir -p logs media staticfiles \
    && chown -R appuser:appgroup /app

# Switch to non-root user.
USER appuser

# Expose the port Daphne listens on.
EXPOSE 8000

# Entrypoint script handles: wait-for-Redis, migrate, collectstatic,
# compilemessages, optional seed, then exec the CMD.
ENTRYPOINT ["scripts/entrypoint.sh"]

# Default command — run Daphne ASGI server (required for WebSockets).
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "settings.asgi:application"]
