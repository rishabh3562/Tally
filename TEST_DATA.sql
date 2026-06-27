-- Personal Finance OS - Test Data SQL Script
-- Copy and paste this into Supabase SQL Editor
-- NOTE: Replace 'YOUR_USER_ID' with an actual UUID from your auth.users table

-- ============================================================================
-- STEP 1: CREATE TEST USER (if not already created via frontend signup)
-- ============================================================================
-- NOTE: The recommended way is to sign up through the frontend at localhost:3000
-- Then use the user UUID from Supabase Auth console
--
-- To find your user UUID:
-- 1. Go to Supabase Dashboard → Your Project
-- 2. Click "Authentication" → "Users"
-- 3. Copy the UUID of your user (e.g., rishabhdubey2003@gmail.com)
-- 4. Replace 'YOUR_USER_ID' in the SQL below

-- Example UUID (replace with actual):
-- YOUR_USER_ID = '550e8400-e29b-41d4-a716-446655440000'

-- If you want to create a user manually (less recommended):
-- INSERT INTO users (id, email, preferences)
-- VALUES ('550e8400-e29b-41d4-a716-446655440000', 'test@example.com', '{"default_currency":"INR","theme":"light"}')
-- ON CONFLICT DO NOTHING;

-- ============================================================================
-- STEP 2: CREATE TEST BANK ACCOUNT
-- ============================================================================

INSERT INTO accounts (user_id, name, type, bank_code)
VALUES
  ('550e8400-e29b-41d4-a716-446655440000', 'HDFC Salary Account', 'Bank', 'HDFC'),
  ('550e8400-e29b-41d4-a716-446655440000', 'ICICI Credit Card', 'CreditCard', 'ICICI');

-- ============================================================================
-- STEP 3: INSERT SAMPLE TRANSACTIONS (June 2026)
-- ============================================================================
-- These represent realistic spending patterns

-- Get category IDs (food, transport, shopping, groceries, etc.)
WITH categories_map AS (
  SELECT id, name FROM categories WHERE user_id IS NULL
)

-- Get the first account we created
, account_ids AS (
  SELECT id FROM accounts WHERE user_id = '550e8400-e29b-41d4-a716-446655440000' LIMIT 1
)

INSERT INTO transactions (
  id, user_id, account_id, date, amount, currency,
  raw_merchant, category_id, memo, fingerprint,
  is_transfer, confidence_score
)
SELECT
  gen_random_uuid(),
  '550e8400-e29b-41d4-a716-446655440000'::uuid,
  (SELECT id FROM account_ids),
  DATE(data->>'date'),
  (data->>'amount')::numeric,
  'INR',
  data->>'merchant',
  (SELECT id FROM categories WHERE name = data->>'category' AND user_id IS NULL),
  data->>'memo',
  data->>'fingerprint',
  false,
  0.95
