# Improvement Loop — Progress Log

Goal: see `.loop/GOAL.md` — improve the finance chat feature.

---

## Iteration 1 — 2026-07-12 — Make chat actually return data

**What changed**
- Rewrote `backend/app/services/chat_service.py`. Removed the dead raw-SQL path
  (`build_sql_query` + `run_query` called a Postgres `sql_exec` RPC that does not
  exist anywhere in the repo, so every chat question errored out). Replaced it with
  PostgREST fetch + Python aggregation, mirroring `app/api/insights.py`.
- Added `parse_period()` — resolves "this month", "last month", "last N days",
  named months ("in May", "March 2024"), "this/last year" into an inclusive
  `(start, end)` date range. Fixes the bug where filters were always empty `{}`,
  so date-scoped questions silently returned all-time data.
- Added `extract_category()` and deterministic answer formatters for
  total-by-category, merchant breakdown, open-ended net, and events (events read
  `name`/`total_amount` directly — no join). Answers are number-driven; no SQL
  injection surface remains (values go through PostgREST, not string interpolation).
- Fixed SSE framing: stream whitespace-delimited tokens as single-line `data:`
  events instead of char-by-char (which could break on embedded newlines).
- No LLM call in this iteration — answers are fully deterministic for now.
- Added `backend/tests/test_chat_service.py` (first backend test file): 26 tests
  over intent classification, category extraction, period parsing, formatters, SSE.

**Verification**
- `python -m pytest tests/test_chat_service.py` → 26 passed (system Python310).
- Import check: `app.api.chat` + `app.services.chat_service` import cleanly.
- NOT verified here: the live PostgREST fetch and end-to-end SSE against a real
  Supabase DB (no DB available in the loop). Pure functions + import path only.

**Next planned step**
- Iteration 2: route answer phrasing through the shared async `llm_client.acomplete`
  (Gemini rotation + OpenRouter fallback) to rephrase the deterministic numbers,
  with the deterministic string as the guaranteed fallback when no LLM is available.
  Do the same for `events.py`'s duplicated blocking OpenRouter call.

---

## Iteration 2 — 2026-07-12 — LLM rephrasing via shared async client (with guardrails)

**What changed**
- Reconnected chat answers to an LLM, but through the shared async
  `app/services/llm_client.py` (`acomplete` → Gemini key rotation + OpenRouter
  fallback) instead of the old blocking, duplicated `requests.post` to OpenRouter.
  Fulfils goal item 3.
- New `rephrase(question, deterministic_answer)`: asks the LLM to reword the
  already-computed answer conversationally. Guardrails: (a) skip entirely if no
  provider is configured, (b) fall back to the deterministic answer on any error,
  (c) reject the LLM output if any `Rs …` figure from the deterministic answer is
  missing (i.e. the model altered a number) — the correct numbers always win.
- `stream_chat_response` now awaits `rephrase` before streaming.
- Added 4 tests (mocked llm_client): unavailable-skip, error-fallback,
  altered-figure-rejection, faithful-rewrite-accepted.

**Verification**
- `python -m pytest tests/test_chat_service.py` → 30 passed (system Python310).
- Import check: `stream_chat_response` is an async generator; API imports clean.
- NOT verified here: a real LLM provider response end-to-end (mocked in tests).

**Next planned step**
- Iteration 3 (frontend): make the example prompts on `app/chat/page.tsx`
  clickable so they send the question, and add partial-line buffering in
  `hooks/useChat.ts` (the SSE reader currently assumes each read is a whole line).

STATUS: IN_PROGRESS
