# Project Files Guide

## Core Application (24 Python files)

### API Layer (`api/`)
- `main.py` - FastAPI app, lifespan management, middleware, health endpoints
- `routes.py` - API endpoints (online, batch, register, list, cache)
- `models.py` - Pydantic schemas with validation
- `auth.py` - API key authentication

### Storage (`store/`)
- `postgres.py` - PostgreSQL + TimescaleDB client
- `redis_cache.py` - Redis caching with msgpack serialization

### Streaming (`streaming/`)
- `spark_processor.py` - Kafka consumer with Spark processing

### Monitoring (`monitoring/`)
- `metrics.py` - Prometheus metrics definitions
- `logger.py` - Structured JSON logging

### Configuration (`config/`)
- `settings.py` - Application settings (env vars)
- `schemas/features.yaml` - Sample feature definitions

### Tests (`tests/`)
- `test_api.py` - API unit tests
- `test_store.py` - Storage layer tests
- `load_test.py` - Locust load testing

### Scripts (`scripts/`)
- `init_db.py` - Initialize database schema
- `seed_data.py` - Generate sample data
- `benchmark.py` - Performance benchmarking
- `test_all.py` - Comprehensive automated test suite

## Deployment (`deploy/`)

- `Dockerfile` - Container image definition
- `docker-compose.yml` - Local dev stack (PostgreSQL, Redis, Kafka, API, Prometheus, Grafana)
- `init.sql` - Database schema (TimescaleDB hypertable, indexes)
- `prometheus.yml` - Prometheus scrape config
- `k8s/` - Kubernetes manifests (deployment, service, configmap)

## Documentation (7 files)

### Essential Docs
- **README.md** - Main documentation (features, quick start, API usage, monitoring)
- **QUICKSTART.md** - 5-minute setup guide
- **ARCHITECTURE.md** - System design, data flow, technology choices
- **PROJECT_FILES.md** - Project structure and file guide

### Setup Guides
- **WINDOWS.md** - Windows-specific setup (Python version, troubleshooting)
- **TROUBLESHOOTING.md** - Common issues and solutions

### Deployment
- **DEPLOYMENT.md** - General deployment guide (local, Docker, Kubernetes)

## Configuration Files

### Requirements
- **requirements.txt** - Main dependencies

### Project Config
- **setup.py** - Package installation config
- **pytest.ini** - Test configuration
- **Makefile** - Common task shortcuts
- **LICENSE** - MIT license

## Scripts

### Quick Start 
- **start.bat** - Windows quick start (starts services, initializes DB, seeds data)

### Testing
- **run-tests.bat** - Windows test runner

## What Each Doc Is For

| File | Purpose | When to Use |
|------|---------|-------------|
| README.md | Comprehensive docs | Understanding full project |
| QUICKSTART.md | 5-minute setup | First-time setup |
| ARCHITECTURE.md | System design | Understanding how it works |
| PROJECT_FILES.md | File structure guide | Understanding project organization |
| WINDOWS.md | Windows setup | Setting up on Windows |
| TROUBLESHOOTING.md | Fix issues | When something breaks |
| DEPLOYMENT.md | General deployment | Production deployment |