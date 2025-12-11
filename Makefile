.PHONY: help install dev test lint format clean docker-up docker-down init-db seed-data benchmark

help:
	@echo "Available commands:"
	@echo "  make install      - Install production dependencies"
	@echo "  make dev          - Install development dependencies"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linters"
	@echo "  make format       - Format code with black"
	@echo "  make clean        - Remove cache and build files"
	@echo "  make docker-up    - Start all services"
	@echo "  make docker-down  - Stop all services"
	@echo "  make init-db      - Initialize database"
	@echo "  make seed-data    - Seed sample data"
	@echo "  make benchmark    - Run performance benchmark"

install:
	pip install -r requirements.txt

dev:
	pip install -r requirements.txt
	pip install -e .

test:
	pytest tests/ -v --cov=.

lint:
	flake8 api/ store/ streaming/ monitoring/ config/ scripts/ tests/
	mypy api/ store/ config/ --ignore-missing-imports

format:
	black api/ store/ streaming/ monitoring/ config/ scripts/ tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf .pytest_cache htmlcov .mypy_cache

docker-up:
	cd deploy && docker-compose up -d

docker-down:
	cd deploy && docker-compose down

docker-logs:
	cd deploy && docker-compose logs -f

init-db:
	python scripts/init_db.py

seed-data:
	python scripts/seed_data.py --users 1000 --days 30

benchmark:
	python scripts/benchmark.py

run-api:
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

run-api-prod:
	uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4

load-test:
	locust -f tests/load_test.py --host http://localhost:8000
