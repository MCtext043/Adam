#!/usr/bin/env bash
# Nginx + Let's Encrypt для kafeadam.ru. Вызывается из remote-deploy.sh
set -eu

REMOTE_DIR="${1:-/opt/adam-delivery}"
DOMAIN="kafeadam.ru"
CERT_PATH="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"

CERTBOT_EMAIL=""
if [ -f "${REMOTE_DIR}/.env" ]; then
  CERTBOT_EMAIL=$(grep '^CERTBOT_EMAIL=' "${REMOTE_DIR}/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '\r' || true)
fi

echo "=== HTTPS: install nginx & certbot if needed ==="
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -qq || true
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx certbot python3-certbot-nginx 2>/dev/null || \
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx certbot 2>/dev/null || true
fi

mkdir -p /var/www/certbot
mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled

cids=$(docker ps -q --filter "publish=80" 2>/dev/null || true)
if [ -n "$cids" ]; then
  for cid in $cids; do
    name=$(docker inspect --format '{{.Name}}' "$cid" 2>/dev/null | sed 's|^/||' || echo "?")
    if [ "$name" = "adam-web" ]; then
      echo "Stopping adam-web on :80 (will use :8010 behind nginx)..."
      docker stop "$cid" || true
    fi
  done
fi

NGINX_SSL="${REMOTE_DIR}/deploy/nginx/kafeadam.conf"
NGINX_HTTP="${REMOTE_DIR}/deploy/nginx/kafeadam-http-only.conf"

if [ -f "$CERT_PATH" ]; then
  echo "=== HTTPS: certificate found, enabling SSL config ==="
  cp "$NGINX_SSL" /etc/nginx/sites-available/kafeadam
else
  echo "=== HTTPS: no certificate yet, HTTP proxy config ==="
  cp "$NGINX_HTTP" /etc/nginx/sites-available/kafeadam
  if [ -n "${CERTBOT_EMAIL:-}" ]; then
    echo "=== HTTPS: requesting certificate (certbot) ==="
    systemctl enable nginx 2>/dev/null || true
    systemctl start nginx 2>/dev/null || true
    nginx -t && systemctl reload nginx 2>/dev/null || true
    certbot certonly --webroot -w /var/www/certbot \
      -d "$DOMAIN" -d "www.$DOMAIN" \
      --email "$CERTBOT_EMAIL" --agree-tos --non-interactive --no-eff-email \
      && cp "$NGINX_SSL" /etc/nginx/sites-available/kafeadam \
      || echo "WARNING: certbot failed — site stays on HTTP until certificate is issued."
  else
    echo "WARNING: set CERTBOT_EMAIL in .env to auto-issue Let's Encrypt certificate."
  fi
fi

ln -sf /etc/nginx/sites-available/kafeadam /etc/nginx/sites-enabled/kafeadam
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

if nginx -t; then
  systemctl enable nginx 2>/dev/null || true
  systemctl restart nginx
  echo "=== Nginx OK ==="
else
  echo "ERROR: nginx config test failed"
  exit 1
fi

if [ -f "$CERT_PATH" ]; then
  echo "HTTPS: https://${DOMAIN}"
else
  echo "HTTP only (no cert): http://${DOMAIN}"
fi
