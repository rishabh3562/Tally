/**
 * Application constants
 */

// API endpoints
export const API_ENDPOINTS = {
  UPLOAD: '/api/upload-statement',
  TRANSACTIONS: '/api/transactions',
  EVENTS: '/api/events',
  CHAT: '/api/chat',
  AUTH: '/api/auth',
};

// Categories
export const EXPENSE_CATEGORIES = [
  'Food & Dining',
  'Transport',
  'Entertainment',
  'Shopping',
  'Utilities',
  'Healthcare',
  'Education',
  'Travel',
  'Groceries',
  'Subscriptions',
  'Other',
];

// Banks supported
export const SUPPORTED_BANKS = [
  'HDFC',
  'ICICI',
  'SBI',
  'Axis',
  'Kotak',
  'IDFC First',
];

// File types
export const ALLOWED_FILE_TYPES = [
  'application/pdf',
  'text/csv',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
];

// Max file size (MB)
export const MAX_FILE_SIZE = 50;

// Pagination
export const DEFAULT_PAGE_SIZE = 50;

// Date formats
export const DATE_FORMAT = 'DD/MM/YYYY';
export const API_DATE_FORMAT = 'YYYY-MM-DD';
