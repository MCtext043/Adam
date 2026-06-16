#!/usr/bin/env bash
set -eu

REMOTE_DIR="__REMOTE_DIR__"
mkdir -p "$REMOTE_DIR"
cd "$REMOTE_DIR"

echo "=== Docker (install if missing) ==="
if ! command -v docker >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ca-certificates curl
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker 2>/dev/null || true
    systemctl start docker 2>/dev/null || true
  else
    echo "ERROR: docker not found and apt-get unavailable"
    exit 1
  fi
fi
docker compose version >/dev/null 2>&1 || docker compose version 2>/dev/null || true

if [ -f .env ]; then
  cp .env ".env.backup.$(date +%Y%m%d%H%M%S)"
else
  touch .env
fi

sed -i 's/\xEF\xBB\xBF//g; s/\r$//' .env

while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    ''|\#*) continue ;;
    *=*)
      key="${line%%=*}"
      sed -i "/^${key}=/d" .env
      ;;
  esac
done < /tmp/adam-smtp.env

cat /tmp/adam-smtp.env >> .env

if ! grep -q '^SESSION_SECRET=.' .env 2>/dev/null; then
  sed -i '/^SESSION_SECRET=/d' .env
  echo "SESSION_SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p -c 64)" >> .env
fi
if ! grep -q '^POSTGRES_PASSWORD=.' .env 2>/dev/null; then
  echo "POSTGRES_PASSWORD=$(openssl rand -hex 16 2>/dev/null || head -c 16 /dev/urandom | xxd -p -c 32)" >> .env
fi
sed -i 's/\xEF\xBB\xBF//g; s/\r$//' .env

if grep -q '^SMTP_USER=' .env; then
  u=$(grep '^SMTP_USER=' .env | head -1 | cut -d= -f2-)
  if [ -n "$u" ]; then
    sed -i "s/^SMTP_FROM=.*/SMTP_FROM=$u/" .env
  fi
fi

# Приложение за nginx на localhost:8010, снаружи — HTTPS :443
sed -i '/^APP_PORT=/d' .env
echo 'APP_PORT=8010' >> .env
sed -i '/^APP_PORT_MAPPING=/d' .env
echo 'APP_PORT_MAPPING=127.0.0.1:8010:8000' >> .env
if ! grep -q '^PUBLIC_BASE_URL=https://' .env 2>/dev/null; then
  sed -i '/^PUBLIC_BASE_URL=/d' .env
  echo 'PUBLIC_BASE_URL=https://kafeadam.ru' >> .env
fi
if ! grep -q '^SESSION_COOKIE_SECURE=' .env 2>/dev/null; then
  echo 'SESSION_COOKIE_SECURE=true' >> .env
fi
sed -i 's/\r$//' .env

tar -xzf /tmp/adam-deploy.tar.gz -C "$REMOTE_DIR"

# Windows checkout may ship CRLF in shell scripts
find "${REMOTE_DIR}/deploy" -type f \( -name '*.sh' -o -name '*.conf' \) -exec sed -i 's/\r$//' {} + 2>/dev/null || true

echo "=== Free port 80 (stop Docker containers on :80) ==="
cids=$(docker ps -q --filter "publish=80" 2>/dev/null || true)
if [ -n "$cids" ]; then
  for cid in $cids; do
    name=$(docker inspect --format '{{.Name}}' "$cid" 2>/dev/null | sed 's|^/||' || echo "unknown")
    echo "Stopping container on :80 -> $name"
    docker stop "$cid" || true
  done
fi

docker compose --profile app down 2>/dev/null || true

echo "=== Docker: clear stale build cache (fixes 'parent snapshot does not exist') ==="
docker builder prune -af 2>/dev/null || true
docker buildx prune -af 2>/dev/null || true

echo "=== Docker build & start ==="
if ! docker compose --profile app up -d --build --force-recreate; then
  echo "Build failed — retrying with --no-cache..."
  docker builder prune -af 2>/dev/null || true
  docker buildx prune -af 2>/dev/null || true
  docker compose --profile app build --no-cache
  docker compose --profile app up -d --force-recreate
fi
docker compose ps

echo "=== Nginx + HTTPS ==="
sed -i 's/\r$//' "${REMOTE_DIR}/deploy/setup-https.sh" 2>/dev/null || true
chmod +x "${REMOTE_DIR}/deploy/setup-https.sh" 2>/dev/null || true
bash "${REMOTE_DIR}/deploy/setup-https.sh" "${REMOTE_DIR}" || {
  echo "WARNING: HTTPS setup failed — app may still work on http://127.0.0.1:8010"
}

echo "=== SMTP inside container (no password) ==="
docker exec adam-web python -c 'from app.email_service import smtp_ready, resolve_sender; h,u,p,f,pt,tls=resolve_sender(); print("smtp_ready=", smtp_ready()); print("host=", h); print("user=", u or "EMPTY"); print("from=", f); print("port=", pt, "tls=", tls); print("password_set=", bool(p))' || true

echo "=== Menu from data/vk_menu.json ==="
docker exec adam-web python -c '
from pathlib import Path
from app.main import VK_MENU_PATH, load_vk_menu_items, startup_session, import_vk_products
print("menu_file_exists=", Path(VK_MENU_PATH).is_file())
items = load_vk_menu_items()
print("menu_items=", len(items))
with startup_session() as session:
    print("menu_sync_changes=", import_vk_products(session))
' || true

APP_PORT=8010
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo "Site URL: https://kafeadam.ru (after DNS) or http://${SERVER_IP}/"
echo "Waiting for app health..."
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${APP_PORT}/health"; then
    echo
    echo "Health check passed on 127.0.0.1:${APP_PORT}."
    if curl -fsS "http://${SERVER_IP}/health" 2>/dev/null; then
      echo
      echo "HTTP via server IP passed."
    fi
    if curl -fsS "https://kafeadam.ru/health" 2>/dev/null; then
      echo
      echo "HTTPS health check passed."
    fi
    rm -f /tmp/adam-deploy.tar.gz /tmp/adam-smtp.env /tmp/adam-deploy-remote.sh
    exit 0
  fi
  sleep 2
done

echo "Health check failed. Port 8010 listeners:"
ss -tlnp 2>/dev/null | grep ':8010 ' || true
echo "Nginx status:"
systemctl is-active nginx 2>/dev/null || true
echo "Last app logs:"
docker logs --tail=120 adam-web || true
exit 1
