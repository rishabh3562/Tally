"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode, useEffect, useState, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";
import type { User } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import apiClient from "@/lib/api";
import Header from "@/components/common/Header";
import Sidebar from "@/components/common/Sidebar";

const queryClient = new QueryClient();

// Routes that render without the auth gate or app chrome (login/signup live here).
const PUBLIC_PREFIXES = ["/auth"];

export default function ClientLayout({
  children,
}: {
  children: ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const isPublicRoute = PUBLIC_PREFIXES.some((p) => pathname?.startsWith(p));

  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  // Guards the one-time backend validation from running twice (React Strict Mode
  // remounts the effect, but refs persist across the remount).
  const didValidate = useRef(false);

  useEffect(() => {
    // Public routes don't need the auth gate — don't subscribe or redirect.
    if (isPublicRoute) {
      setIsLoading(false);
      return;
    }

    let active = true;

    // A single subscription handles INITIAL_SESSION plus every later change.
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (event, session) => {
      if (!active) return;

      // No session (initial load with nothing stored, or after sign-out) -> login.
      if (!session) {
        setUser(null);
        setIsLoading(false);
        if (event === "INITIAL_SESSION" || event === "SIGNED_OUT") {
          router.replace("/auth/login");
        }
        return;
      }

      // First resolution with a session: validate against the backend exactly once.
      if (event === "INITIAL_SESSION") {
        if (didValidate.current) {
          setUser(session.user);
          setIsLoading(false);
          return;
        }
        didValidate.current = true;

        try {
          await apiClient.get("/api/users/me");
          if (!active) return;
          setUser(session.user);
        } catch (error: any) {
          if (!active) return;
          if (error.response?.status === 401) {
            // Token was rejected. The api interceptor already triggers a single
            // sign-out, whose SIGNED_OUT event drives the redirect below — so here
            // we only clear local state and avoid firing a competing redirect.
            setUser(null);
            setIsLoading(false);
            return;
          }
          // Non-auth failure (network / 5xx / 404): keep the user signed in and
          // let individual pages surface their own errors.
          setUser(session.user);
        }
        setIsLoading(false);
        return;
      }

      // SIGNED_IN / TOKEN_REFRESHED / USER_UPDATED — session is valid, load the app.
      setUser(session.user);
      setIsLoading(false);
    });

    return () => {
      active = false;
      subscription?.unsubscribe();
    };
  }, [isPublicRoute, router]);

  // Login / signup: render without the auth gate or app chrome.
  if (isPublicRoute) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

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

  // No user on a protected route: a redirect to /auth/login is in flight.
  // Render nothing so the app chrome never flashes.
  if (!user) {
    return null;
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
