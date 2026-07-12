-- Migration 002: transaction groups (clubbing collective payments).
-- Run once in the Supabase SQL editor. Idempotent / safe to re-run.

CREATE TABLE IF NOT EXISTS transaction_groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  kind TEXT DEFAULT 'manual' CHECK (kind IN ('manual', 'auto')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transaction_groups_user ON transaction_groups(user_id);

-- Attach transactions.group_id -> transaction_groups (column added in 001).
-- When a group is deleted, its transactions are simply un-clubbed.
DO $$ BEGIN
  ALTER TABLE transactions
    ADD CONSTRAINT fk_transactions_group
    FOREIGN KEY (group_id) REFERENCES transaction_groups(id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- RLS to match the rest of the schema.
ALTER TABLE transaction_groups ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
  CREATE POLICY "Users see own groups" ON transaction_groups
    FOR ALL USING (auth.uid() = user_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
