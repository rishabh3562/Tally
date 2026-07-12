-- Personal Finance OS - Supabase Schema
-- Run this SQL in Supabase SQL Editor to set up the database

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";

-- Users table (extends Supabase Auth)
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT UNIQUE NOT NULL,
  preferences JSONB DEFAULT '{"default_currency":"INR","theme":"light"}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Bank accounts (multi-account support)
CREATE TABLE IF NOT EXISTS accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('Bank', 'CreditCard', 'UPI', 'Investment')),
  bank_code TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Canonical merchants
CREATE TABLE IF NOT EXISTS merchants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT UNIQUE NOT NULL,
  domain TEXT,
  logo TEXT
);

-- Merchant alias lookup (raw string → canonical merchant)
CREATE TABLE IF NOT EXISTS merchant_aliases (
  id SERIAL PRIMARY KEY,
  merchant_id UUID REFERENCES merchants(id) ON DELETE CASCADE,
  alias TEXT NOT NULL UNIQUE,
  match_type TEXT DEFAULT 'exact' CHECK (match_type IN ('exact', 'prefix', 'regex', 'llm_confirmed'))
);

-- Categories (hierarchical; system + user-custom)
CREATE TABLE IF NOT EXISTS categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  parent_id UUID REFERENCES categories(id),
  icon TEXT DEFAULT '📌'
);

-- Transactions (core table)
CREATE TABLE IF NOT EXISTS transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  account_id UUID REFERENCES accounts(id),
  date DATE NOT NULL,
  amount NUMERIC(12,2) NOT NULL,
  currency TEXT DEFAULT 'INR',
  raw_merchant TEXT,
  merchant_id UUID REFERENCES merchants(id),
  category_id UUID REFERENCES categories(id),
  memo TEXT,
  fingerprint TEXT UNIQUE NOT NULL,
  is_transfer BOOLEAN DEFAULT FALSE,
  confidence_score REAL DEFAULT 1.0,
  -- Richer datapoints captured at ingestion (esp. from UPI/GPay statements).
  upi_transaction_id TEXT,             -- first-class UPI reference id (was memo-only)
  txn_time TIME,                       -- time-of-day when available
  direction TEXT CHECK (direction IN ('debit', 'credit')),
  counterparty TEXT,                   -- cleaned payee/payer name
  funding_source TEXT,                 -- e.g. "Paid by State Bank of India 9112"
  source_job_id UUID,                  -- provenance / correlation (FK added below, after processing_jobs exists)
  source_file_path TEXT,               -- path in the statements Storage bucket
  group_id UUID,                       -- clubbing collective payments (set by analytics)
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Category assignments with confidence (supports multiple tags per transaction)
CREATE TABLE IF NOT EXISTS transaction_categories (
  transaction_id UUID REFERENCES transactions(id) ON DELETE CASCADE,
  category_id UUID REFERENCES categories(id),
  confidence REAL NOT NULL DEFAULT 1.0,
  source TEXT DEFAULT 'rule' CHECK (source IN ('rule', 'regex', 'llm', 'user')),
  PRIMARY KEY (transaction_id, category_id)
);

-- User feedback / learning records
CREATE TABLE IF NOT EXISTS learning_records (
  id SERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  raw_merchant TEXT NOT NULL,
  category_id UUID REFERENCES categories(id),
  merchant_id UUID REFERENCES merchants(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, raw_merchant)
);

-- Events / Case Studies (user-defined transaction groups)
CREATE TABLE IF NOT EXISTS events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  metadata JSONB DEFAULT '{}',
  summary TEXT,
  total_amount NUMERIC(12,2) DEFAULT 0,
  currency TEXT DEFAULT 'INR',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS event_transactions (
  event_id UUID REFERENCES events(id) ON DELETE CASCADE,
  transaction_id UUID REFERENCES transactions(id) ON DELETE CASCADE,
  PRIMARY KEY (event_id, transaction_id)
);

-- Notes / summaries for RAG (embedded into pgvector)
CREATE TABLE IF NOT EXISTS notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  source TEXT DEFAULT 'system' CHECK (source IN ('event_summary', 'user_note', 'monthly_digest')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  embedding vector(1536)
);

