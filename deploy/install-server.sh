#!/usr/bin/env bash
# Запуск на сервере (из каталога с проектом, рядом с docker-compose.yml).
# Перед первым запуском создайте .env — см. deploy/server.env.sample

set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "Установите Docker и Docker Compose v2, затем повторите."
  exit 1
fi

if [ ! -f .env ]; then
  echo "Создайте файл .env (скопируйте deploy/server.env.sample и заполните POSTGRES_PASSWORD)."
  exit 1
fi

docker compose --profile app up -d --build

echo "Готово. Проверка: curl -sS http://127.0.0.1:${APP_PORT:-8010}/health"
echo "Сайт: http://$(hostname -I | awk '{print $1}'):${APP_PORT:-8010}"
