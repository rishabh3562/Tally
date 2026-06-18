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
