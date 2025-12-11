# Windows Setup Guide

## Prerequisites

**IMPORTANT:** Use Python 3.11 or 3.12 (not 3.13) - many packages don't have pre-built wheels for 3.13 yet.

1. **Python 3.11 or 3.12** - Download from [python.org](https://www.python.org/downloads/)
2. **Docker Desktop** - Download from [docker.com](https://www.docker.com/products/docker-desktop)
3. **Git** - Download from [git-scm.com](https://git-scm.com/)

## If You Have Python 3.13

Install packages without version restrictions to get latest compatible builds:

```powershell
pip install fastapi uvicorn[standard] pydantic pydantic-settings asyncpg redis msgpack prometheus-client python-json-logger httpx pytest pytest-asyncio
```

Or install what works, skip what doesn't:
```powershell
# Install packages that have wheels for 3.13
pip install fastapi uvicorn[standard] httpx pytest pytest-asyncio prometheus-client python-json-logger

# Try these (may need compilation)
pip install --only-binary :all: pydantic pydantic-settings asyncpg redis msgpack
```

## Quick Start (Windows)

### Option 1: Using PowerShell

```powershell
# 1. Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install core dependencies first
pip install --upgrade pip setuptools wheel
pip install fastapi uvicorn[standard] pydantic pydantic-settings asyncpg redis msgpack prometheus-client python-json-logger httpx

# 3. Install testing tools
pip install pytest pytest-asyncio pytest-cov

# 4. Start Docker services
cd deploy
docker-compose up -d
cd ..

# 5. Initialize database
python scripts/init_db.py

# 6. Seed data
python scripts/seed_data.py --users 1000 --days 30

# 7. Start API
uvicorn api.main:app --reload
```

### Option 2: Using CMD

```cmd
REM 1. Create virtual environment
python -m venv venv
venv\Scripts\activate.bat

REM 2. Install core dependencies
pip install --upgrade pip setuptools wheel
pip install fastapi uvicorn[standard] pydantic pydantic-settings asyncpg redis msgpack prometheus-client python-json-logger httpx pytest pytest-asyncio

REM 3. Start Docker services
cd deploy
docker-compose up -d
cd ..

REM 4. Initialize and seed
python scripts\init_db.py
python scripts\seed_data.py --users 1000 --days 30

REM 5. Start API
python -m uvicorn api.main:app --reload
```

## Common Windows Issues

### Issue 1: Package Installation Failures

**Problem:** Packages requiring C++ compilation fail (psycopg, hiredis, etc.)

**Solution:** Install pre-built wheels only:
```powershell
pip install --only-binary :all: -r requirements.txt
```

Or skip problematic packages:
```powershell
# Install without optional C extensions
pip install redis  # Without [hiredis]
pip install psycopg  # Without [binary]
```

### Issue 2: Docker Not Running

**Problem:** `docker-compose` command fails

**Solution:**
1. Start Docker Desktop
2. Wait for Docker to fully start (check system tray)
3. Test: `docker ps`

### Issue 3: Port Already in Use

**Problem:** Port 8000, 5432, 6379, or 9092 already in use

**Solution:**
```powershell
# Find process using port
netstat -ano | findstr :8000

# Kill process (replace PID)
taskkill /PID <PID> /F

# Or change ports in .env
```

### Issue 4: Permission Errors

**Problem:** Cannot write to directories

**Solution:**
```powershell
# Run PowerShell as Administrator
# Or change directory permissions
```

### Issue 5: Python Not Found

**Problem:** `python` command not recognized

**Solution:**
1. Reinstall Python with "Add to PATH" checked
2. Or use: `py -3.11` instead of `python`

## Minimal Installation (No Spark/Kafka)

For development without stream processing:

```powershell
# Install only API and storage dependencies
pip install fastapi uvicorn[standard] pydantic pydantic-settings asyncpg redis msgpack prometheus-client python-json-logger httpx pytest pytest-asyncio

# Use minimal docker-compose
cd deploy
docker-compose up -d postgres redis prometheus
cd ..

# Skip Kafka/Spark, just use API + storage
```

## Testing on Windows

```powershell
# Unit tests
pytest tests\ -v

# Load test (install locust separately if needed)
pip install locust
locust -f tests\load_test.py --host http://localhost:8000

# Benchmark
python scripts\benchmark.py
```

## API Access

Once running:
- API: http://localhost:8000
- Swagger Docs: http://localhost:8000/docs
- Metrics: http://localhost:8000/metrics
- Prometheus: http://localhost:9090

## Troubleshooting

### Check Service Status
```powershell
docker ps
curl http://localhost:8000/health
```

### View Logs
```powershell
docker-compose -f deploy\docker-compose.yml logs -f api
```

### Restart Everything
```powershell
cd deploy
docker-compose down
docker-compose up -d
cd ..
python scripts\init_db.py
```

## WSL2 Alternative (Recommended)

For better Linux compatibility:

```bash
# Install WSL2
wsl --install

# Inside WSL2
git clone <repo>
cd feature-store
./start.sh
```

This avoids Windows-specific issues with packages requiring compilation.
