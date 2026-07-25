-- Migration 001: richer transaction datapoints, job provenance, storage.
-- Run this once in the Supabase SQL editor. Safe to re-run (idempotent).
--
-- Context: we promote UPI id / time / direction / funding source to real columns,
-- link each transaction to the job that imported it (correlation) and to the
-- archived source file in Storage (provenance), and add a group_id for clubbing.

-- 1) processing_jobs metrics (if not already applied)
ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS stats JSONB;

-- 2) transactions: new first-class datapoints
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS upi_transaction_id TEXT;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS txn_time TIME;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS direction TEXT;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS counterparty TEXT;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS funding_source TEXT;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS source_job_id UUID REFERENCES processing_jobs(id) ON DELETE SET NULL;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS source_file_path TEXT;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS group_id UUID;

-- 3) supporting indexes
CREATE INDEX IF NOT EXISTS idx_transactions_upi_txn_id ON transactions(upi_transaction_id);
CREATE INDEX IF NOT EXISTS idx_transactions_source_job ON transactions(source_job_id);
CREATE INDEX IF NOT EXISTS idx_transactions_group ON transactions(group_id);

-- 4) (Optional, NOT included here) The dedup fingerprint now keys on the UPI
--    transaction id, so to get UPI ids / provenance on your EXISTING rows you'd
--    re-upload the statement. Adding the columns above is non-destructive and
--    leaves current rows intact (new columns just become NULL). If you DO want a
--    clean re-import, run the clearly-labelled `optional_reset_transactions.sql`
--    separately — it is deliberately NOT part of this schema-alignment migration.

-- 5) STORAGE (do this in the dashboard, not SQL):
--    Storage -> New bucket -> name "statements", PRIVATE (uncheck "Public").
--    The backend writes/reads it with the service-role key, so no bucket RLS
--    policy is required. If you name it differently, set SUPABASE_STATEMENTS_BUCKET.
