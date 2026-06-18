# Personal Finance OS

🏦 **Intelligent Bank Statement Ingestion, Categorization & AI-Powered Insights**

A full-stack application that transforms raw bank statements into structured, searchable, and AI-enriched financial intelligence for Indian tech professionals.

## Features

✅ **Multi-bank statement ingestion** (PDF, CSV, Excel)  
✅ **Automatic transaction categorization** with user learning  
✅ **Duplicate detection** with fingerprinting  
✅ **Merchant normalization** (raw strings → canonical names)  
✅ **Event grouping** (e.g., "Goa Trip 2026")  
✅ **SQL-backed chat interface** for financial queries  
✅ **Multi-account support** for Indians (HDFC, ICICI, SBI, etc.)  
✅ **Supabase backend** with PostgreSQL + pgvector  

## Project Structure

```
Tally/
├── frontend/                   # Next.js 16 frontend (App Router, no src/)
│   ├── app/                    # Pages & layouts
│   ├── components/             # React components (organized by feature)
│   ├── hooks/                  # Custom React hooks
│   ├── lib/                    # API client, Supabase, utilities
│   ├── types/                  # TypeScript interfaces
│   ├── styles/                 # Global styles with Tailwind
│   └── public/                 # Static assets
├── backend/                    # FastAPI backend (Python 3.12)
│   ├── app/
│   │   ├── api/                # REST endpoints
│   │   ├── core/               # Config & security
│   │   ├── services/           # Business logic
│   │   ├── pipeline/           # LangGraph pipeline
│   │   └── utils/              # Helpers
│   └── tests/
├── config/                     # Docker Compose & shared config
├── infrastructure/             # Docker, deployment scripts
├── docs/                       # Architecture, API, database docs
├── FOLDER_STRUCTURE.md         # Backend structure (detailed)
└── FRONTEND_STRUCTURE.md       # Frontend structure (detailed)
```

For detailed folder structure, see:
- [FOLDER_STRUCTURE.md](./FOLDER_STRUCTURE.md) - Backend structure
- [FRONTEND_STRUCTURE.md](./FRONTEND_STRUCTURE.md) - Frontend structure

## Tech Stack

### Frontend
- **Framework**: Next.js 16 (App Router)
- **Runtime**: React 19
- **Styling**: Tailwind CSS v4
- **Database Client**: Supabase JS
- **API Client**: Axios
- **Language**: TypeScript
- **Linting**: ESLint

### Backend
- **Framework**: FastAPI (Python 3.12)
- **Pipeline**: LangGraph (AI agent orchestration)
- **Queue**: Redis + Celery (async jobs)
- **Database**: Supabase (PostgreSQL + pgvector)
- **LLM Gateway**: OpenRouter (Google Gemini, Claude)
- **Parsing**: pdfplumber, pandas, OCRmyPDF

### Infrastructure
- **Containerization**: Docker & Docker Compose
- **Database**: PostgreSQL 15 + pgvector
- **Cache**: Redis 7
- **Monitoring**: Sentry, LangSmith, Grafana
- **Auth**: Supabase Auth + JWT

## Quick Start

### Prerequisites
- Node.js 18+
- Python 3.12+
- Docker & Docker Compose
- Supabase account
- OpenRouter API key

### Option 1: Docker Compose (Recommended)
```bash
# Clone repository
git clone https://github.com/rishabh3562/Tally.git
cd Tally

# Set up environment variables
cp frontend/.env.example frontend/.env.local
cp backend/.env.example backend/.env

# Edit .env files with your actual keys

# Start the stack
cd config
docker-compose up -d
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000/docs
- Redis: localhost:6379

### Option 2: Manual Setup (Recommended for Development)

**Backend Setup:**
```bash
cd backend
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your Supabase & OpenRouter keys

# Start the backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend Setup (in a new terminal):**
```bash
cd frontend

# Install dependencies
npm install

# Copy environment template
cp .env.example .env.local
# Edit .env.local with your Supabase URL & key

# Start the dev server
npm run dev
```

The frontend will be available at **http://localhost:3000**  
The backend API will be available at **http://localhost:8000**

See [DEVELOPMENT.md](./docs/DEVELOPMENT.md) for detailed setup instructions.

## Getting Started

### First Time Setup

1. **Clone and navigate to the project**
   ```bash
   git clone https://github.com/rishabh3562/Tally.git
   cd Tally
   ```

