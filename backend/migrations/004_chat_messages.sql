-- 004: persist chat history
-- A flat per-user message log so the conversation survives a reload. No separate
-- "conversations" table — one implicit thread per user is enough at this scale.
-- Idempotent.

CREATE TABLE IF NOT EXISTS chat_messages (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content    TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_user
  ON chat_messages(user_id, created_at);
