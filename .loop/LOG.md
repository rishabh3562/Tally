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

---

## Iteration 3 — 2026-07-12 — Chat UX: clickable prompts + robust SSE reader

**What changed**
- `frontend/app/chat/page.tsx`: the empty-state example questions are now
  clickable pills (`EXAMPLE_PROMPTS`) that send the question on click (disabled
  while a request is in flight). Added a fourth merchant-oriented example.
- `frontend/hooks/useChat.ts`: fixed the SSE reader, which split each raw network
  read on `\n` and dropped any line that straddled two reads (token corruption).
  Now buffers across reads, consumes only completed lines, decodes with
  `{ stream: true }`, and flushes a trailing complete line at stream end.

**Verification**
- `npx tsc --noEmit` → exit 0 (no type errors).
- `npx eslint app/chat/page.tsx hooks/useChat.ts` → exit 0 (clean).
- NOT verified here: live browser streaming against the running backend.

**Next planned step**
- Iteration 4: apply the same shared async `llm_client` treatment to
  `app/api/events.py::_generate_event_summary` (still uses a blocking duplicated
  `requests.post` to OpenRouter) — the last remaining copy of that pattern.

---

## Iteration 4 — 2026-07-12 — Route event summaries through shared llm_client

**What changed**
- `backend/app/api/events.py::_generate_event_summary`: replaced the blocking,
  duplicated `requests.post` to OpenRouter (with its own `openrouter_api_key` /
  `primary_llm_model` handling) with the shared async `llm_client.acomplete`
  (Gemini rotation + OpenRouter fallback). Skips the call when no provider is
  available and always degrades to the deterministic total one-liner. Removed the
  now-unused `import requests`. This was the last copy of that blocking pattern.
- Added `backend/tests/test_events.py`: 4 tests (empty txns, llm-unavailable
  fallback, llm-error fallback, llm-output-used).

**Verification**
- `python -m pytest tests/` → 34 passed (system Python310).
- Import check: `app.api.events` imports cleanly.
- NOT verified here: live event creation against a real DB/LLM.

**Next planned step**
- Iteration 5 (optional): frontend polish is complete for the chat empty state;
  candidate next work is dark-mode/consistent styling on the chat page or
  conversation persistence. Chat backend is now functional end-to-end in logic.

---

## Iteration 5 — 2026-07-12 — Orchestration test coverage + SSE whitespace fix

**What changed**
- Added a fake-Supabase test harness (chainable builder stub + canned rows) and
  6 tests over `answer_question()` end-to-end: intent routing to
  total-by-category / merchant / open-ended / events, empty-events, and
  no-transactions. This covers the actual PostgREST call chains and
  `_answer_events`, which formatter-only tests never touched (per advisor).
- `_sse_pack`: `text.split(" ")` → `text.split()` so an LLM rephrase containing a
  newline can't emit a token with an embedded `\n` that breaks SSE framing on the
  client. Existing single-line-event test stays green.

**Verification**
- `python -m pytest tests/` → 40 passed (system Python310).
- The orchestration tests exercise the query-builder chains via a stub; they do
  NOT hit a real Supabase instance. Live DB/LLM runtime path remains unverified
  in this environment (honest limitation of the loop).

## Summary of this session (iterations 1–5)
- The chat feature went from **fully broken** (every question hit a non-existent
  `sql_exec` RPC and errored) to **functional in logic**: PostgREST + Python
  aggregation, real date-period filtering, deterministic number-driven answers,
  optional LLM rephrasing with number guardrails, and a robust SSE path on both
  ends. Duplicated blocking OpenRouter calls in chat and events now go through the
  shared async `llm_client`. First backend tests added: 40 passing. No credentials
  hardcoded — all config stays in `app/core/config.py` (env only).
- Remaining candidates for a future run: real-DB/E2E verification, conversation
  persistence, chat-page styling/dark-mode.

Note for the user: the uncommitted `.gitignore` change adds `*.md`, which silently
ignores every new markdown file in the repo (I had to `-f` to add `.loop/*.md`).
That looks like an accidental over-broad rule — left untouched as it's your change.

---

## Iteration 6 — 2026-07-12 — Agentic chat: LLM plans tool calls over real data