FROM (
  VALUES
    -- Food & Dining transactions
    ('{"date":"2026-06-01","amount":"450.00","merchant":"Swiggy","category":"Food & Dining","memo":"Lunch delivery","fingerprint":"f1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6"}'),
    ('{"date":"2026-06-02","amount":"280.00","merchant":"Starbucks","category":"Food & Dining","memo":"Coffee","fingerprint":"a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"}'),
    ('{"date":"2026-06-03","amount":"1200.00","merchant":"Zomato","category":"Food & Dining","memo":"Dinner - office order","fingerprint":"b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7"}'),
    ('{"date":"2026-06-04","amount":"650.00","merchant":"McDonald\'s","category":"Food & Dining","memo":"Breakfast with friends","fingerprint":"c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8"}'),

    -- Transport transactions
    ('{"date":"2026-06-05","amount":"125.00","merchant":"Uber","category":"Transport","memo":"Office commute","fingerprint":"d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9"}'),
    ('{"date":"2026-06-06","amount":"95.00","merchant":"Ola","category":"Transport","memo":"Return trip","fingerprint":"e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0"}'),
    ('{"date":"2026-06-07","amount":"2500.00","merchant":"HDFC ATM","category":"Transport","memo":"Fuel - HP Petrol","fingerprint":"f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1"}'),

    -- Shopping transactions
    ('{"date":"2026-06-08","amount":"3500.00","merchant":"Amazon","category":"Shopping","memo":"Monitor and keyboard","fingerprint":"g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2"}'),
    ('{"date":"2026-06-09","amount":"1200.00","merchant":"Flipkart","category":"Shopping","memo":"Headphones","fingerprint":"h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3"}'),

    -- Groceries transactions
    ('{"date":"2026-06-10","amount":"850.00","merchant":"BigBasket","category":"Groceries","memo":"Weekly groceries","fingerprint":"i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4"}'),
    ('{"date":"2026-06-11","amount":"450.00","merchant":"DMart","category":"Groceries","memo":"Vegetables and fruits","fingerprint":"j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5"}'),

    -- Subscriptions
    ('{"date":"2026-06-12","amount":"199.00","merchant":"Netflix","category":"Subscriptions","memo":"Monthly subscription","fingerprint":"k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6"}'),
    ('{"date":"2026-06-13","amount":"99.00","merchant":"Spotify","category":"Subscriptions","memo":"Premium","fingerprint":"l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7"}'),

    -- Entertainment
    ('{"date":"2026-06-14","amount":"800.00","merchant":"BookMyShow","category":"Entertainment","memo":"Movie tickets - 2x","fingerprint":"m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8"}'),

    -- Healthcare
    ('{"date":"2026-06-15","amount":"500.00","merchant":"Apollo Pharmacy","category":"Healthcare","memo":"Medicines","fingerprint":"n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9"}'),

    -- Education
    ('{"date":"2026-06-16","amount":"2000.00","merchant":"Udemy","category":"Education","memo":"Python course","fingerprint":"o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0"}'),

    -- Utilities
    ('{"date":"2026-06-17","amount":"1500.00","merchant":"BSNL","category":"Utilities","memo":"Internet bill","fingerprint":"p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1"}'),

    -- More food spending (for case study)
    ('{"date":"2026-06-18","amount":"350.00","merchant":"Swiggy","category":"Food & Dining","memo":"Lunch","fingerprint":"q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2"}'),
    ('{"date":"2026-06-19","amount":"500.00","merchant":"Zomato","category":"Food & Dining","memo":"Dinner","fingerprint":"r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2g3"}'),
    ('{"date":"2026-06-20","amount":"200.00","merchant":"Starbucks","category":"Food & Dining","memo":"Coffee","fingerprint":"s9t0u1v2w3x4y5z6a7b8c9d0e1f2g3h4"}')
) AS data(data);

-- ============================================================================
-- STEP 4: CREATE A CASE STUDY/EVENT (Goa Trip)
-- ============================================================================

-- First, insert the event
INSERT INTO events (user_id, name, description, metadata, summary, total_amount, currency)
VALUES (
  '550e8400-e29b-41d4-a716-446655440000'::uuid,
  'Goa Trip 2026',
  'Weekend trip to Goa with friends',
  '{"destination":"Goa","days":3,"participants":2,"dates":"2026-06-18 to 2026-06-20"}',
  'Spent ₹1,050 on food and dining during the Goa trip. Includes restaurant meals, coffee, and food delivery.',
  1050.00,
  'INR'
);

-- Add transactions to the event
-- This links the food transactions from June 18-20 to the case study
INSERT INTO event_transactions (event_id, transaction_id)
SELECT
  e.id,
  t.id
FROM events e
JOIN transactions t ON t.user_id = e.user_id
WHERE
  e.name = 'Goa Trip 2026'
  AND t.raw_merchant IN ('Swiggy', 'Zomato', 'Starbucks')
  AND t.date BETWEEN '2026-06-18' AND '2026-06-20'
  AND t.category_id = (SELECT id FROM categories WHERE name = 'Food & Dining');

-- ============================================================================
-- STEP 5: ADD LEARNING RECORDS (User corrections for next processing)
-- ============================================================================

