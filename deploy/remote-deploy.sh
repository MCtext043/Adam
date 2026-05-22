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

# Сайт «Адам» на порту 80 (SmartWallet больше не используется)
sed -i '/^APP_PORT=/d' .env
echo 'APP_PORT=80' >> .env
sed -i 's/\r$//' .env

tar -xzf /tmp/adam-deploy.tar.gz -C "$REMOTE_DIR"

echo "=== Free port 80 (stop other Docker containers) ==="
for cid in $(docker ps -q --filter "publish=80" 2>/dev/null || true); do
  name=$(docker inspect --format '{{.Name}}' "$cid" 2>/dev/null | sed 's|^/||' || echo "unknown")
  if [ "$name" != "adam-web" ]; then
    echo "Stopping container on :80 -> $name"
    docker stop "$cid" || true
  fi
done

echo "=== Nginx: release port 80 if needed ==="
if [ -d /etc/nginx/sites-enabled ]; then
  rm -f /etc/nginx/sites-enabled/kafeadam 2>/dev/null || true
  nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null || true
fi
if ss -tlnp 2>/dev/null | grep ':80 ' | grep -q nginx; then
  echo "Stopping nginx (was using port 80)..."
  systemctl stop nginx 2>/dev/null || true
fi

docker compose --profile app down 2>/dev/null || true
docker compose --profile app up -d --build --force-recreate
docker compose ps

echo "=== SMTP inside container (no password) ==="
docker exec adam-web python -c 'from app.email_service import smtp_ready, resolve_sender; h,u,p,f,pt,tls=resolve_sender(); print("smtp_ready=", smtp_ready()); print("host=", h); print("user=", u or "EMPTY"); print("from=", f); print("port=", pt, "tls=", tls); print("password_set=", bool(p))' || true

APP_PORT=80
echo "Site URL: http://kafeadam.ru (port 80)"
echo "Waiting for app health..."
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${APP_PORT}/health"; then
    echo
    echo "Health check passed on port ${APP_PORT}."
    rm -f /tmp/adam-deploy.tar.gz /tmp/adam-smtp.env /tmp/adam-deploy-remote.sh
    exit 0
  fi
  sleep 2
done

echo "Health check failed. Port 80 listeners:"
ss -tlnp 2>/dev/null | grep ':80 ' || true
echo "Last app logs:"
docker logs --tail=120 adam-web || true
exit 1
