/**
 * API client for backend communication with Supabase auth integration
 */

import axios, { AxiosInstance } from 'axios';
import { supabase } from './supabase';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const apiClient: AxiosInstance = axios.create({
  baseURL: API_URL,
  timeout: parseInt(process.env.NEXT_PUBLIC_API_TIMEOUT || '30000'),
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add Supabase JWT token to requests
apiClient.interceptors.request.use(async (config) => {
  try {
    const { data: { session } } = await supabase.auth.getSession();

    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`;
    }
  } catch (error) {
    console.error(`❌ Failed to get auth token for ${config.url}:`, error);
  }
  return config;
});

// Latches the first 401 so N simultaneous failures (users/me + transactions +
// accounts) don't each trigger a redirect. The auth layer (client-layout) owns
// navigation: signing out emits SIGNED_OUT, which redirects exactly once.
let isHandlingAuthFailure = false;

// Re-arm the latch on a fresh sign-in so a later token rejection (e.g. after
// re-logging in within the same tab) is handled again.
supabase.auth.onAuthStateChange((event) => {
  if (event === 'SIGNED_IN') {
    isHandlingAuthFailure = false;
  }
});

// Handle errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const url = error.config?.url;

    if (status === 401) {
      console.error(`❌ 401 Unauthorized on ${url} — session rejected by backend.`);

      const onLoginPage =
        typeof window !== 'undefined' &&
        window.location.pathname.startsWith('/auth/login');

      // Redirect at most once, and never while already on the login page.
      if (typeof window !== 'undefined' && !isHandlingAuthFailure && !onLoginPage) {
        isHandlingAuthFailure = true;
        // Clear the rejected session. client-layout listens for SIGNED_OUT and
        // performs the single redirect to /auth/login, so we don't hard-redirect
        // here and fight it. Only fall back to a hard redirect if sign-out fails.
        supabase.auth
          .signOut()
          .catch((e) => {
            console.error('Failed to sign out after 401:', e);
            window.location.href = '/auth/login';
          });
      }
    } else if (status === 403) {
      console.error(`❌ 403 Forbidden on ${url}`);
    } else if (status === 404) {
      console.error(`⚠️ 404 Not Found on ${url}`);
    } else if (status >= 500) {
      console.error(`❌ Server Error ${status} on ${url}`);
    }

    throw error;
  }
);

export default apiClient;
