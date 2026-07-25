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

// Event / "Case study" (POST/GET /api/events)
// A named grouping of scattered transactions from one life event. Many-to-many:
// a transaction can belong to an event AND keep its own category/group.
export interface Event {
  id: string;
  user_id?: string;
  name: string;
  description?: string | null;
  summary?: string | null;
  total_amount?: number | null;
  currency?: string | null;
  created_at?: string | null;
}

// Member transaction of an event (GET /api/events/{id}). Unlike group members,
// each keeps its own category via the joined `categories` row.
export interface EventTransaction {
  id: string;
  date: string;
  amount: number;
  raw_merchant: string;
  memo: string | null;
  category_id: string | null;
  categories: { name: string } | null;
}

// Event detail (GET /api/events/{id})
export interface EventDetail extends Event {
  transactions: EventTransaction[];
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

// Triage: a merchant still needing a category (GET /api/transactions/triage)
export interface TriageSuggestion {
  category: string;
  category_id: string;
  confidence: number;
}

export interface TriageMerchant {
  raw_merchant: string;
  count: number;
  total: number; // absolute ₹ magnitude, for ranking
  net: number; // signed: positive = spent, negative = received
  sample_memo: string | null;
  suggestion: TriageSuggestion | null;
}

export interface TriageResponse {
  data: TriageMerchant[];
  merchants: number;
  total_amount: number;
}

// Chat observability (GET /api/chat/traces)
export interface ChatTraceStep {
  tool: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  args: Record<string, any>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  result: any;
}

export interface ChatTrace {
  id: string;
  created_at: string;
  question: string;
  steps: ChatTraceStep[] | null;
  answer: string;
  source: 'agent' | 'deterministic' | 'error-fallback';
  action_taken: boolean;
  error: string | null;
  duration_ms: number | null;
}

// Split-expense / settle-up cluster (GET /api/insights/contributions)
// A burst of small inbound transfers that offset a big spend (you paid ₹800 for a
// game, 11 friends sent ~₹62 back → net ₹50).
export interface Contribution {
  date: string;
  count: number;
  total_received: number;
  avg_amount: number;
  transaction_ids: string[];
  source_debit: { id: string; amount: number; merchant: string } | null;
  net_cost: number | null;
}

export interface ContributionsResponse {
  data: Contribution[];
  count: number;
  total_recovered: number;
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
