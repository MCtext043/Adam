#!/usr/bin/env bash
set -eu

REMOTE_DIR="__REMOTE_DIR__"
mkdir -p "$REMOTE_DIR"
cd "$REMOTE_DIR"

if [ -f .env ]; then
  cp .env ".env.backup.$(date +%Y%m%d%H%M%S)"
else
  touch .env
fi

sed -i 's/\xEF\xBB\xBF//g; s/\r$//' .env

for key in SMTP_HOST SMTP_PORT SMTP_USE_TLS SMTP_USER SMTP_PASSWORD SMTP_FROM SMTP_FROM_NAME SESSION_SECRET ADMIN_USERNAME ADMIN_PASSWORD; do
  sed -i "/^${key}=/d" .env
done

cat /tmp/adam-smtp.env >> .env
sed -i 's/\xEF\xBB\xBF//g; s/\r$//' .env

if grep -q '^SMTP_USER=' .env; then
  u=$(grep '^SMTP_USER=' .env | head -1 | cut -d= -f2-)
  if [ -n "$u" ]; then
    sed -i "s/^SMTP_FROM=.*/SMTP_FROM=$u/" .env
  fi
fi

tar -xzf /tmp/adam-deploy.tar.gz -C "$REMOTE_DIR"

docker compose --profile app up -d --build --force-recreate
docker compose ps

echo "=== SMTP inside container (no password) ==="
docker exec adam-web python -c 'from app.email_service import smtp_ready, resolve_sender; h,u,p,f,pt,tls=resolve_sender(); print("smtp_ready=", smtp_ready()); print("host=", h); print("user=", u or "EMPTY"); print("from=", f); print("port=", pt, "tls=", tls); print("password_set=", bool(p))' || true

echo "Waiting for app health..."
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${APP_PORT:-8010}/health"; then
    echo
    echo "Health check passed."
    rm -f /tmp/adam-deploy.tar.gz /tmp/adam-smtp.env /tmp/adam-deploy-remote.sh
    exit 0
  fi
  sleep 2
done

echo "Health check failed. Last app logs:"
docker logs --tail=120 adam-web || true
exit 1