-- File processing jobs (for dedup and retry tracking)
CREATE TABLE IF NOT EXISTS processing_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  file_hash TEXT NOT NULL,
  status TEXT DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'done', 'failed')),
  error TEXT,
  -- Per-job metrics captured during ingestion (parsed/inserted/skipped counts,
  -- category distribution, sample errors, duration, human-readable message).
  stats JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  finished_at TIMESTAMPTZ
);
-- Migration for existing projects (safe to re-run):
--   ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS stats JSONB;

-- Now that processing_jobs exists, attach the transactions.source_job_id FK.
-- Wrapped so a re-run doesn't error on the already-present constraint.
DO $$ BEGIN
  ALTER TABLE transactions
    ADD CONSTRAINT fk_transactions_source_job
    FOREIGN KEY (source_job_id) REFERENCES processing_jobs(id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Transaction groups (clubbing collective payments; manual or auto-detected)
CREATE TABLE IF NOT EXISTS transaction_groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  kind TEXT DEFAULT 'manual' CHECK (kind IN ('manual', 'auto')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
DO $$ BEGIN
  ALTER TABLE transactions
    ADD CONSTRAINT fk_transactions_group
    FOREIGN KEY (group_id) REFERENCES transaction_groups(id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Chat conversation history
CREATE TABLE IF NOT EXISTS chat_conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT DEFAULT 'Conversation',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_id, date);
CREATE INDEX IF NOT EXISTS idx_transactions_user_category ON transactions(user_id, category_id);
CREATE INDEX IF NOT EXISTS idx_transactions_fingerprint ON transactions(fingerprint);
CREATE INDEX IF NOT EXISTS idx_transactions_upi_txn_id ON transactions(upi_transaction_id);
CREATE INDEX IF NOT EXISTS idx_transactions_source_job ON transactions(source_job_id);
CREATE INDEX IF NOT EXISTS idx_transactions_group ON transactions(group_id);
CREATE INDEX IF NOT EXISTS idx_events_user_id ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_learning_records_user_merchant ON learning_records(user_id, raw_merchant);
CREATE INDEX IF NOT EXISTS idx_notes_user_id ON notes(user_id);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_user_id ON processing_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_file_hash ON processing_jobs(file_hash);
CREATE INDEX IF NOT EXISTS idx_transaction_groups_user ON transaction_groups(user_id);

-- Enable RLS (Row-Level Security)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE transaction_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- RLS Policies - Users can only see their own data
CREATE POLICY "Users see own data" ON transactions FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users see own accounts" ON accounts FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users see own categories" ON categories FOR ALL USING (auth.uid() = user_id OR user_id IS NULL);
CREATE POLICY "Users see own events" ON events FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users see own event transactions" ON event_transactions FOR ALL USING (
  event_id IN (SELECT id FROM events WHERE auth.uid() = user_id)
);
CREATE POLICY "Users see own notes" ON notes FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users see own learning records" ON learning_records FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users see own processing jobs" ON processing_jobs FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users see own groups" ON transaction_groups FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users see own conversations" ON chat_conversations FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users see own messages" ON chat_messages FOR ALL USING (auth.uid() = user_id);

-- Seed system categories (these are global, not user-specific)
INSERT INTO categories (name, icon, user_id) VALUES
  ('Food & Dining', '🍔', NULL),
  ('Transport', '🚗', NULL),
  ('Shopping', '🛍️', NULL),
  ('Entertainment', '🎬', NULL),
  ('Groceries', '🛒', NULL),
  ('Utilities', '💡', NULL),
  ('Healthcare', '🏥', NULL),
  ('Education', '📚', NULL),
  ('Travel', '✈️', NULL),
  ('Subscriptions', '📱', NULL),
  ('Other', '📌', NULL)
ON CONFLICT DO NOTHING;

-- Seed common merchants
INSERT INTO merchants (name, logo) VALUES
  ('Swiggy', '🍕'),
  ('Zomato', '🍜'),
  ('Uber', '🚗'),
  ('Ola', '🚗'),
  ('Amazon', '📦'),
  ('Flipkart', '📦'),
  ('BigBasket', '🛒'),
  ('Netflix', '📺'),
  ('Spotify', '🎵'),
  ('Starbucks', '☕')
ON CONFLICT DO NOTHING;

-- Create trigger function to automatically create user profile on signup
CREATE OR REPLACE FUNCTION public.create_user_profile()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.users (id, email, preferences)
  VALUES (NEW.id, NEW.email, '{"default_currency":"INR","theme":"light"}')
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to create user profile when user signs up
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.create_user_profile();
