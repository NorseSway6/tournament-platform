# Football Platform

Монорепозиторий веб-платформы для проведения любительских футбольных турниров. Backend использует Django, Django Ninja и PostgreSQL; публичные GET-маршруты доступны гостям, изменяющие операции защищены access-токеном и ролевыми областями.

## Требования

- Docker Engine и Docker Compose v2;
- либо pyenv с Python 3.12, Pipenv и PostgreSQL 16 для запуска без Docker.

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

Установите Python через pyenv, затем зависимости из `backend/Pipfile` через Pipenv и задайте переменные PostgreSQL из `.env.example`:

```bash
pyenv install 3.12.18
cd backend
pyenv local 3.12.18
pipenv install --dev
pipenv run python manage.py migrate
pipenv run python manage.py runserver
```

В разработке access-токен живёт 15 минут, refresh-токен — до 30 дней и ротируется при обновлении. Для запросов используйте `Authorization: Bearer <access_token>`. Организаторские области назначаются в Django admin в карточке организации или турнира; капитан определяется полем `Team.captain`, судья — назначением `MatchOfficial`.

Если база уже применяла старую миграцию `identity_access.0002_tokensession_userrole`, перенесите сохранённые роли до миграции, удаляющей старую таблицу:

```bash
pipenv run python manage.py migrate organizations 0003_organizationmember
pipenv run python manage.py migrate tournaments 0003_tournamentmember
pipenv run python manage.py backfill_legacy_roles
pipenv run python manage.py migrate
```

Команда переносит администраторов и организаторские области и безопасна при повторном запуске. Капитан и судья уже определяются существующими связями `Team.captain` и `MatchOfficial`.

## Контракт API

Описание маршрутов, примеры и правила таблицы находятся в [docs/api-contract.md](docs/api-contract.md). Регистрация, вход, обновление и отзыв токенов доступны в `/api/v1/auth/`; полная ролевая модель описана в API-контракте. Статeless-архитектура не используется: refresh-сессии хранятся в PostgreSQL, а отзыв сессии сразу прекращает действие связанных access-токенов.
