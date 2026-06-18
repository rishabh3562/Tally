# Personal Finance OS - Folder Structure

```
Tally/
├── frontend/                       # Next.js 14 Frontend Application
│   ├── src/
│   │   ├── app/                    # Next.js App Router
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── (auth)/             # Auth routes
│   │   │   ├── (dashboard)/        # Main dashboard routes
│   │   │   ├── api/                # Client-side API routes (if needed)
│   │   │   └── globals.css
│   │   ├── components/             # React components
│   │   │   ├── auth/
│   │   │   ├── dashboard/
│   │   │   ├── transactions/
│   │   │   ├── events/
│   │   │   ├── chat/
│   │   │   └── common/
│   │   ├── hooks/                  # Custom React hooks
│   │   │   ├── useAuth.ts
│   │   │   ├── useTransactions.ts
│   │   │   └── useChat.ts
│   │   ├── lib/                    # Utility functions & API clients
│   │   │   ├── api.ts              # Axios/fetch client for backend
│   │   │   ├── supabase.ts         # Supabase client
│   │   │   └── utils.ts
│   │   ├── types/                  # TypeScript types/interfaces
│   │   │   ├── index.ts
│   │   │   ├── transactions.ts
│   │   │   ├── events.ts
│   │   │   └── api.ts
│   │   └── styles/                 # Global styles
│   ├── public/                     # Static assets
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.js
│   └── tailwind.config.ts
│
├── backend/                        # FastAPI Backend Application
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app entry point
│   │   ├── api/                    # API routes
│   │   │   ├── __init__.py
│   │   │   ├── auth.py             # /auth endpoints
│   │   │   ├── transactions.py     # /transactions endpoints
│   │   │   ├── events.py           # /events endpoints
│   │   │   ├── chat.py             # /chat endpoints
│   │   │   └── uploads.py          # /upload endpoints
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py           # Environment & settings
│   │   │   ├── security.py         # Auth, JWT, RLS
│   │   │   └── middleware.py
│   │   ├── models/                 # SQLAlchemy models (if used)
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── transaction.py
│   │   │   ├── event.py
│   │   │   └── merchant.py
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   │   ├── __init__.py
│   │   │   ├── transaction.py
│   │   │   ├── event.py
│   │   │   └── chat.py
│   │   ├── services/               # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── transaction_service.py
│   │   │   ├── merchant_service.py
│   │   │   ├── category_service.py
│   │   │   ├── event_service.py
│   │   │   └── chat_service.py
│   │   ├── pipeline/               # LangGraph pipeline logic
│   │   │   ├── __init__.py
│   │   │   ├── graph.py            # LangGraph definition
│   │   │   ├── nodes/
│   │   │   │   ├── parse.py        # PDF/CSV parsing
│   │   │   │   ├── dedupe.py       # Deduplication
│   │   │   │   ├── normalize.py    # Merchant normalization
│   │   │   │   ├── categorize.py   # Categorization
│   │   │   │   └── embed.py        # Embedding generation
│   │   │   └── state.py            # Pipeline state management
│   │   ├── llm/                    # LLM integration
│   │   │   ├── __init__.py
│   │   │   ├── openrouter.py       # OpenRouter gateway
│   │   │   ├── prompts.py          # LLM prompts
│   │   │   └── models.py           # Model configs
│   │   ├── queue/                  # Celery/Redis tasks
│   │   │   ├── __init__.py
│   │   │   ├── tasks.py            # Async tasks
│   │   │   └── config.py
│   │   └── utils/                  # Helper utilities
│   │       ├── __init__.py
│   │       ├── parsers.py          # Bank statement parsers
│   │       ├── fingerprint.py      # Transaction fingerprinting
│   │       └── validators.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── unit/
│   │   ├── integration/
│   │   └── fixtures/
│   ├── requirements.txt            # Python dependencies
│   ├── pyproject.toml              # Modern Python project config
│   ├── .env.example
│   └── README.md
│
├── config/                         # Shared configuration
│   ├── .env.example                # Example environment variables
│   ├── docker-compose.yml          # Local development stack
│   └── constants.ts/py             # Shared constants
│
├── infrastructure/
│   ├── .docker/
│   │   ├── Dockerfile.frontend
│   │   ├── Dockerfile.backend
│   │   └── docker-compose.prod.yml
│   ├── k8s/                        # Kubernetes manifests (future)
│   │   └── README.md
│   └── scripts/
│       ├── setup.sh
│       └── seed-db.py
│
├── docs/                           # Documentation
│   ├── API.md                      # API documentation
│   ├── ARCHITECTURE.md             # System architecture
│   ├── DEVELOPMENT.md              # Setup & development guide
│   ├── DATABASE.md                 # Schema & migrations
│   └── DEPLOYMENT.md               # Deployment guide
│
├── .gitignore
├── .github/                        # GitHub workflows (future)
│   └── workflows/
├── README.md                       # Project overview
├── FOLDER_STRUCTURE.md             # This file
└── PersonalFinanceOS_PRD_v1.1.pdf  # PRD reference
```

## Key Directory Purposes

### **Frontend** (`/frontend`)
- Next.js 14 with App Router
- Contains all UI components, pages, and client-side logic
- Handles file uploads, authentication, transaction views, event creation, chat UI
- Uses Tailwind CSS for styling
- Communicates with backend via REST API

### **Backend** (`/backend`)
- FastAPI application (Python 3.12)
- Handles all API endpoints: `/upload`, `/transactions`, `/events`, `/chat`
- Contains business logic, database interactions, LLM integrations
- **Pipeline** folder: LangGraph-based processing pipeline
  - Parse → Dedupe → Normalize → Categorize → Store → Embed
- **Services** folder: High-level business operations
- **Queue** folder: Redis/Celery for async processing

### **Config** (`/config`)
- Shared configuration for both frontend and backend
- Environment variable templates
- Docker Compose for local development

### **Infrastructure** (`/infrastructure`)
- Docker files for containerization
- Kubernetes configs for deployment (future)
- Setup and deployment scripts

### **Docs** (`/docs`)
- API documentation
- Architecture diagrams and explanations
- Setup and development guides
- Database schema documentation

## Development Workflow

1. **Frontend only changes**: Work in `/frontend` → `npm run dev`
2. **Backend only changes**: Work in `/backend` → `python -m uvicorn app.main:app --reload`
3. **Both changes**: Run `docker-compose up` in `/config` for full stack
4. **Database changes**: Update Supabase schema, document in `/docs/DATABASE.md`

## Technology Stack by Directory

| Directory | Technology | Purpose |
|-----------|-----------|---------|
| frontend | Next.js 14, React, Tailwind, TanStack Query | UI & client logic |
| backend | FastAPI, Python 3.12, LangGraph, SQLAlchemy | API & processing |
| queue | Redis, Celery/Dramatiq | Async job processing |
| llm | OpenRouter, LangChain | LLM integrations |
| database | Supabase (PostgreSQL), pgvector | Data storage & RAG |
