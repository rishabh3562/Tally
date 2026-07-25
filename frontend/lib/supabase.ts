/**
 * Supabase client initialization
 */

import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Missing Supabase environment variables');
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    // Persist the session in localStorage across reloads.
    persistSession: true,
    // Refresh the access token in the background before it expires so API
    // calls don't 401 on an otherwise valid session.
    autoRefreshToken: true,
    // Handle the token that arrives in the URL after email confirmation / OAuth.
    detectSessionInUrl: true,
  },
});
