# Football Platform

Монорепозиторий веб-платформы для проведения любительских футбольных турниров. Сейчас реализован публичный read-only API на Django, Django Ninja и PostgreSQL.

## Требования

- Docker Engine и Docker Compose v2;
- либо Python 3.12 и PostgreSQL 16 для запуска без Docker.

## Запуск в Docker

```bash
cp .env.example .env
docker compose up --build
```

API будет доступен по адресу `http://localhost:8000/api/v1/`, Swagger UI — `http://localhost:8000/api/v1/docs`, а OpenAPI JSON — `http://localhost:8000/api/v1/openapi.json`. Проверки состояния: `GET /api/v1/health/live` (само приложение) и `GET /api/v1/health/ready` (приложение и PostgreSQL).

`backend` применяет миграции при старте. Данные PostgreSQL сохраняются в именованном volume `postgres_data`.

Полезные команды:

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_demo
docker compose exec backend ruff check .
```

`seed_demo` создаёт данные только при явном запуске и не участвует в работе API автоматически.

## Конфигурация

Все параметры перечислены в `.env.example`. Для Docker `POSTGRES_HOST` принудительно указывает на сервис `postgres`. `DJANGO_CORS_ALLOWED_ORIGINS` принимает список разрешённых origin через запятую; по умолчанию разрешений нет. Секреты и рабочий `.env` не должны попадать в Git.

## Локальный запуск без Docker

Установите зависимости из `backend/Pipfile`, задайте переменные PostgreSQL из `.env.example`, затем выполните из `backend/`:

```bash
python manage.py migrate
python manage.py runserver
```

## Контракт API

Описание маршрутов, примеры и правила таблицы находятся в [docs/api-contract.md](docs/api-contract.md). Текущий API не включает аутентификацию, изменение данных, заявки, составы команд, турнирные группы, live-протоколы и уведомления.
