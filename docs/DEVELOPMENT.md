# Development Setup Guide

This guide explains how to set up the Personal Finance OS project locally for development.

## Project Structure

- **`/frontend`** - Next.js 16 frontend application (React 19, TypeScript, Tailwind CSS v4)
  - No `src/` folder (flat structure)
  - Components, hooks, lib, types at root level
  - See [FRONTEND_STRUCTURE.md](../FRONTEND_STRUCTURE.md) for details

- **`/backend`** - FastAPI backend application (Python 3.12)
  - See [FOLDER_STRUCTURE.md](../FOLDER_STRUCTURE.md) for details

- **`/config`** - Shared configuration & Docker Compose
- **`/infrastructure`** - Docker files and deployment scripts
- **`/docs`** - Documentation files

## Prerequisites

### Global Requirements
- Node.js 18+ (for frontend)
- Python 3.12+ (for backend)
- Docker & Docker Compose (recommended for local development)
- Git

### Accounts & API Keys
- Supabase account with PostgreSQL database
- OpenRouter API key (for LLM access)
- (Optional) Sentry account for error tracking
- (Optional) LangSmith account for LLM debugging

## Quick Start (Docker Compose)

### 1. Clone the Repository
```bash
git clone https://github.com/rishabh3562/Tally.git
cd Tally
```

### 2. Set Up Environment Variables
```bash
# Backend
cp backend/.env.example backend/.env
# Edit backend/.env with your actual keys

# Frontend
cp frontend/.env.example frontend/.env.local
# Edit frontend/.env.local with your actual keys
```

### 3. Start the Development Stack
```bash
cd config
docker-compose up -d
```

This will start:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### 4. Verify Everything Works
- Frontend: `curl http://localhost:3000`
- Backend: `curl http://localhost:8000/docs` (Swagger UI)
- Health check: `curl http://localhost:8000/health`

---

## Manual Setup (Without Docker)

### Backend Setup

#### 1. Create Virtual Environment
```bash
cd backend
python -m venv venv

# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

#### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 3. Set Up Environment Variables
```bash
cp .env.example .env
# Edit .env with your configuration
```

#### 4. Initialize Database
```bash
# Run Supabase migrations (if using SQL files)
# Or create tables via Supabase dashboard
python scripts/seed-db.py
```

#### 5. Start the Backend
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API will be available at: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

#### 6. (Optional) Start Celery Worker
```bash
celery -A app.queue.tasks worker --loglevel=info
```

### Frontend Setup

The frontend uses **Next.js 16** with **App Router** and **NO `src/` folder** structure.

#### 1. Install Dependencies
```bash
cd frontend
npm install
```

#### 2. Set Up Environment Variables
```bash
cp .env.example .env.local
# Edit .env.local with your configuration
```

**Required Variables:**
```
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

#### 3. Start the Development Server
```bash
npm run dev
```

Frontend will be available at: **http://localhost:3000**

#### 4. Frontend Structure
```
frontend/
├── app/              # Next.js pages & layouts (App Router)
├── components/       # React components (organized by feature)
├── hooks/            # Custom React hooks
├── lib/              # API client, Supabase, utilities
├── types/            # TypeScript interfaces
├── styles/           # Global styles
├── utils/            # Constants & config
└── public/           # Static assets
```

For detailed frontend structure, see [FRONTEND_STRUCTURE.md](../FRONTEND_STRUCTURE.md)

---

## Development Workflow

### Working on Frontend Only
```bash
cd frontend
npm run dev
```
Frontend available at: **http://localhost:3000**

### Working on Backend Only
```bash
cd backend

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows

# Start the server
python -m uvicorn app.main:app --reload
```
Backend available at: **http://localhost:8000**
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

### Working on Both (Recommended for Full Stack Development)

**Terminal 1: Frontend**
```bash
cd frontend
npm run dev
```

**Terminal 2: Backend**
```bash
cd backend
source venv/bin/activate  # macOS/Linux or venv\Scripts\activate for Windows
python -m uvicorn app.main:app --reload
```

**Terminal 3: Celery Worker (for async tasks)**
```bash
cd backend
source venv/bin/activate
celery -A app.queue.tasks worker --loglevel=info
```

**Terminal 4: Redis (if not using Docker)**
```bash
redis-server
```

This gives you:
- Frontend with hot reload: http://localhost:3000
- Backend with auto-reload: http://localhost:8000/docs
- Async task queue: Celery + Redis

---

## Frontend Development Tips

### Directory Structure (No `src/` folder)
All folders are at the root level of `frontend/`:

- **`app/`** - Next.js App Router (pages and layouts)
- **`components/`** - React components organized by feature
- **`hooks/`** - Custom hooks (useAuth, useTransactions, useChat)
- **`lib/`** - Utilities (API client, Supabase, helpers)
- **`types/`** - TypeScript interfaces
- **`styles/`** - Global CSS with Tailwind
- **`utils/`** - Constants and configuration
- **`public/`** - Static assets

