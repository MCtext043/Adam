# Кафе «Адам» — доставка

Монолитное приложение на FastAPI для доставки кафе «Адам»: витрина товаров, корзина, оформление тестового заказа и админ-панель текущих заказов.

## Что внутри

- FastAPI backend и HTML-страницы в одном приложении.
- PostgreSQL через SQLAlchemy.
- Seed-товары создаются автоматически при первом запуске.
- Главная страница: меню, корзина, форма заказа.
- Админ-панель `/admin`: состав заказа, телефон, адрес, комментарий и смена статуса.

## Запуск

1. Установите зависимости:

```bash
pip install -r requirements.txt
```

2. Поднимите PostgreSQL через Docker:

```bash
docker compose up -d
```

Или создайте PostgreSQL-базу вручную:

```sql
CREATE DATABASE adam_delivery;
```

3. Укажите подключение, если оно отличается от стандартного:

```bash
set DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/adam_delivery
```

Для PowerShell:

```powershell
$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5433/adam_delivery"
```

4. Запустите сервер:

```bash
uvicorn app.main:app --reload --port 8010
```

Откройте сайт: http://127.0.0.1:8010

Админ-панель: http://127.0.0.1:8010/admin
