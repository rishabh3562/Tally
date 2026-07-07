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
    let unsubscribe: (() => void) | null = null;

    // Listen for auth state changes - this handles INITIAL_SESSION + all changes
    const setupAuth = () => {
      const { data: { subscription } } = supabase.auth.onAuthStateChange(
        async (event, session) => {
          console.log(`🔔 Auth event: ${event}`, session ? "with session" : "no session");

          // INITIAL_SESSION fires on mount with the actual session state
          if (event === "INITIAL_SESSION") {
            if (!session) {
              console.log("⚠️ No session - redirecting to login");
              setIsLoading(false);
              router.push("/auth/login");
              return;
            }

            console.log(`✅ Session found for ${session.user?.email}`);

            // Validate token with backend
            try {
              console.log("🔐 Validating token with backend...");
              await apiClient.get("/api/users/me");
              console.log("✅ Backend validation successful");
              setUser(session.user);
            } catch (error: any) {
              if (error.response?.status === 401) {
                console.error("❌ CRITICAL: JWT signature mismatch!");
                console.error("   Action needed: Update SUPABASE_JWT_SECRET in backend/.env");
                console.error("   Get correct secret from: https://app.supabase.com → Settings → Auth → JWT Secret");
                await supabase.auth.signOut();
                router.push("/auth/login");
                setIsLoading(false);
                return;
              }
              // Other errors - continue anyway
              console.warn(`⚠️ Profile check warning (${error.response?.status}):`, error.message);
              setUser(session.user);
            }

            setIsLoading(false);
          }
          // Handle sign out
          else if (event === "SIGNED_OUT") {
            console.log("👋 User signed out");
            setUser(null);
            setIsLoading(false);
            router.push("/auth/login");
          }
          // Handle sign in (from login page)
          else if (event === "SIGNED_IN" && session) {
            console.log(`📝 User signed in: ${session.user?.email}`);
            setUser(session.user);
            setIsLoading(false);
          }
        }
      );

      unsubscribe = subscription?.unsubscribe || null;
    };

    setupAuth();

    return () => {
      unsubscribe?.();
    };
    // Empty dependency array - only run once on mount
  }, [router]);

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
