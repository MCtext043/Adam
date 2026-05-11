#!/usr/bin/env bash
# Запуск на сервере: bash deploy/diagnose-server.sh
set -e
echo "=== Docker ==="
docker ps -a 2>/dev/null || echo "Docker не установлен или нет прав"
echo
echo "=== Порт 8010 локально ==="
curl -sS -o /dev/null -w "%{http_code}" --connect-timeout 3 http://127.0.0.1:8010/health || echo " нет ответа"
echo
curl -sS --connect-timeout 3 http://127.0.0.1:8010/health || true
echo
echo "=== UFW (если есть) ==="
sudo ufw status 2>/dev/null || echo "ufw не используется или нет sudo"
echo
echo "=== Слушает ли кто-то 8010 ==="
ss -tlnp 2>/dev/null | grep 8010 || netstat -tlnp 2>/dev/null | grep 8010 || echo "не найдено (или нет ss/netstat)"