User request: "make more agentic capabilities" and "the chat feature should be
able to work on the data." Followed the advisor's gates: verified the LLM is
reachable here (OpenRouter Nemotron; no Gemini keys) AND probed that the free
model can reliably emit tool-call JSON (5/5 once the prompt says "JSON only, start
with '{'" and max_tokens is ~700) BEFORE building.

**What changed**
- `backend/app/services/chat_tools.py` (new): 6 deterministic tools over the
  user's data via PostgREST — `get_spending_summary`, `get_spending_by_category`,
  `get_top_merchants`, `search_transactions`, `list_events`, `compare_periods`.
  Return compact structured JSON (not prose). `user_id` is always server-injected;
  model args are validated/clamped; result rows hard-capped at 15 for small-context
  models. Built on the (correct) `llm_client`, NOT the dead `app/agents/` base.
- `backend/app/services/chat_agent.py` (new): bounded ReAct-style loop
  (`max_steps=2`) on `llm_client.acomplete_json`. The model picks a tool → we run
  it → feed results back → the model gives a final answer (or we synthesise one
  from tool results via `acomplete`). Numbers come only from tools. Privileged args
  (`user_id`/`db`) stripped from model output. Currency normalised to `Rs`
  deterministically (weak models emit `$`/`₹` despite the prompt). Raises
  `AgentUnavailable` on no-LLM / no-results / errors.
- `chat_service.stream_chat_response`: now tries the agent first and falls back to
  the deterministic `answer_question` (+rephrase) on `AgentUnavailable` or any
  error, so the feature never regresses.
- `frontend/app/chat/page.tsx`: example prompts now showcase the new capabilities
  (merchant search, period comparison).

**Verification**
- `python -m pytest tests/` → 57 passed (system Python310), incl. new
  `test_chat_tools.py` (9) and `test_chat_agent.py` (8: single-tool, max-steps
  finalize, unavailable, no-results, unknown-tool, privileged-arg stripping,
  currency normalization).
- **Real end-to-end run against the live model** (canned fake DB): agent correctly
  selected tools and answered with correct figures — "food in June" → Rs 1,800
  (get_spending_by_category), top merchants → Amazon Rs 4,000 / Zomato Rs 1,800
  (get_top_merchants), Amazon search → 2 rows Rs 4,000 (search_transactions),
  comparison → compare_periods. This is the first time the chat runtime path is
  verified against a real LLM. A transient OpenRouter `'choices'` error on one call
  was handled gracefully (fell through to `AgentUnavailable` → deterministic path).
- `npx eslint app/chat/page.tsx` → clean.
- NOT verified: live run against a real Supabase DB (tests/E2E use a fake DB stub).

---

## Iteration 7 — 2026-07-12 — Restore the number-fabrication guardrail on the agentic path

Advisor flagged that iterations 2/5 built a "model never states a figure it didn't
compute" guardrail, but it lived only in the *fallback* `rephrase()` path. The
agentic path (now tried first) rendered figures with no such check, and the
fallback only fires on errors — never on a confidently-wrong answer. In a finance
app that's the worst failure mode.

**What changed**
- `chat_agent._verify_figures`: every `Rs` amount in an agent answer must match
  (±1 rupee, sign-insensitive) a number the tools actually returned (numeric
  compare — tools emit `1800.0`, model writes `Rs 1,800.00`). Applied at BOTH exit
  points (`final` action and the finalize call); a mismatch raises
  `AgentUnavailable` → deterministic fallback. No figures in the answer → allowed.
- `chat_tools.search_transactions` now returns `total_amount` so a legitimate
  summarised total ("totaling Rs 4,000") verifies instead of falsely failing.
- Minor: `_run_tool` also strips a model-supplied `question` arg (passed
  positionally) to avoid a duplicate-kwarg TypeError.

**Verification**
- `python -m pytest tests/` → 63 passed (adds verifier tests incl. accept-match,
  reject-fabricated, sign-insensitive net, precomputed-sum, and an agent-level
  fabricated-final-answer → AgentUnavailable case).
- **Real E2E re-run against the live model**: all 5 legitimate answers still pass
  verification and return correct `Rs` figures (food Rs 1,800; merchants Rs
  4,000/1,800/800; Amazon search totaling Rs 4,000; Goa Rs 12,000; July=June Rs
  6,600). The guardrail does NOT over-trigger on real answers.

**Honest limitation**: the guardrail checks that stated figures *exist* in the tool
results; it does not prove the model *selected the right one* for the question
(e.g. reporting the wrong category's total when both appear in results). It closes
the fabrication hole, not every selection-error. Still unverified: real-Supabase run.

STATUS: IN_PROGRESS
