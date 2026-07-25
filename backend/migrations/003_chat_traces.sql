-- 003: chat observability
-- One row per chat turn: the question, the exact tool calls + results the agent
-- made, the final answer, and how it was produced. This is the homegrown "why
-- did the chat say that?" trace — no external service. Idempotent.

CREATE TABLE IF NOT EXISTS chat_traces (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  question     TEXT,
  steps        JSONB,          -- [{tool, args, result}, ...] the agent executed
  answer       TEXT,
  source       TEXT,           -- 'agent' | 'deterministic' | 'error-fallback'
  action_taken BOOLEAN DEFAULT FALSE,   -- did a write-action run this turn?
  error        TEXT,
  duration_ms  INTEGER
);

CREATE INDEX IF NOT EXISTS idx_chat_traces_user
  ON chat_traces(user_id, created_at DESC);
