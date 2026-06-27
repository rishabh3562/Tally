# Testing Guide - Personal Finance OS

## Quick Start: Create Test Data

This guide walks you through creating a test user and populating sample data in Supabase.

## Step 1: Create a Real User (via Frontend)

1. Start the frontend:
   ```bash
   cd frontend
   npm run dev
   # Opens http://localhost:3000
   ```

2. Sign up at the login page:
   - Email: `rishabhdubey2003@gmail.com` (or any test email)
   - Password: Any password you choose

3. You'll be redirected to `/dashboard` (empty for now)

## Step 2: Get Your User UUID

1. Go to [Supabase Dashboard](https://app.supabase.com)
2. Select your project
3. Navigate to **Authentication** → **Users**
4. Find the user you just created (should be at the top)
5. Copy the UUID (it looks like: `550e8400-e29b-41d4-a716-446655440000`)

## Step 3: Populate Test Data

1. Go to Supabase SQL Editor
2. Open the file: `TEST_DATA.sql` (in project root)
3. **IMPORTANT**: Replace all instances of `550e8400-e29b-41d4-a716-446655440000` with YOUR user UUID
   - Find & Replace in your editor is fastest
   - Or in Supabase SQL Editor, use Ctrl+H (Find & Replace)

4. Copy the entire SQL script
5. Paste into Supabase SQL Editor
6. Click **Run** (or press Ctrl+Enter)

## Expected Results

After running the script, you should have:

### User Profile
```
Email: rishabhdubey2003@gmail.com
Currency: INR
Theme: Light
```

### Bank Accounts (2)
- HDFC Salary Account (Bank)
- ICICI Credit Card (CreditCard)

### Transactions (21)
- Date Range: June 1 - June 20, 2026
- Total Spending: ₹16,845
- Distribution:
  - Food & Dining: ₹3,580 (5 transactions)
  - Shopping: ₹4,700 (2 transactions)
  - Transport: ₹2,720 (3 transactions)
  - Groceries: ₹1,300 (2 transactions)
  - Subscriptions: ₹298 (2 transactions)
  - Entertainment: ₹800 (1 transaction)
  - Healthcare: ₹500 (1 transaction)
  - Education: ₹2,000 (1 transaction)
  - Utilities: ₹1,500 (1 transaction)

### Case Study (1)
- **Goa Trip 2026**
  - Duration: 3 days
  - Total: ₹1,050
  - Transactions: 3 (all food-related)
  - Location: Goa

## Step 4: Verify in Frontend

1. Refresh `http://localhost:3000/dashboard`
2. You should see:

### Dashboard Page
- ✅ Total Spent: ₹16,845
- ✅ Transaction Count: 21
- ✅ Top Category: Shopping (₹4,700)
- ✅ Pie Chart showing category breakdown
- ✅ Bar Chart showing monthly trends
- ✅ Recent Transactions list

### Transactions Page
- ✅ Full list of 21 transactions
- ✅ Pagination controls (20 per page)
- ✅ Date range filters
- ✅ Category filters

### Events/Case Studies Page
- ✅ "Goa Trip 2026" event card
- ✅ Shows ₹1,050 spent
- ✅ Description: "Weekend trip to Goa with friends"

### Chat Page
Try asking:
- "How much did I spend on food?" → ₹3,580
- "What was my top spending category?" → Shopping (₹4,700)
- "Show me June spending" → ₹16,845 (all in June)
- "How much did the Goa trip cost?" → ₹1,050

## SQL Queries to Test Manually

Run these in Supabase SQL Editor to verify data:

### Get User Profile
```sql
SELECT * FROM users
WHERE id = 'YOUR_USER_ID'::uuid;
```

### Count Transactions
```sql
SELECT COUNT(*) as total_transactions,
       SUM(amount) as total_amount
FROM transactions
WHERE user_id = 'YOUR_USER_ID'::uuid;
```

### Spending by Category
```sql
SELECT c.name, SUM(t.amount) as total, COUNT(t.id) as count
FROM transactions t
LEFT JOIN categories c ON t.category_id = c.id
WHERE t.user_id = 'YOUR_USER_ID'::uuid
GROUP BY c.name
ORDER BY total DESC;
```

### Goa Trip Details
```sql
SELECT t.date, t.raw_merchant, c.name as category, t.amount, t.memo
FROM event_transactions et
JOIN transactions t ON et.transaction_id = t.id
JOIN categories c ON t.category_id = c.id
JOIN events e ON et.event_id = e.id
WHERE e.name = 'Goa Trip 2026'
  AND e.user_id = 'YOUR_USER_ID'::uuid;
```

## Testing Upload Feature (Optional)

To test the file upload pipeline:

1. Create a CSV file in this format:
   ```
   Date,Amount,Merchant,Description
   2026-07-01,250,Swiggy,Lunch delivery
   2026-07-02,1200,Amazon,Laptop stand
   2026-07-03,500,Starbucks,Coffee
   ```

2. Save as `test_statement.csv`

3. Go to Dashboard → Upload Statement

4. Select:
   - Account: HDFC Salary Account
   - Bank: HDFC
   - File: test_statement.csv

5. Upload and watch the processing

6. Go back to Dashboard and you should see the new transactions

## Troubleshooting

### "User not found" or "No data showing"
- Make sure you replaced the UUID correctly
- Verify in Supabase: Auth → Users (should show your user)
- Try running the test queries above

### "Foreign key constraint failed"
- The user UUID might not exist yet
- Create the user via frontend first (Step 1)

### "Transaction data not showing in dashboard"
- Refresh the page (Ctrl+Shift+R for hard refresh)
- Check Supabase SQL Editor → tables → transactions
- Verify the user_id matches

### "Categories showing as blank"
- The category lookup might need the category_id first
- Run the seed categories script if needed

## Clean Up Test Data

To delete all test data for this user:

```sql
-- DELETE ALL DATA FOR USER (WARNING: Cannot be undone)
DELETE FROM transactions WHERE user_id = 'YOUR_USER_ID'::uuid;
DELETE FROM accounts WHERE user_id = 'YOUR_USER_ID'::uuid;
DELETE FROM events WHERE user_id = 'YOUR_USER_ID'::uuid;
DELETE FROM learning_records WHERE user_id = 'YOUR_USER_ID'::uuid;
DELETE FROM notes WHERE user_id = 'YOUR_USER_ID'::uuid;
DELETE FROM users WHERE id = 'YOUR_USER_ID'::uuid;
```

## Testing the Agentic System

Once you have test data, you can test the new agent system:

### Via Frontend Upload
1. Create a CSV with transactions
2. Upload via Dashboard
3. Watch agents process it:
   - ParsingAgent: Extracts from CSV
   - ValidationAgent: Checks data quality
   - MerchantNormalizationAgent: Normalizes names
   - CategorizationAgent: Assigns categories
   - Transactions stored with confidence scores

### Via Chat
Ask the system:
- "How much did I spend this month?"
- "What's my top spending category?"
- "Show me food expenses"
- "How much was the Goa trip?"

The chat will:
1. Run SQL query to get data
2. Pass to AnalyticsAgent (Nemotron 3 Ultra)
3. Generate natural language response
4. Stream back to you

## Expected Files in Supabase

After setup, you should have:

**Tables with data:**
- ✅ users (1 record)
- ✅ accounts (2 records)
- ✅ transactions (21 records)
- ✅ categories (11 system categories)
- ✅ events (1 record - Goa Trip)
- ✅ event_transactions (3 records)

**Tables without data (yet):**
- processing_jobs (populated during uploads)
- chat_conversations (populated during chat)
- learning_records (populated by user corrections)
- notes (populated by AI summaries)

## Next Steps

1. ✅ Create test user (this guide)
2. ✅ Populate test data (this guide)
3. Verify in dashboard (should work now)
4. Test upload feature with your own CSV
5. Test chat with natural language queries
6. Test creating events manually
7. Test correcting transactions (learning)

## Tips

- The test data includes realistic 2026 June transactions
- Fingerprints are pre-generated (in real usage, system generates them)
- Confidence scores are 0.95 (very high - data is known good)
- Categories are pre-assigned (real uploads would categorize)
- Event is pre-created (real events created by user selecting transactions)

Everything is set up to test the full system end-to-end!
