# Football Platform

Веб-платформа для проведения любительских футбольных турниров.

## Запуск

1. Создать `.env` файл в корне. Все параметры перечислены в `.env.example`

2. Запустить приложение

```bash
make up
make migrate
```

3. Создать суперпользователя, если нужна админка (необязательно):

```bash
make createsuperuser
```

4. Заполнить БД данными для упрощения проверки эндпоинтов (необязательно):

```
docker compose exec backend python manage.py seed_demo
```

API: `http://localhost:8000/api/v1/`

Swagger UI: `http://localhost:8000/api/v1/docs`

OpenAPI JSON — `http://localhost:8000/api/v1/openapi.json`
