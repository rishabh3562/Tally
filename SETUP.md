# Tally - Personal Finance OS - Setup Guide

## Quick Start (15 minutes)

### 1. Supabase Setup

1. Go to your Supabase project: https://app.supabase.com/projects
2. Go to **SQL Editor** and run the schema migration:
   - Copy all SQL from `supabase/migrations/001_initial_schema.sql`
   - Paste into the editor and execute
   - This creates all tables, RLS policies, and seeds categories/merchants

### 2. Backend Setup

```bash
cd backend

# Create .env file (already created with your Supabase URL + keys)
# Verify backend/.env has:
# - SUPABASE_URL=https://cfjqglqfjrohgkrpebqf.supabase.co
# - SUPABASE_KEY=<your service role key>

# Install dependencies
pip install -r requirements.txt

# Run server
python -m uvicorn app.main:app --reload
```

Backend runs on **http://localhost:8000**  
API docs available at **http://localhost:8000/docs**

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Environment is already configured in .env.local with:
# - NEXT_PUBLIC_SUPABASE_URL
# - NEXT_PUBLIC_SUPABASE_ANON_KEY
# - NEXT_PUBLIC_API_URL=http://localhost:8000

# Run dev server
npm run dev
```

Frontend runs on **http://localhost:3000**

### 4. Create Test Account

1. Go to http://localhost:3000
2. On login page, enter any email/password and click "Create Account"
3. You'll be signed up and redirected to dashboard

### 5. Create Test Account in App

1. Go to **Upload** page
2. Click "Create New Account" (if no accounts exist)
3. Name: "My HDFC Account", Type: "Bank", Bank: "HDFC"
4. Save

### 6. Upload Test Data

1. Prepare a CSV file with columns: `Date`, `Debit Amount`, `Description`
   ```csv
   Date,Debit Amount,Description
   05-01-2024,500,SWIGGY
   06-01-2024,1200,AMAZON
   07-01-2024,150,HDFC ATM
   ```
2. Go to **Upload** page
3. Select file, pick your account, pick bank (HDFC), upload
4. Wait for processing to complete
5. Go to **Dashboard** to see transactions

## Architecture

```
Frontend (Next.js 14)
├── auth/login              (Supabase email/password)
├── dashboard               (Charts + key metrics)
├── upload                  (File processing with job polling)
├── transactions            (Paginated list + filters)
├── events                  (User-defined transaction groups)
└── chat                    (SQL-backed AI chat)

Backend (FastAPI)
├── api/
│   ├── accounts           (CRUD)
│   ├── uploads            (async job queue)
│   ├── transactions       (query + patch category)
│   ├── events             (with AI summaries)
│   └── chat               (streaming SSE)
├── services/
│   ├── parser             (PDF/CSV/XLSX)
│   ├── deduplicator       (SHA256 fingerprints)
│   ├── merchant           (normalization)
│   ├── categorizer        (rules → regex → LLM)
│   └── chat_service       (SQL + LLM explanation)
└── pipeline/
    └── ingestion          (end-to-end flow)

Database (Supabase/PostgreSQL)
├── users, accounts
├── merchants, merchant_aliases
├── transactions, transaction_categories
├── categories (system + user-custom)
├── events, event_transactions
├── learning_records (user corrections)
└── processing_jobs (upload tracking)
```

## Key Features

| Feature | Status | Notes |
|---------|--------|-------|
| Bank statement upload | ✅ | PDF/CSV/XLSX parsing |
| Deduplication | ✅ | SHA256 fingerprints |
| Categorization | ✅ | 3-layer (rules/regex/LLM) |
| Merchant normalization | ✅ | Lookup → regex → LLM |
| User corrections | ✅ | Stored in learning_records |
| Dashboard | ✅ | Charts via Recharts |
| Chat | ✅ | SQL-backed, no LLM math |
| Events | ✅ | Group txs + AI summaries |
| Multi-account | ✅ | Full RLS isolation |

## Troubleshooting

### Backend won't start
- Check `.env` has SUPABASE_URL and SUPABASE_KEY
- Verify `pip install -r requirements.txt` completed
- Run: `python -c "import pdfplumber; print('OK')"`

### Login not working
- Check `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` in `.env.local`
- Check browser console for auth errors
- Try signing up (creates new user)

### Upload hangs
- Check backend logs for parsing errors
- Verify CSV format matches bank template
- Check `/api/jobs/{job_id}` endpoint manually

### Categorization not working
- Verify `ENABLE_LLM_CATEGORIZATION=true` in backend `.env`
- Add OpenRouter API key to use LLM layer
- Otherwise uses rule + regex (confidence < 0.7 goes to review queue)

## Next Steps

1. **OpenRouter API Key** (for AI features)
   - Sign up at https://openrouter.ai
   - Get API key
   - Add to `backend/.env`: `OPENROUTER_API_KEY=sk-or-v1-...`
   - Restart backend
   - Chat and AI summaries now work

2. **Connect More Banks**
   - Add bank parsers to `backend/app/services/parser.py`
   - Map columns in `BANK_PARSERS` dict
   - Add test CSV/PDF statements

3. **Production Deployment**
   - Set `DEBUG=false` in backend `.env`
   - Use production Supabase tier
   - Deploy backend to Railway/Render/AWS
   - Deploy frontend to Vercel

## Testing the Full Flow

```bash
# Terminal 1: Start backend
cd backend
python -m uvicorn app.main:app --reload

# Terminal 2: Start frontend
cd frontend
npm run dev

# Terminal 3: Upload test CSV and monitor
# Create test.csv with sample transactions
# Upload via http://localhost:3000/upload
# Monitor job at http://localhost:8000/docs → GET /api/jobs/{job_id}
```

---

**Your Supabase Project:** https://app.supabase.com/projects/cfjqglqfjrohgkrpebqf  
**Built:** 2026-06-27  
**Ready to run:** 2 servers, 1 database, all wired up!
