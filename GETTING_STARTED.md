# Getting Started with Personal Finance OS

This guide will help you set up the project and start developing locally.

## ✅ Verification Checklist

Before starting, ensure you have:

- [ ] Node.js 18+ installed (`node --version`)
- [ ] npm installed (`npm --version`)
- [ ] Python 3.12+ installed (`python --version`)
- [ ] Git installed
- [ ] Supabase account created
- [ ] OpenRouter account created

## Step 1: Clone & Setup

```bash
# Clone the repository
git clone https://github.com/rishabh3562/Tally.git
cd Tally

# Verify folder structure
ls -la
# You should see: frontend/, backend/, config/, docs/, infrastructure/, etc.
```

## Step 2: Get API Keys

### Supabase
1. Go to https://supabase.com and sign up
2. Create a new project
3. Go to Settings → API
4. Copy your **Project URL** and **Service Role Key** (for backend)
5. Copy your **Project URL** and **Anon Key** (for frontend)

### OpenRouter
1. Go to https://openrouter.ai and sign up
2. Go to Dashboard → API Keys
3. Create a new API key
4. Copy the key

## Step 3: Set Up Environment Variables

### Frontend Setup
```bash
cd frontend

# Copy environment template
cp .env.example .env.local

# Edit .env.local with your keys
# Required variables:
# NEXT_PUBLIC_SUPABASE_URL=<your-supabase-url>
# NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-supabase-anon-key>
# NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Backend Setup
```bash
cd ../backend

# Copy environment template
cp .env.example .env

# Edit .env with your keys
# Required variables:
# SUPABASE_URL=<your-supabase-url>
# SUPABASE_KEY=<your-supabase-service-key>
# DATABASE_URL=postgresql://user:password@localhost:5432/tally (or use Supabase)
# OPENROUTER_API_KEY=<your-openrouter-key>
# JWT_SECRET_KEY=<generate-a-random-secret>
```

Generate JWT_SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Step 4: Install Dependencies

### Frontend
```bash
cd frontend
npm install
```

Expected output:
```
added 378 packages in 8s
```

### Backend
```bash
cd ../backend

# Create virtual environment
python -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

Expected output:
```
Successfully installed <packages>
```

## Step 5: Verify Everything Works

### Frontend Verification
```bash
cd frontend

# Check that build works
npm run build

# Should see:
# ✓ Compiled successfully
# ✓ Generating static pages
# ✓ Finalizing page optimization
```

### Backend Verification
```bash
cd ../backend

# Activate venv (if not already)
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Check imports
python -c "from app.main import app; print('✅ Backend imports OK')"

# Should output: ✅ Backend imports OK
```

## Step 6: Run Locally

You need at least 2 terminals (3 if you want Celery).

**Terminal 1: Frontend**
```bash
cd frontend
npm run dev
```

Wait for:
```
▲ Next.js 16.2.9 (Local)
 > Local:        http://localhost:3000
 > Environments: .env.local

✓ Ready in 2.1s
```

**Terminal 2: Backend**
```bash
cd backend
source venv/bin/activate  # macOS/Linux or venv\Scripts\activate for Windows
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Wait for:
```
Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

## Step 7: Access the Application

- **Frontend**: http://localhost:3000
- **Backend API Docs**: http://localhost:8000/docs
- **Backend Health Check**: http://localhost:8000/health

## Verify Connectivity

Test the backend health endpoint:
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
```

## Common Issues

### "ModuleNotFoundError: No module named 'fastapi'"
**Solution**: Make sure you activated the virtual environment
```bash
cd backend
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows
```

### "Port 3000/8000 already in use"
**Solution**: Kill the process using that port
```bash
# On macOS/Linux:
lsof -i :3000
kill -9 <PID>

# On Windows:
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# Or use a different port:
npm run dev -- -p 3001  # Frontend
python -m uvicorn app.main:app --reload --port 8001  # Backend
```

### "Cannot find module 'axios'"
**Solution**: Install frontend dependencies
```bash
cd frontend
npm install
```

### Supabase connection error
**Solution**: 
1. Check that SUPABASE_URL and SUPABASE_KEY are correct in `.env`
2. Verify your Supabase project is active
3. Check network connectivity

## Next Steps

1. Read the [Product Requirements Document](./PersonalFinanceOS_PRD_v1.1.pdf)
2. Check out [FRONTEND_STRUCTURE.md](./FRONTEND_STRUCTURE.md) to understand the frontend layout
3. Check out [FOLDER_STRUCTURE.md](./FOLDER_STRUCTURE.md) to understand the backend layout
4. Read [DEVELOPMENT.md](./docs/DEVELOPMENT.md) for detailed development guide
5. Start building features!

## Project Files to Explore

- **Frontend Components**: `frontend/components/`
- **Frontend Hooks**: `frontend/hooks/`
- **Backend API**: `backend/app/api/`
- **Backend Services**: `backend/app/services/`
- **Types/Interfaces**: `frontend/types/` and in backend models
- **Environment Templates**: `frontend/.env.example` and `backend/.env.example`

## Useful Commands

### Frontend
```bash
npm run dev        # Start dev server
npm run build      # Build for production
npm run lint       # Run ESLint
npm run type-check # TypeScript check
npm start          # Start production server
```

### Backend
```bash
python -m uvicorn app.main:app --reload  # Start with auto-reload
pytest tests/                             # Run tests
black .                                   # Format code
flake8 .                                  # Lint code
mypy .                                    # Type checking
```

## Getting Help

- Check [DEVELOPMENT.md](./docs/DEVELOPMENT.md) for detailed setup
- Check [FAQ](#faq) section below
- Review the [PRD](./PersonalFinanceOS_PRD_v1.1.pdf) for feature details
- Open an issue on GitHub

## FAQ

**Q: Do I need Docker to run this locally?**
A: No, you can run frontend and backend directly. Docker is optional for simplified setup.

**Q: Can I work on just frontend without the backend running?**
A: Yes, but API calls will fail. The frontend is still good for component development.

**Q: Where do I add new features?**
A: Frontend features go in `frontend/components/` and `frontend/hooks/`. Backend endpoints go in `backend/app/api/`.

**Q: How do I connect to Supabase?**
A: The frontend uses Supabase JS client (initialized in `frontend/lib/supabase.ts`). The backend uses the service key.

**Q: What should I do if I encounter bugs?**
A: Check the logs in the terminal where you started the server. Use `npm run lint` for frontend and `python -m pytest` for backend tests.

## That's it! 🎉

You're now set up and ready to develop. Happy coding!
