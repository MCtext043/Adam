# Кафе «Адам» — доставка

Монолитное приложение на FastAPI для доставки кафе «Адам»: витрина товаров, корзина, оформление заказа (демо) и админ-панель текущих заказов.

## Возможности

- FastAPI + Jinja2 (страницы и API в одном приложении)
- PostgreSQL, SQLAlchemy, автосоздание таблиц и демо-меню при старте
- Главная: меню, поиск и фильтры по категориям, корзина, оформление заказа
- Админка `/admin`: состав заказа, телефон, адрес, смена статуса (заказы со статусом `done` в списке не показываются)
- Проверка готовности: `GET /health` (включая запрос к БД)

## Локальный запуск

1. `pip install -r requirements.txt`
2. Поднять только PostgreSQL: `docker compose up -d`
3. Скопировать `.env.example` в `.env` и при необходимости поправить `DATABASE_URL`
4. `uvicorn app.main:app --reload --port 8010`

Сайт: http://127.0.0.1:8010 · Админка: http://127.0.0.1:8010/admin

## Выгрузка на сервер (Docker)

Подготовлены **`Dockerfile`** и **`docker-compose.yml`** (профиль `app` для контейнера с приложением).

### Один сервер: приложение + PostgreSQL в Docker

На сервере установите Docker и Docker Compose v2.

1. Скопируйте проект на сервер (git clone или архив).
2. Создайте файл `.env` рядом с `docker-compose.yml`:

   ```env
   POSTGRES_PASSWORD=надёжный_пароль
   APP_PORT=8010
   ```

   При другом пароле строка для приложения задаётся так (если не используете только `POSTGRES_PASSWORD`):

   ```env
   DATABASE_URL=postgresql+psycopg://postgres:надёжный_пароль@postgres:5432/adam_delivery
   ```

   В `docker-compose.yml` для сервиса `web` можно заменить блок `environment` на чтение из `.env` через `env_file: .env`.

3. Сборка и запуск:

   ```bash
   docker compose --profile app up -d --build
   ```

4. Откройте `http://IP_СЕРВЕРА:8010` (или настройте reverse proxy на порт `APP_PORT`).

Полезно для мониторинга: `GET http://IP:8010/health`

### Развёртывание на VPS (пример: Ubuntu + Docker)

С этой машины автоматический вход по паролю SSH недоступен — выполните шаги вручную после `ssh root@ВАШ_IP`.

1. На сервере установите [Docker Engine](https://docs.docker.com/engine/install/) и плагин Compose v2.

2. Скопируйте проект (без `.venv`), например:

   ```bash
   rsync -avz --exclude '.venv' --exclude '.git' --exclude '__pycache__' \
     ./ root@45.11.26.79:/opt/adam-delivery/
   ```

   Или `git clone` в `/opt/adam-delivery`, если репозиторий уже на GitHub/GitLab.

3. На сервере:

   ```bash
   cd /opt/adam-delivery
   cp deploy/server.env.sample .env
   nano .env   # POSTGRES_PASSWORD, при необходимости APP_PORT / POSTGRES_PORT_MAPPING
   chmod +x deploy/install-server.sh
   ./deploy/install-server.sh
   ```

   Шаблон `.env`: сайт на порту **8010**, PostgreSQL с хоста только через **127.0.0.1:8009** (не торчит в интернет).

4. Откройте в браузере: `http://45.11.26.79:8010` и `http://45.11.26.79:8010/admin`.

5. Фаервол (если включён `ufw`): `ufw allow 8010/tcp` и `ufw reload`.

Если с вашего ПК сайт по `http://IP:8010` не открывается, на сервере выполните `bash deploy/diagnose-server.sh` и пришлите вывод. Частые причины: контейнеры не запущены; **ufw/облачный firewall** не пускает порт **8010** (откройте в панели провайдера и в `ufw`).

Порт **80** у вас уже занят другим сервисом — сайт «Адам» на нём не появится сам. Варианты: открыть **8010** снаружи или настроить **Nginx** на отдельный `server_name`/домен (см. `deploy/nginx-adam.example.conf`).

**Безопасность:** пароль root, отправленный в чат, считается скомпрометированным — смените его на сервере и **не используйте тот же пароль для PostgreSQL** (`POSTGRES_PASSWORD` в `.env` должен быть отдельным).

### Внешняя PostgreSQL (managed DB)

Собирайте и запускайте только образ приложения (без профиля `app` в compose или свой compose-файл):

```bash
docker build -t adam-delivery .
docker run -d --name adam-web -p 8010:8000 \
  -e DATABASE_URL="postgresql+psycopg://USER:PASSWORD@HOST:5432/adam_delivery" \
  -e WEB_CONCURRENCY=2 \
  adam-delivery
```

Убедитесь, что с сервера приложения открыт доступ к хосту и порту БД.

### Nginx (кратко)

Типичная схема: Nginx слушает 443, проксирует на `127.0.0.1:8010`. Укажите заголовки `Host`, `X-Forwarded-For`, `X-Forwarded-Proto` при необходимости.

### Что уточнить при необходимости

- Домен и HTTPS (Nginx + Let's Encrypt)
- Отдельный пользователь Linux вместо `root` для деплоя

