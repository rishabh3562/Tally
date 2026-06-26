-- Personal Finance OS — Initial Schema
-- Run this in Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";

-- Users table (extends Supabase Auth)
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT UNIQUE NOT NULL,
  preferences JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Bank accounts
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
  logo TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
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
  icon TEXT,
  is_system BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Transactions (core table)
CREATE TABLE IF NOT EXISTS transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  date DATE NOT NULL,
  amount NUMERIC(12, 2) NOT NULL,
  currency TEXT DEFAULT 'INR',
  raw_merchant TEXT,
  merchant_id UUID REFERENCES merchants(id),
  category_id UUID REFERENCES categories(id),
  memo TEXT,
  fingerprint TEXT UNIQUE NOT NULL,
  is_transfer BOOLEAN DEFAULT FALSE,
  confidence_score REAL DEFAULT 1.0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Category assignments with confidence (supports multiple tags per transaction)
CREATE TABLE IF NOT EXISTS transaction_categories (
  id SERIAL PRIMARY KEY,
  transaction_id UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
  category_id UUID NOT NULL REFERENCES categories(id),
  confidence REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
  source TEXT DEFAULT 'rule' CHECK (source IN ('rule', 'regex', 'llm', 'user')),
  UNIQUE(transaction_id, category_id)
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

-- Events (user-defined transaction groups)
CREATE TABLE IF NOT EXISTS events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  metadata JSONB,
  summary TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS event_transactions (
  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  transaction_id UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
  PRIMARY KEY (event_id, transaction_id)
);

-- Notes / summaries for RAG (without pgvector for MVP)
CREATE TABLE IF NOT EXISTS notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  source TEXT DEFAULT 'system' CHECK (source IN ('event_summary', 'user_note', 'monthly_digest')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- File processing jobs (for dedup and retry tracking)
CREATE TABLE IF NOT EXISTS processing_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  file_hash TEXT NOT NULL,
  status TEXT DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'done', 'failed')),
  error TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  finished_at TIMESTAMPTZ
);

-- Create indices for common queries
CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_user_date ON transactions(user_id, date DESC);
CREATE INDEX idx_transactions_user_category ON transactions(user_id, category_id);
CREATE INDEX idx_transactions_fingerprint ON transactions(fingerprint);
CREATE INDEX idx_accounts_user_id ON accounts(user_id);
CREATE INDEX idx_events_user_id ON events(user_id);
CREATE INDEX idx_processing_jobs_user_id ON processing_jobs(user_id);
CREATE INDEX idx_merchant_aliases_alias ON merchant_aliases(alias);
CREATE INDEX idx_learning_records_user_raw ON learning_records(user_id, raw_merchant);

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE transaction_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY;

-- RLS Policies
-- Users can only see their own data
CREATE POLICY "Users see own data" ON users
  FOR ALL USING (auth.uid() = id);

CREATE POLICY "Users see own accounts" ON accounts
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users see own transactions" ON transactions
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users see own transaction categories" ON transaction_categories
  FOR ALL USING (
    transaction_id IN (
      SELECT id FROM transactions WHERE user_id = auth.uid()
    )
  );

CREATE POLICY "Users see own categories" ON categories
  FOR ALL USING (user_id IS NULL OR user_id = auth.uid());

CREATE POLICY "Users see own learning records" ON learning_records
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users see own events" ON events
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users see own event transactions" ON event_transactions
  FOR ALL USING (
    event_id IN (SELECT id FROM events WHERE user_id = auth.uid())
  );

CREATE POLICY "Users see own notes" ON notes
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users see own processing jobs" ON processing_jobs
  FOR ALL USING (auth.uid() = user_id);

-- Seed system categories
INSERT INTO categories (name, is_system, icon) VALUES
  ('Food & Dining', TRUE, '🍽️'),
  ('Transport', TRUE, '🚗'),
  ('Entertainment', TRUE, '🎬'),
  ('Shopping', TRUE, '🛍️'),
  ('Utilities', TRUE, '💡'),
  ('Healthcare', TRUE, '⚕️'),
  ('Education', TRUE, '📚'),
  ('Travel', TRUE, '✈️'),
  ('Groceries', TRUE, '🛒'),
  ('Subscriptions', TRUE, '🔄'),
  ('Other', TRUE, '📌')
ON CONFLICT DO NOTHING;

-- Seed common merchants
INSERT INTO merchants (name, domain) VALUES
  ('Swiggy', 'swiggy.com'),
  ('Zomato', 'zomato.com'),
  ('Uber', 'uber.com'),
  ('Ola', 'olaride.com'),
  ('Amazon', 'amazon.in'),
  ('Flipkart', 'flipkart.com'),
  ('BigBasket', 'bigbasket.com'),
  ('Starbucks', 'starbucks.com'),
  ('Netflix', 'netflix.com'),
  ('Spotify', 'spotify.com')
ON CONFLICT (name) DO NOTHING;

-- Seed merchant aliases
INSERT INTO merchant_aliases (merchant_id, alias, match_type)
SELECT id, 'SWIGGY', 'exact' FROM merchants WHERE name = 'Swiggy'
UNION ALL
SELECT id, 'ZOMATO', 'exact' FROM merchants WHERE name = 'Zomato'
UNION ALL
SELECT id, 'UBER', 'exact' FROM merchants WHERE name = 'Uber'
UNION ALL
SELECT id, 'OLA', 'exact' FROM merchants WHERE name = 'Ola'
UNION ALL
SELECT id, 'AMZN', 'exact' FROM merchants WHERE name = 'Amazon'
UNION ALL
SELECT id, 'FLIPKART', 'exact' FROM merchants WHERE name = 'Flipkart'
ON CONFLICT DO NOTHING;
