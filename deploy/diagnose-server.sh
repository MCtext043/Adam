#!/usr/bin/env bash
# Запуск на сервере: bash deploy/diagnose-server.sh
set -e
echo "=== Docker ==="
docker ps -a 2>/dev/null || echo "Docker не установлен или нет прав"
echo
APP_PORT="${APP_PORT:-80}"
echo "=== Порт ${APP_PORT} локально ==="
curl -sS -o /dev/null -w "%{http_code}" --connect-timeout 3 "http://127.0.0.1:${APP_PORT}/health" || echo " нет ответа"
echo
curl -sS --connect-timeout 3 "http://127.0.0.1:${APP_PORT}/health" || true
echo
echo "=== UFW (если есть) ==="
sudo ufw status 2>/dev/null || echo "ufw не используется или нет sudo"
echo
echo "=== Слушает ли кто-то 80 и 8010 ==="
ss -tlnp 2>/dev/null | grep -E ':80 |:8010 ' || netstat -tlnp 2>/dev/null | grep -E ':80 |:8010 ' || echo "не найдено"
