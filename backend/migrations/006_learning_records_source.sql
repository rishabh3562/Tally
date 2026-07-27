-- 006: tell a user's decision apart from a machine's guess
--
-- `learning_records` is what makes "fix a category once and it sticks" work, but
-- four different code paths write to it: the triage screen and the chat write what
-- the USER decided, while /recategorize writes what a rule or the LLM GUESSED.
-- Nothing distinguished them, which broke the promise in both directions:
--
--   * rules outranked corrections, because `categorize_transaction` consults
--     learning_records only after `rule_category` misses;
--   * and honouring the table unconditionally instead would freeze whatever the
--     rules happened to output the first time /recategorize ran, killing every
--     future rule improvement.
--
-- With provenance recorded, `source='user'` can take precedence over rules while
-- 'rule'/'llm' rows stay a cheap cache. Idempotent — safe to re-run.

ALTER TABLE learning_records ADD COLUMN IF NOT EXISTS source TEXT;

-- Backfill BEFORE setting the default: every row that exists today was made by
-- hand (triage / chat / single-row correction). Doing it in this order also keeps
-- a re-run safe — after /recategorize has written 'rule' rows, a second run of
-- this file must not promote them to 'user'.
UPDATE learning_records SET source = 'user' WHERE source IS NULL;

-- A weak default from here on: a path that forgets to say what it is degrades to
-- "machine guess", never to "user intent".
ALTER TABLE learning_records ALTER COLUMN source SET DEFAULT 'rule';

DO $$ BEGIN
  ALTER TABLE learning_records
    ADD CONSTRAINT learning_records_source_check
    CHECK (source IN ('user', 'rule', 'llm'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_learning_records_user_source
  ON learning_records(user_id, source);
