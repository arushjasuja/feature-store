@echo off
REM Quick start script for Feature Store on Windows

echo ===================================
echo Feature Store - Windows Quick Start
echo ===================================
echo.

REM Check if running from project root
if not exist "requirements.txt" (
    echo Error: Please run this script from the project root directory
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Error: Failed to create virtual environment
        echo Make sure Python 3.11+ is installed
        exit /b 1
    )
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing core dependencies...
pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo Warning: pip upgrade failed, continuing...
)

REM Install requirements
echo Installing packages...
pip install --only-binary :all: -r requirements.txt
if errorlevel 1 (
    echo.
    echo Pre-built wheels not available, trying compilation...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Error: Package installation failed
        echo.
        echo You are using Python 3.13 which has limited package support.
        echo.
        echo RECOMMENDED: Use Python 3.11 or 3.12 instead
        echo Download from: https://www.python.org/downloads/
        echo.
        echo Alternative: Install Microsoft C++ Build Tools
        echo https://visualstudio.microsoft.com/visual-cpp-build-tools/
        echo.
        echo See WINDOWS.md for detailed troubleshooting
        pause
        exit /b 1
    )
)

REM Check if .env exists
if not exist ".env" (
    echo Creating .env from template...
    copy .env.example .env
    echo Note: Using default configuration. Edit .env for custom settings.
)

REM Start Docker services
echo.
echo Starting Docker services...
cd deploy
docker-compose up -d
if errorlevel 1 (
    echo.
    echo Error: Docker services failed to start
    echo Make sure Docker Desktop is running
    echo.
    pause
    exit /b 1
)
cd ..

REM Wait for services
echo Waiting for services to be ready (10 seconds)...
ping 127.0.0.1 -n 11 > nul

REM Set PYTHONPATH so scripts can find modules
set PYTHONPATH=%CD%

REM Initialize database
echo.
echo Initializing database...
python scripts\init_db.py
if errorlevel 1 (
    echo Warning: Database initialization had issues
)

REM Seed data
echo.
echo Seeding sample data...
python scripts\seed_data.py --users 1000 --days 30
if errorlevel 1 (
    echo Warning: Data seeding had issues
)

REM Success message
echo.
echo ===================================
echo Setup Complete!
echo ===================================
echo.
echo Starting API server...
echo API will be available at: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo Metrics: http://localhost:8000/metrics
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start API
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
