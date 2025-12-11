@echo off
REM Automated test runner for Feature Store (Windows)

echo ==================================
echo Feature Store - Test Runner
echo ==================================
echo.

REM Check if services are running
echo Checking if services are running...
curl -s http://localhost:8000/health > nul 2>&1
if errorlevel 1 (
    echo Error: API is not accessible at http://localhost:8000
    echo Please start services with: docker-compose up -d
    pause
    exit /b 1
)

echo [OK] API is running
echo.

REM Run automated tests
echo Running automated test suite...
py scripts\test_all.py %*

if errorlevel 1 (
    echo.
    echo ==================================
    echo [FAIL] Some tests failed
    echo ==================================
    echo.
    echo Troubleshooting:
    echo   1. Check logs: docker-compose logs api
    echo   2. Check services: docker-compose ps
    echo   3. Restart: docker-compose restart api
    echo.
    pause
    exit /b 1
)

echo.
echo ==================================
echo [PASS] All tests passed!
echo ==================================
echo.
echo View detailed results: test_results.json
echo View metrics: curl http://localhost:8000/metrics
echo View API docs: http://localhost:8000/docs
echo.

pause