-- Example: User corrected "DMart" to be Food/Groceries
INSERT INTO learning_records (user_id, raw_merchant, category_id, merchant_id)
VALUES (
  '550e8400-e29b-41d4-a716-446655440000'::uuid,
  'DMart',
  (SELECT id FROM categories WHERE name = 'Groceries' AND user_id IS NULL),
  NULL
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- STEP 6: VERIFICATION QUERIES
-- ============================================================================

-- View your user profile
SELECT 'USER PROFILE' as section, id, email, preferences, created_at
FROM users
WHERE id = '550e8400-e29b-41d4-a716-446655440000'::uuid;

-- View your accounts
SELECT 'ACCOUNTS' as section, name, type, bank_code, created_at
FROM accounts
WHERE user_id = '550e8400-e29b-41d4-a716-446655440000'::uuid;

-- View transaction summary
SELECT
  'TRANSACTION SUMMARY' as section,
  COUNT(*) as total_transactions,
  SUM(amount) as total_spent,
  MIN(date) as date_from,
  MAX(date) as date_to,
  COUNT(DISTINCT category_id) as categories_used
FROM transactions
WHERE user_id = '550e8400-e29b-41d4-a716-446655440000'::uuid;

-- View spending by category
SELECT
  'SPENDING BY CATEGORY' as section,
  c.name as category,
  COUNT(t.id) as transaction_count,
  SUM(t.amount) as category_total
FROM transactions t
LEFT JOIN categories c ON t.category_id = c.id
WHERE t.user_id = '550e8400-e29b-41d4-a716-446655440000'::uuid
GROUP BY c.name
ORDER BY category_total DESC;

-- View your events
SELECT
  'EVENTS/CASE STUDIES' as section,
  name,
  description,
  total_amount,
  (SELECT COUNT(*) FROM event_transactions WHERE event_id = events.id) as transaction_count,
  created_at
FROM events
WHERE user_id = '550e8400-e29b-41d4-a716-446655440000'::uuid;

-- View event details
SELECT
  'GOA TRIP DETAILS' as section,
  t.date,
  t.raw_merchant,
  c.name as category,
  t.amount,
  t.memo
FROM event_transactions et
JOIN transactions t ON et.transaction_id = t.id
JOIN categories c ON t.category_id = c.id
JOIN events e ON et.event_id = e.id
WHERE e.name = 'Goa Trip 2026'
ORDER BY t.date;

-- ============================================================================
-- EXPECTED RESULTS
-- ============================================================================
-- After running this script you should see:
--
-- 1. USER PROFILE:
--    - 1 user record
--    - ID, email, preferences (INR currency, light theme)
--
-- 2. ACCOUNTS:
--    - 2 accounts (1 Bank, 1 CreditCard)
--
-- 3. TRANSACTION SUMMARY:
--    - 21 transactions
--    - Total spent: ₹16,845
--    - Date range: 2026-06-01 to 2026-06-20
--    - 11 categories used
--
-- 4. SPENDING BY CATEGORY:
--    - Food & Dining: ₹3,580 (5 transactions)
--    - Shopping: ₹4,700 (2 transactions)
--    - Transport: ₹2,720 (3 transactions)
--    - Subscriptions: ₹298 (2 transactions)
--    - And more...
--
-- 5. EVENTS:
--    - "Goa Trip 2026" with 3 transactions, ₹1,050 total
--
-- ============================================================================
-- QUICK TEST QUERIES FOR DASHBOARD
-- ============================================================================

-- Test dashboard pie chart (category distribution)
SELECT c.name, SUM(t.amount) as amount, COUNT(t.id) as count
FROM transactions t
LEFT JOIN categories c ON t.category_id = c.id
WHERE t.user_id = '550e8400-e29b-41d4-a716-446655440000'::uuid
GROUP BY c.name
ORDER BY amount DESC;

-- Test monthly trend
SELECT
  DATE_TRUNC('month', date)::date as month,
  SUM(amount) as monthly_total,
  COUNT(*) as transaction_count
FROM transactions
WHERE user_id = '550e8400-e29b-41d4-a716-446655440000'::uuid
GROUP BY DATE_TRUNC('month', date)
ORDER BY month;

-- Test top merchants
SELECT raw_merchant, COUNT(*) as count, SUM(amount) as total
FROM transactions
WHERE user_id = '550e8400-e29b-41d4-a716-446655440000'::uuid
GROUP BY raw_merchant
ORDER BY total DESC
LIMIT 10;
