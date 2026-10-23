ENV_FILE := .env
ifneq (,$(wildcard $(ENV_FILE)))
    include $(ENV_FILE)
    export
endif

.PHONY: piplock makemigrations migrate createsuperuser up down

piplock:
	pipenv install
	sudo chown -R $(USER) Pipfile.lock

makemigrations:
	docker compose exec -T backend python manage.py makemigrations
	sudo chown -R $USER:$(id -gn $USER) backend/src/app/migrations/

migrate:
	docker compose exec -T backend python manage.py migrate

createsuperuser:
	docker compose exec backend python manage.py createsuperuser

up:
	docker compose up -d

down:
	docker compose down
