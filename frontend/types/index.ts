/**
 * Type definitions for the application
 */

// User
export interface User {
  id: string;
  email: string;
  created_at: string;
}

// Transaction
export interface Transaction {
  id: string;
  user_id: string;
  account_id: string;
  date: string;
  amount: number;
  currency: string;
  raw_merchant: string;
  merchant_id?: string;
  category_id?: string;
  memo?: string;
  is_transfer: boolean;
  created_at: string;
}

// Merchant
export interface Merchant {
  id: string;
  name: string;
  domain?: string;
  logo?: string;
}

// Category
export interface Category {
  id: string;
  user_id?: string;
  name: string;
  parent_id?: string;
  icon?: string;
}

// Event
export interface Event {
  id: string;
  user_id: string;
  name: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  metadata?: Record<string, any>;
  summary?: string;
  created_at: string;
}

// Account
export interface Account {
  id: string;
  user_id: string;
  name: string;
  type: 'Bank' | 'CreditCard' | 'UPI' | 'Investment';
  bank_code?: string;
  created_at: string;
}

// API Response
export interface ApiResponse<T> {
  data?: T;
  error?: string;
  message?: string;
  status?: number;
}

// Upload Job
export interface UploadJob {
  job_id: string;
  status: 'queued' | 'processing' | 'done' | 'failed';
  error?: string;
  created_at?: string;
  finished_at?: string;
}

// Ingestion job status values
export type JobStatus = 'queued' | 'processing' | 'done' | 'failed';

// Per-job ingestion stats (GET /api/jobs, GET /api/jobs/{id})
export interface JobStats {
  parser: string | null;
  parsed: number;
  inserted: number;
  duplicates_skipped: number;
  failed: number;
  debit_count: number;
  debit_total: number;
  credit_count: number;
  credit_total: number;
  categories: Record<string, number>;
  duration_ms: number;
  // Some jobs surface per-row parse errors (rendered in the upload panel).
  errors?: string[];
}

// Ingestion job (GET /api/jobs, GET /api/jobs/{id})
export interface Job {
  job_id: string;
  status: JobStatus;
  message: string | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
  stats: JobStats | null;
}

// Transaction imported by a job (GET /api/jobs/{id}/transactions)
export interface JobTransaction {
  id: string;
  date: string;
  amount: number;
  currency: string;
  raw_merchant: string;
  memo: string | null;
  category: string | null;
  upi_transaction_id: string | null;
  direction: 'debit' | 'credit' | null;
}

export interface JobTransactionsResponse {
  total: number;
  items: JobTransaction[];
}

// Insights summary (GET /api/insights/summary)
export interface InsightsBreakdown {
  name: string;
  total: number;
  count: number;
}

export interface InsightsMonthly {
  month: string; // "YYYY-MM"
  spent: number;
  received: number;
}

export interface InsightsSummary {
  total_spent: number;
  total_received: number;
  net: number;
  txn_count: number;
  top_categories: InsightsBreakdown[];
  top_merchants: InsightsBreakdown[];
  monthly: InsightsMonthly[];
}

// AI narrative insights (GET /api/insights/ai)
export interface AIInsights {
  summary: string;
  highlights: string[];
  generated_at: string;
}

// Transaction row as returned by GET /api/transactions?page=&limit=
export interface TransactionListItem {
  id: string;
  date: string;
  amount: number;
  raw_merchant: string;
  memo: string | null;
  category_id: string | null;
  upi_transaction_id: string | null;
  direction: 'debit' | 'credit' | null;
  group_id: string | null;
}

export interface TransactionsPage {
  data: TransactionListItem[];
  total: number;
  page: number;
  limit: number;
}

// Clubbing / groups
export type GroupKind = 'manual' | 'auto';

// List item (GET /api/groups) and create response (POST /api/groups)
export interface Group {
  id: string;
  name: string;
  kind: GroupKind;
  created_at?: string;
  count: number;
  total: number;
}

// Member transaction of a group (GET /api/groups/{id})
export interface GroupTransaction {
  id: string;
  date: string;
  amount: number;
  raw_merchant: string;
  memo: string | null;
  upi_transaction_id: string | null;
  direction: 'debit' | 'credit' | null;
  category: string | null;
}

// Group detail (GET /api/groups/{id})
export interface GroupDetail {
  id: string;
  name: string;
  kind: GroupKind;
  created_at: string;
  count: number;
  total: number;
  transactions: GroupTransaction[];
}

// Auto-club response (POST /api/groups/auto)
export interface AutoClubResponse {
  status: string;
  groups_created: number;
  transactions_clubbed: number;
  groups: { id: string; name: string; count: number; total: number }[];
  message: string;
}

// AI category suggestion (POST /api/transactions/{id}/suggest-category)
export interface CategorySuggestion {
  suggested_category: string;
  suggested_category_id: string | null;
  confidence: number;
  reasoning: string | null;
  source: 'ai' | 'rule';
}

// Bulk AI recategorization (POST /api/recategorize)
export interface RecategorizeResponse {
  status: string;
  candidates?: number;
  categorized_merchants?: number;
  updated_transactions?: number;
  message?: string;
  // Present when status === "skipped"
  reason?: string;
}
