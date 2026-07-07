# Environment Setup Guide

## 🚀 Quick Start

### Backend Setup

```bash
cd backend

# 1. Copy template to actual config
cp .env.example .env

# 2. Edit .env and fill in your credentials
# - Get SUPABASE_URL and SUPABASE_KEY from Supabase dashboard
# - Get OPENROUTER_API_KEY from https://openrouter.ai/keys
# - Set JWT_SECRET_KEY to a random string

# 3. Start backend
python -m app.main
```

### Frontend Setup

```bash
cd frontend

# 1. Copy template to actual config
cp .env.local.example .env.local

# 2. Edit .env.local and fill in your credentials
# - Get NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY from Supabase

# 3. Start frontend
npm run dev
```

## ⚙️ Configuration Details

### Backend (.env)

**Required Environment Variables:**

| Variable | Description | Where to Get |
|----------|-------------|--------------|
| `SUPABASE_URL` | Your Supabase project URL | Supabase Dashboard → Settings → API |
| `SUPABASE_KEY` | Service role key (with full access) | Supabase Dashboard → Settings → API |
| `SUPABASE_JWT_SECRET` | JWT secret for token validation | Supabase Dashboard → Settings → Auth |
| `OPENROUTER_API_KEY` | OpenRouter API key for LLM access | https://openrouter.ai/keys |

**Optional but Recommended:**

```env
# These have sensible defaults
API_PORT=8000                          # Port for backend
CORS_ORIGINS=http://localhost:3000,... # Frontend URL for CORS
JWT_SECRET_KEY=change-this-in-prod     # Random secret key
```

### Frontend (.env.local)

**Required Environment Variables:**

| Variable | Description | Where to Get |
|----------|-------------|--------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Your Supabase project URL | Supabase Dashboard → Settings → API |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Anon key (for client-side) | Supabase Dashboard → Settings → API |

**Optional:**

```env
# Defaults to http://localhost:8000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 🔐 Security Notes

### What to Keep Secret

**Never commit these to git:**
- `.env` file (contains SUPABASE_KEY, JWT secrets, API keys)
- `.env.local` file (contains SUPABASE_ANON_KEY)

**Why?** These files are in `.gitignore` to prevent accidental commits

### Production Setup

For production, use:
- Environment variables from your hosting platform (Vercel, Railway, Heroku, etc.)
- Never hardcode secrets
- Rotate keys regularly
- Use separate credentials for dev/staging/production

## 🆘 Troubleshooting

### Error: "ValidationError: Extra inputs are not permitted"

**Cause:** Environment variable name typo (e.g., `OPENROUTER_API_KEYS` plural instead of singular)

**Solution:**
1. Check `backend/.env.example` for exact field names
2. Copy the exact name from `.env.example`
3. Common mistake: `OPENROUTER_API_KEYS` → should be `OPENROUTER_API_KEY`

### Error: "CORS not allowing origin http://localhost:3000"

**Cause:** `CORS_ORIGINS` in `backend/.env` doesn't include `http://localhost:3000`

**Solution:**
```env
# backend/.env should have:
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### Error: Backend won't start

**Checklist:**
1. ✅ `backend/.env` exists?
   ```bash
   ls backend/.env
   ```

2. ✅ All required variables filled in?
   ```bash
   grep "SUPABASE\|OPENROUTER" backend/.env | grep -v "^#"
   ```

3. ✅ Backend restarted after .env change?
   ```bash
   # Kill current process (Ctrl+C)
   # Restart:
   python -m app.main
   ```

4. ✅ Port 8000 not already in use?
   ```bash
   lsof -i :8000  # macOS/Linux
   netstat -ano | findstr :8000  # Windows
   ```

### Error: Frontend can't connect to backend

**Checklist:**
1. ✅ Backend running on port 8000?
   ```bash
   curl http://localhost:8000/health
   ```

2. ✅ Frontend `.env.local` has correct API URL?
   ```bash
   cat frontend/.env.local | grep NEXT_PUBLIC_API_URL
   ```

3. ✅ Browser DevTools (F12 → Network) shows CORS headers?
   - Look for `access-control-allow-origin: http://localhost:3000`

## 📋 Step-by-Step Setup

### First Time Setup

```bash
# 1. Backend
cd backend
cp .env.example .env
# Edit .env with your credentials
python -m app.main
# Should see: "Uvicorn running on http://0.0.0.0:8000"

# 2. Frontend (in another terminal)
cd frontend
cp .env.local.example .env.local
# Edit .env.local with your credentials
npm run dev
# Should see: "ready - started server on 0.0.0.0:3000"

# 3. Browser
# Go to http://localhost:3000
# Try to sign up or login
```

### Daily Development

```bash
# Terminal 1: Backend
cd backend
python -m app.main

# Terminal 2: Frontend
cd frontend
npm run dev

# Browser
# http://localhost:3000
```

## ✅ Verification Checklist

After setup, verify everything works:

- [ ] Backend running on http://localhost:8000
- [ ] Frontend running on http://localhost:3000
- [ ] Can access backend health check: `curl http://localhost:8000/health`
- [ ] Can load frontend homepage
- [ ] Can see Network requests in browser DevTools (F12)
- [ ] CORS headers present in API responses
- [ ] Can sign up new account
- [ ] Can login with existing account
- [ ] Can create account (after signup)
- [ ] Dashboard loads without errors

## 🔍 Credential Sources

### Supabase

1. Go to https://app.supabase.com
2. Select your project
3. Click Settings (⚙️ icon)
4. Click API
5. Copy:
   - `Project URL` → `SUPABASE_URL`
   - `Service Role Key` → `SUPABASE_KEY` (backend only!)
   - `anon public` → `NEXT_PUBLIC_SUPABASE_ANON_KEY` (frontend only)
6. Go to Settings → Auth → JWT Settings
7. Copy `JWT Secret` → `SUPABASE_JWT_SECRET`

### OpenRouter

1. Go to https://openrouter.ai
2. Create account
3. Click your profile icon
4. Click Keys
5. Create new API key
6. Copy → `OPENROUTER_API_KEY` in backend/.env

## 💡 Common Patterns

### Multiple Environments

If you want dev/staging/production:

```bash
# Use different .env files
backend/.env              # Development (gitignored)
backend/.env.staging      # Staging (gitignored)
backend/.env.production   # Production (gitignored)

# Load with: python -m dotenv -f backend/.env.staging run python -m app.main
```

### Shared Credentials in Team

Use `.env.template.local` (no secrets):
```env
# backend/.env.template
SUPABASE_URL=XXX  # Ask team lead for credentials
OPENROUTER_API_KEY=XXX  # Get from 1Password or LastPass
```

Then in README:
```
1. Ask team lead for credentials
2. Fill in backend/.env using .env.example as template
```

## 🚀 Deployment

### Vercel (Frontend)

1. Go to https://vercel.com
2. Import your repo
3. Add environment variables:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_API_URL` (your production backend URL)
4. Deploy

### Railway (Backend)

1. Go to https://railway.app
2. Import your repo
3. Add environment variables from `.env.example`
4. Deploy

## 📞 Need Help?

Check:
1. `.env.example` files for exact field names
2. This guide for common issues
3. Backend logs for detailed errors
4. Browser DevTools (F12) for frontend/network issues
