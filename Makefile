ENV_FILE := .env
ifneq (,$(wildcard $(ENV_FILE)))
    include $(ENV_FILE)
    export
endif

.PHONY: piplock makemigrations migrate createsuperuser up down \
	lint lint-fix format format-check

piplock:
	pipenv install
	sudo chown -R $(USER) Pipfile.lock

lint:
	$(RUN) ruff check ./backend

lint-fix:
	$(RUN) ruff check ./backend --fix

format:
	$(RUN) ruff format ./backend

format-check:
	$(RUN) ruff format --check ./backend

makemigrations:
	docker compose exec --user "$(id -u):$(id -g)" backend python manage.py makemigrations

migrate:
	docker compose exec -T backend python manage.py migrate

createsuperuser:
	docker compose exec backend python manage.py createsuperuser

up:
	docker compose up -d

down:
	docker compose down