2. **Get API Keys**
   - Create a [Supabase account](https://supabase.com) and project
   - Create an [OpenRouter account](https://openrouter.ai) and get API key
   - Copy your Supabase URL and service key

3. **Set up environment files**
   ```bash
   # Copy backend env template
   cp backend/.env.example backend/.env
   
   # Copy frontend env template
   cp frontend/.env.example frontend/.env.local
   ```

4. **Edit environment files with your keys**
   ```bash
   # Edit backend/.env
   SUPABASE_URL=your-supabase-url
   SUPABASE_KEY=your-supabase-key
   OPENROUTER_API_KEY=your-openrouter-key
   
   # Edit frontend/.env.local
   NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
   NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

5. **Choose your setup method**
   
   **Option A: Manual (Recommended for Development)**
   ```bash
   # Terminal 1: Frontend
   cd frontend && npm install && npm run dev
   
   # Terminal 2: Backend
   cd backend && python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt && python -m uvicorn app.main:app --reload
   ```

   **Option B: Docker (Full Stack)**
   ```bash
   cd config && docker-compose up -d
   ```

6. **Verify everything is working**
   - Frontend: http://localhost:3000
   - Backend API Docs: http://localhost:8000/docs
   - Backend Health: http://localhost:8000/health

### Project Navigation

- **Frontend Code**: `frontend/` (Next.js 16, React 19, TypeScript)
  - See [FRONTEND_STRUCTURE.md](./FRONTEND_STRUCTURE.md)
  - Components in `frontend/components/`
  - Hooks in `frontend/hooks/`
  - Utilities in `frontend/lib/`

- **Backend Code**: `backend/` (FastAPI, Python 3.12)
  - See [FOLDER_STRUCTURE.md](./FOLDER_STRUCTURE.md)
  - API endpoints in `backend/app/api/`
  - Business logic in `backend/app/services/`
  - Processing pipeline in `backend/app/pipeline/`

- **Documentation**: `docs/`
  - [DEVELOPMENT.md](./docs/DEVELOPMENT.md) - Setup & troubleshooting
  - [ARCHITECTURE.md](./docs/ARCHITECTURE.md) - System design *(coming soon)*
  - [DATABASE.md](./docs/DATABASE.md) - Schema & migrations *(coming soon)*
  - [API.md](./docs/API.md) - Endpoint documentation *(coming soon)*

### Next Steps

1. Read the [PRD](./PersonalFinanceOS_PRD_v1.1.pdf) to understand the features
2. Set up Supabase database schema (see [Database Setup](#database-setup))
3. Start building features with the existing hooks and components
4. Check out [Development Workflow](#development) section

## Architecture

The application follows a **pipeline-driven architecture**:

```
Upload → Parse → Dedupe → Normalize → Categorize → Store → Embed
                   (LangGraph DAG with async Redis queue)
```

### Core Flows

**1. Statement Upload & Processing**
- User uploads bank statement (PDF/CSV/Excel)
- FastAPI validates & queues parsing job
- Redis/Celery workers process asynchronously
- LangGraph pipeline executes: parse → dedupe → normalize → categorize
- Results stored in Supabase with RLS protection

**2. Categorization with Learning**
- Layer 1: Hard rules (Uber → Transport)
- Layer 2: Regex patterns (/GROCERY/ → Food)
- Layer 3: LLM fallback (for confidence < 0.7)
- User corrections stored in `learning_records` → reapplied on future imports

**3. Chat / RAG Interface**
- User asks: "How much did I spend on food last month?"
- Backend: classify intent → run SQL query → retrieve context from pgvector
- LLM never performs arithmetic (all sums from SQL)
- Stream response back to UI

## Key Concepts

### Fingerprinting
Every transaction gets a unique fingerprint:
```
SHA256(date + amount + raw_merchant + account_id)
```
Prevents duplicate transactions on re-upload.

### Row-Level Security (RLS)
Supabase enforces user isolation at the database layer:
```sql
USING (auth.uid() = user_id)
```
No cross-user data leakage possible.

### Vector Search (pgvector)
Only high-level summaries are embedded:
- Monthly digests (~200 words)
- Event summaries (AI-generated breakdowns)
- User notes

Chat queries fetch relevant context via cosine similarity before calling LLM.

### Multi-Model Gateway
OpenRouter provides automatic fallback:
1. Google Gemini Flash (fast, cost-efficient for categorization)
2. Anthropic Claude (complex reasoning)
3. Nemotron Ultra (free fallback)

## API Endpoints

```bash
# Upload statement
POST /api/upload-statement

# Get transactions
GET /api/transactions?start=2026-05-01&end=2026-05-31&category_id=...

# Update transaction category
PATCH /api/transactions/{id}/category

# Create event
POST /api/events

# Chat query (Server-Sent Events)
POST /api/chat
```

See [docs/API.md](./docs/API.md) for complete endpoint documentation.

## Development

### Commands

**Frontend:**
```bash
npm run dev       # Start dev server
npm run build     # Build for production
npm run lint      # Lint code
npm run format    # Format with Prettier
npm run type-check # TypeScript check
```

**Backend:**
```bash
python -m uvicorn app.main:app --reload  # Dev server
pytest tests/                             # Run tests
black . && isort .                        # Format
mypy .                                    # Type check
```

### Testing

```bash
# Backend unit tests
cd backend && pytest tests/ -v

# Backend with coverage
pytest tests/ --cov=app --cov-report=html

# Frontend tests
cd frontend && npm test
```

### Code Quality

- **Backend**: Black, isort, flake8, mypy
- **Frontend**: Prettier, ESLint, TypeScript

## Database

### Schema
Key tables:
- `users` - User accounts
- `transactions` - Bank transactions (core data)
- `merchants` - Canonical merchant names
- `merchant_aliases` - Raw string → canonical name mappings
- `categories` - Expense categories (system + user-custom)
- `events` - User-defined transaction groups
- `notes` - Summaries for RAG (embedded into pgvector)

See [docs/DATABASE.md](./docs/DATABASE.md) for full schema.

### Migrations
Use Supabase dashboard SQL editor or migration files.

## Monitoring & Observability

- **Errors**: Sentry (FastAPI exceptions, frontend crashes)
- **LLM Tracing**: LangSmith (debug categorization & chat issues)
- **Metrics**: Prometheus → Grafana (database, API performance)
- **Logs**: Structured logging in both services

## Configuration

All configuration via environment variables:

**Backend**: `backend/.env`  
**Frontend**: `frontend/.env.local`

Critical variables:
- `SUPABASE_URL`, `SUPABASE_KEY` - Database & auth
- `OPENROUTER_API_KEY` - LLM access
- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Cache & queue
- `JWT_SECRET_KEY` - API authentication

See `.env.example` files for all options.

## Cost Estimates

| Service | Cost (100K MAU) | Notes |
|---------|---|---|
| Supabase Pro | ~$100–200/mo | Database, auth, storage, backups |
| Supabase Team | $599/mo | At 50K–500K MAU |
| OpenRouter LLM | ~$300/mo | ~100 chat queries/day |
| Redis/Celery | ~$20/mo | Small VMs on any cloud |
| Sentry | $26/mo | Error tracking |
| **Total** | **~$600–900/mo** | Scales linearly with usage |

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit changes: `git commit -m "Add your feature"`
4. Push to branch: `git push origin feature/your-feature`
5. Open a pull request

## License

MIT License - see LICENSE file for details.

## Support & Documentation

### Getting Started
- 🚀 **[GETTING_STARTED.md](./GETTING_STARTED.md)** - Step-by-step setup guide (START HERE!)
- ✅ [Setup Complete Report](./docs/SETUP_COMPLETE.md) - Verification and checklist
- 📖 [Development Guide](./docs/DEVELOPMENT.md) - Detailed development setup
- 🏗️ [Frontend Structure](./FRONTEND_STRUCTURE.md) - Next.js 16 folder layout
- 🗂️ [Backend Structure](./FOLDER_STRUCTURE.md) - FastAPI folder layout

### Architecture & Design
- 📐 [Architecture Documentation](./docs/ARCHITECTURE.md) *(coming soon)*
- 🗄️ [Database Schema](./docs/DATABASE.md) *(coming soon)*
- 🔌 [API Documentation](./docs/API.md) *(coming soon)*
- 📋 [Product Requirements](./docs/PersonalFinanceOS_PRD_v1.1.pdf) - Full PRD

### Quick Links
- Frontend code: `frontend/` (Next.js 16 + React 19)
- Backend code: `backend/` (FastAPI + Python 3.12)
- Configuration: `config/` (Docker Compose)

---

**Personal Finance OS** — Making financial clarity accessible to Indian professionals.

**New to the project?** Start with [GETTING_STARTED.md](./GETTING_STARTED.md) 👈
