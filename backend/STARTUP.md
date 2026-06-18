# Backend Startup Guide

## ✅ Setup Complete

Your virtual environment has been created and dependencies are being installed at:
- **Location**: `D:\rishabh\Github\Tally\backend\venv\`
- **Status**: Ready to use

---

## Quick Start

### Step 1: Activate Virtual Environment

**Windows (PowerShell):**
```powershell
cd backend
.\venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
cd backend
venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
cd backend
source venv/bin/activate
```

### Step 2: Start the Backend Server

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 3: Verify It's Running

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete
```

### Step 4: Access the Backend

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **ReDoc**: http://localhost:8000/redoc

---

## Common Commands

### Check Installed Packages
```bash
# Activate venv first
pip list
```

### Install New Package
```bash
pip install package-name
pip freeze > requirements.txt  # Update requirements file
```

### Run Tests
```bash
pytest tests/
```

### Format Code
```bash
black .
isort .
```

### Type Checking
```bash
mypy .
```

---

## Environment Variables

You need to create a `.env` file in the `backend/` directory:

```bash
cp .env.example .env
```

Then edit `.env` with your values:
```
SUPABASE_URL=your-url
SUPABASE_KEY=your-key
DATABASE_URL=your-db-url
OPENROUTER_API_KEY=your-key
JWT_SECRET_KEY=your-secret
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'fastapi'"
```bash
# Make sure venv is activated
# Windows:
venv\Scripts\activate.bat
# macOS/Linux:
source venv/bin/activate
```

### "Port 8000 already in use"
```bash
# Use a different port
python -m uvicorn app.main:app --reload --port 8001
```

### "No module named 'pytesseract' or 'ocrmypdf'"
These require system dependencies. On Windows, you may need to install them separately or skip them for now:
```bash
pip install -r requirements-minimal.txt
```

### Installation failed with "No space left on device"
Free up disk space and run:
```bash
pip install -r requirements.txt
```

---

## With Celery Worker (Optional)

For async tasks, run in a separate terminal:

```bash
# Make sure venv is activated first
celery -A app.queue.tasks worker --loglevel=info
```

---

## Production Setup

To run for production:

```bash
# Don't use --reload flag
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Or use Gunicorn:
```bash
pip install gunicorn
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

---

## Project Structure

```
backend/
├── app/
│   ├── main.py           # FastAPI app entry point
│   ├── api/              # REST endpoints (to be implemented)
│   ├── core/             # Config and security
│   ├── services/         # Business logic
│   ├── pipeline/         # LangGraph pipeline
│   ├── models/           # Database models
│   └── utils/            # Utilities
├── tests/                # Test files
├── venv/                 # Virtual environment
├── requirements.txt      # Python dependencies
├── .env.example         # Environment template
├── pyproject.toml       # Python project config
└── run.bat              # Quick start script (Windows)
```

---

## Next Steps

1. Create `.env` file with your API keys
2. Set up Supabase database schema
3. Implement API endpoints in `app/api/`
4. Implement business logic in `app/services/`
5. Set up LangGraph pipeline in `app/pipeline/`

---

## Need Help?

Check:
- `DEVELOPMENT.md` - Detailed development guide
- `../GETTING_STARTED.md` - Project setup guide
- FastAPI docs: https://fastapi.tiangolo.com
