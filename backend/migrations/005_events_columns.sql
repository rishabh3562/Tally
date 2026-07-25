-- 005: align the live events table with case-study events (#9)
-- The live DB predates these columns (schema drift); the events feature writes a
-- user description and a computed total. Idempotent — safe to re-run.

ALTER TABLE events ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE events ADD COLUMN IF NOT EXISTS total_amount NUMERIC(12,2) DEFAULT 0;
ALTER TABLE events ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'INR';
ALTER TABLE events ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
