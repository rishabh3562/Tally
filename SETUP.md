# Personal Finance OS - Setup Guide

## Prerequisites

- Node.js 18+ (for frontend)
- Python 3.12+ (for backend)
- Supabase account and project
- OpenRouter API key for LLM access

## Environment Setup

### 1. Backend Configuration

Create `.env` file in `backend/` directory:

```bash
# Environment
ENVIRONMENT=development
DEBUG=true

# Supabase Configuration (Dashboard -> Project Settings -> API Keys)
SUPABASE_URL=https://your-project.supabase.co
# Server-side SECRET key. New projects: sb_secret_...  (NOT the publishable key)
# Legacy projects only: the service_role JWT (eyJ...).
SUPABASE_KEY=sb_secret_xxxxxxxxxxxxxxxxxxxxxxxx
# LEGACY ONLY — omit this if your project uses asymmetric signing keys (ES256/RS256).
# Migrated projects verify user tokens via the public JWKS endpoint, no secret needed.
# SUPABASE_JWT_SECRET=

# API Configuration
API_PORT=8000
API_HOST=0.0.0.0
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# OpenRouter / LLM Configuration
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_API_URL=https://openrouter.ai/api/v1

# LLM Models
PRIMARY_LLM_MODEL=google/gemini-2.0-flash-exp
SECONDARY_LLM_MODEL=anthropic/claude-3-5-sonnet
FALLBACK_LLM_MODEL=openrouter/auto

# File Upload Configuration
MAX_FILE_SIZE_MB=50
UPLOAD_TIMEOUT_SECONDS=300
ALLOWED_FILE_TYPES=pdf,csv,xlsx

# Feature Flags
ENABLE_OCR=false
ENABLE_LLM_CATEGORIZATION=true
ENABLE_EVENT_SUMMARIZATION=true

# Monitoring
SENTRY_DSN=
SENTRY_ENVIRONMENT=development
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=Personal Finance OS

# Logging
LOG_LEVEL=INFO
```

### 2. Frontend Configuration

Create `.env.local` file in `frontend/` directory:

```bash
# Supabase Configuration (from Supabase dashboard)
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key

# Backend API
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_TIMEOUT=30000
```

## Database Setup

### 1. Create Tables in Supabase

Run the SQL script in `backend/database_schema.sql` in the Supabase SQL Editor.

### 2. Seed Default Data

After creating tables, run the seed script:

```bash
cd backend
pip install python-dotenv supabase
python -m scripts.seed_data
```

## Running the Application

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m app.main
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## First Time Usage

1. Create account at http://localhost:3000/auth/login
2. Create a bank account in the Accounts section
3. Upload a bank statement (PDF, CSV, or Excel)
4. View and correct categorized transactions
5. Create events for trips or spending groups
6. Chat with your data to get spending insights
