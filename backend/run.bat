@echo off
setlocal enabledelayedexpansion

echo.
echo ========================================
echo  Personal Finance OS - Backend Server
echo ========================================
echo.

REM Check if venv exists
if not exist venv (
    echo ERROR: Virtual environment not found at venv/
    echo Please run: python -m venv venv
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if FastAPI is installed
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo ERROR: FastAPI not installed
    echo Please run: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Start the backend server
echo.
echo Starting backend server on http://localhost:8000
echo Press CTRL+C to stop
echo.
echo API Documentation: http://localhost:8000/docs
echo Health Check: http://localhost:8000/health
echo.

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
