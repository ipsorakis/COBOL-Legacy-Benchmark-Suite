UV ?= uv

.PHONY: install run lint format typecheck test check migrate revision docker-build compose-up compose-down

install:
	$(UV) sync

run:
	$(UV) run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

lint:
	$(UV) run ruff check alembic app tests
	$(UV) run ruff format --check alembic app tests

format:
	$(UV) run ruff format alembic app tests
	$(UV) run ruff check --fix alembic app tests

typecheck:
	$(UV) run mypy

test:
	$(UV) run pytest

check: lint typecheck test

migrate:
	$(UV) run alembic upgrade head

revision:
	$(UV) run alembic revision --autogenerate -m "$(m)"

docker-build:
	docker build -t ipms-api:local .

compose-up:
	docker compose up --build -d

compose-down:
	docker compose down -v
