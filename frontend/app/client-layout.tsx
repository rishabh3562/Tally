"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";
import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import apiClient from "@/lib/api";
import Header from "@/components/common/Header";
import Sidebar from "@/components/common/Sidebar";

const queryClient = new QueryClient();

export default function ClientLayout({
  children,
}: {
  children: ReactNode;
}) {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState(null);
  const hasCheckedAuth = useRef(false);
  const isAuthenticating = useRef(false);

  useEffect(() => {
    // Prevent multiple simultaneous auth checks
    if (isAuthenticating.current || hasCheckedAuth.current) {
      return;
    }

    const checkAuth = async () => {
      isAuthenticating.current = true;

      try {
        console.log("🔍 Checking authentication status...");

        const {
          data: { user: currentUser, session },
        } = await supabase.auth.getSession();

        // No session = not logged in
        if (!session || !currentUser) {
          console.log("⚠️ No active session - redirecting to login");
          setIsLoading(false);
          hasCheckedAuth.current = true;
          router.push("/auth/login");
          return;
        }

        console.log(`✅ Session found for ${currentUser.email}`);

        // Verify backend can validate our token
        try {
          console.log("🔐 Validating token with backend...");
          await apiClient.get("/api/users/me");
          console.log("✅ Backend validation successful");
        } catch (error: any) {
          if (error.response?.status === 401) {
            console.error("❌ CRITICAL: JWT signature mismatch!");
            console.error("   Action needed: Update SUPABASE_JWT_SECRET in backend/.env");
            console.error("   Get correct secret from: https://app.supabase.com → Settings → Auth → JWT Secret");

            // Sign out to clear invalid session
            await supabase.auth.signOut();
            setIsLoading(false);
            hasCheckedAuth.current = true;
            router.push("/auth/login");
            return;
          }

          // Other errors: log but continue
          console.warn(`⚠️ Backend check failed (${error.response?.status}):`, error.message);
        }

        // Auth successful - set user
        setUser(currentUser);
        console.log("✅ Auth check complete - user authenticated");
      } catch (error) {
        console.error("❌ Unexpected auth error:", error);
        router.push("/auth/login");
      } finally {
        setIsLoading(false);
        hasCheckedAuth.current = true;
        isAuthenticating.current = false;
      }
    };

    checkAuth();

    // Listen for auth state changes (e.g., logout from another tab)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        console.log(`🔔 Auth event: ${event}`, session ? "with session" : "no session");

        if (event === "SIGNED_OUT" || !session) {
          console.log("👋 User signed out");
          setUser(null);
          setIsLoading(false);
          router.push("/auth/login");
        } else if (event === "SIGNED_IN" && session) {
          console.log(`📝 User signed in: ${session.user?.email}`);
          // Don't re-check immediately - just update user
          setUser(session.user);
          setIsLoading(false);
        }
      }
    );

    return () => {
      subscription?.unsubscribe();
    };
    // Empty dependency array - only run once on mount
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">Tally</h1>
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      <div className="flex h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header user={user} />
          <main className="flex-1 overflow-auto bg-gray-50 p-6">
            {children}
          </main>
        </div>
      </div>
    </QueryClientProvider>
  );
}