### Adding a New Feature

1. **Create a page in `app/`**
   ```bash
   # Example: app/myfeature/page.tsx
   ```

2. **Create components in `components/myfeature/`**
   ```typescript
   // components/myfeature/MyFeatureMain.tsx
   export default function MyFeatureMain() {
     return <div>Feature content</div>;
   }
   ```

3. **Create a custom hook if needed**
   ```typescript
   // hooks/useMyFeature.ts
   export const useMyFeature = () => {
     // Logic here
   };
   // Don't forget to export in hooks/index.ts
   ```

4. **Use in your component**
   ```typescript
   import { useMyFeature } from '../hooks';
   import MyFeatureMain from '../components/myfeature/MyFeatureMain';
   ```

### Component Best Practices

- **Organized by feature**: `components/transactions/`, `components/events/`, not `components/buttons/`
- **Centralized exports**: Use `index.ts` files for cleaner imports
- **TypeScript everywhere**: Use proper types for props and state
- **Tailwind CSS**: Use Tailwind classes for styling

### Testing Frontend

```bash
npm run lint      # Run ESLint
npm run type-check # TypeScript type checking
npm run build     # Production build
npm start         # Production server
```

### Tailwind CSS

Already configured with Tailwind CSS v4. Use utility classes for styling:

```tsx
<div className="flex gap-4 p-4 bg-gray-100 rounded-lg">
  <button className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
    Click me
  </button>
</div>
```

CSS variables defined in `styles/globals.css` for theming:
```css
:root {
  --primary: #0066cc;
  --text-primary: #1f2937;
  /* ... more variables */
}
```

---

## Database Setup

### Initialize Supabase Schema

1. **Create Supabase Project**
   - Go to https://supabase.com and create a new project
   - Copy your project URL and API key

2. **Run SQL Migrations**
   - Go to Supabase Dashboard → SQL Editor
   - Copy the SQL from `docs/DATABASE.md` or use migration files
   - Execute the schema setup

3. **Enable Extensions**
   ```sql
   CREATE EXTENSION IF NOT EXISTS pgvector;
   CREATE EXTENSION IF NOT EXISTS uuid-ossp;
   ```

4. **Set Up RLS Policies**
   - Supabase will help with Row-Level Security
   - Reference: `docs/DATABASE.md`

---

## Testing

### Backend Tests
```bash
cd backend
pytest tests/ -v
# Or with coverage:
pytest tests/ --cov=app --cov-report=html
```

### Frontend Tests
```bash
cd frontend
npm run test
```

---

## Code Quality

### Backend
```bash
cd backend

# Format code
black .

# Sort imports
isort .

# Linting
flake8 .

# Type checking
mypy .
```

### Frontend
```bash
cd frontend

# Format code
npm run format

# Lint
npm run lint

# Type check
npm run type-check
```

---

## Troubleshooting

### Backend Issues

**Port 8000 already in use:**
```bash
# Find and kill the process
lsof -i :8000
kill -9 <PID>

# Or use a different port
python -m uvicorn app.main:app --reload --port 8001
```

**Database connection error:**
- Verify `DATABASE_URL` in `.env` is correct
- Ensure Supabase database is running
- Check firewall/network access

**Redis connection error:**
- Ensure Redis is running: `redis-cli ping`
- Check `REDIS_URL` in `.env`

### Frontend Issues

**Port 3000 already in use:**
```bash
npm run dev -- -p 3001
```

**Module not found errors:**
```bash
cd frontend
rm -rf node_modules .next
npm install
npm run dev
```

### Docker Issues

**Containers not starting:**
```bash
docker-compose logs -f
docker-compose restart
```

**Volume permission errors:**
```bash
docker-compose down
docker system prune -a
docker-compose up -d
```

---

## Environment Variables Reference

See `.env.example` files in both frontend and backend directories for all available configuration options.

### Critical Variables
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_KEY` - Supabase service key
- `OPENROUTER_API_KEY` - LLM gateway API key
- `NEXT_PUBLIC_SUPABASE_URL` - Frontend Supabase URL
- `NEXT_PUBLIC_API_URL` - Backend API URL (frontend perspective)

---

## Useful Commands

```bash
# Check backend health
curl http://localhost:8000/health

# View API docs
open http://localhost:8000/docs

# Clear Redis cache
redis-cli FLUSHALL

# View Celery tasks
celery -A app.queue.tasks events

# Tail logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

---

## Next Steps

1. Read `ARCHITECTURE.md` for system design overview
2. Check `API.md` for available endpoints
3. See `DATABASE.md` for schema details
4. Review the PRD: `PersonalFinanceOS_PRD_v1.1.pdf`

---

## Getting Help

- Check existing GitHub issues
- Review logs: `docker-compose logs <service>`
- Check `.env` variables are set correctly
- Consult the PRD for feature specifications
