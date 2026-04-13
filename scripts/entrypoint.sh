#!/bin/bash
# ---------------------------------------------------------------------------
# Blog API — Entrypoint Script
# ---------------------------------------------------------------------------

set -e

echo "==> Waiting for Redis..."

REDIS_URL="${BLOG_REDIS_URL:-redis://redis:6379/0}"
REDIS_HOST=$(echo "$REDIS_URL" | sed 's|redis://||' | cut -d: -f1)
REDIS_PORT=$(echo "$REDIS_URL" | sed 's|redis://||' | cut -d: -f2 | cut -d/ -f1)

MAX_RETRIES=30
RETRY=0

# Use Python to ping Redis — no redis-cli needed in the image.
until python -c "
import socket, sys
try:
    s = socket.create_connection(('$REDIS_HOST', $REDIS_PORT), timeout=1)
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    RETRY=$((RETRY + 1))
    if [ "$RETRY" -ge "$MAX_RETRIES" ]; then
        echo "ERROR: Redis not available after ${MAX_RETRIES}s. Exiting."
        exit 1
    fi
    echo "    Redis not ready yet (attempt $RETRY/$MAX_RETRIES)..."
    sleep 1
done

echo "==> Redis is ready."

# ---------------------------------------------------------------------------
# Run setup steps only for the web service (CMD starts with "daphne").
# ---------------------------------------------------------------------------
if echo "$*" | grep -q "daphne"; then

    echo "==> Running database migrations..."
    python manage.py migrate --noinput
    echo "==> Migrations complete."

    echo "==> Collecting static files..."
    python manage.py collectstatic --noinput
    echo "==> Static files collected."

    echo "==> Compiling translation messages..."
    python manage.py compilemessages
    echo "==> Translations compiled."

    if [ "${BLOG_SEED_DB:-false}" = "true" ]; then
        echo "==> Seeding database..."
        python manage.py seed
        echo "==> Database seeded."
    fi

fi

echo "==> Starting: $*"
exec "$@"