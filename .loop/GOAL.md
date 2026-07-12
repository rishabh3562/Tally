# Goal: Improve the finance chat feature

Make the "Ask About Your Finances" chat (backend `app/services/chat_service.py`,
`app/api/chat.py`; frontend `app/chat/page.tsx`, `hooks/useChat.ts`) actually work
well and grow useful features around it.

Known problems to fix, roughly in priority order:

1. **Chat is dead.** `chat_service.run_query` calls a Postgres `sql_exec` RPC that
   does not exist anywhere in the repo, so every question errors out. Replace the
   raw-SQL path with PostgREST + Python aggregation, mirroring `app/api/insights.py`.
2. **Date filters never applied.** `build_sql_query` is always called with empty
   `filters={}`, so "last month" / "in May" questions silently return all-time data.
   Parse a period from the question and filter by it.
3. **LLM call is blocking + duplicated.** `explain_with_llm` uses a blocking
   `requests.post` to OpenRouter directly instead of the shared async
   `app/services/llm_client.py` (which does Gemini key rotation + fallback). Route
   through `llm_client.acomplete`, with a deterministic fallback when no LLM is up.
4. **SQL injection debt.** `build_sql_query` f-string-interpolates values. Latent
   today (no user string reaches SQL) but must not survive the rewrite.
5. **Streaming + UX.** Char-by-char SSE is fragile; frontend has no partial-line
   buffering, no clickable example prompts, no conversation persistence.

## Constraints
- Never touch `.env*`, secrets, or credentials. Never hardcode API keys — all
  config comes from `app/core/config.py` (env only).
- Backend tests run with SYSTEM Python310 (not `backend/venv`). No DB in the loop,
  so verify pure functions with unit tests + import checks; be honest in the log
  that the live SQL/LLM runtime path is unverified here.
- One small, verified change per iteration. Commit format: `loop: <what and why>`.
- No `Co-Authored-By` trailer in commits.
