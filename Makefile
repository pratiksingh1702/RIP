.PHONY: setup test lint index

setup:
	uv sync
	docker-compose up -d

test:
	uv run pytest

lint:
	uv run ruff check .

index:
	uv run repo index $(path)
