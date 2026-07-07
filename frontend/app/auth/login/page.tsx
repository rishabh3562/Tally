"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

type AuthMode = "login" | "signup";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [step, setStep] = useState<"email" | "auth" | "profile">("email");

  const validateEmail = (email: string) => {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
  };

  const validatePassword = (pwd: string) => {
    return pwd.length >= 8;
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    if (!validateEmail(email)) {
      setError("Please enter a valid email address");
      setLoading(false);
      return;
    }

    if (!password) {
      setError("Please enter your password");
      setLoading(false);
      return;
    }

    try {
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (signInError) {
        if (signInError.message.includes("Invalid login credentials")) {
          setError("❌ Email or password is incorrect");
        } else {
          setError(`❌ ${signInError.message}`);
        }
        setLoading(false);
        return;
      }

      setSuccess("✅ Logged in! Redirecting...");
      setTimeout(() => router.push("/dashboard"), 1000);
    } catch (err) {
      setError("❌ Login failed. Please try again.");
      console.error(err);
      setLoading(false);
    }
  };

  const handleSignUp = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);

    // Validation
    if (!validateEmail(email)) {
      setError("❌ Please enter a valid email address");
      setLoading(false);
      return;
    }

    if (!validatePassword(password)) {
      setError("❌ Password must be at least 8 characters long");
      setLoading(false);
      return;
    }

    if (password !== confirmPassword) {
      setError("❌ Passwords do not match");
      setLoading(false);
      return;
    }

    try {
      setStep("auth");
      setSuccess("📧 Creating account...");

      // Step 1: Create Supabase Auth user
      const { data, error: signUpError } = await supabase.auth.signUp({
        email,
        password,
      });

      if (signUpError) {
        if (signUpError.message.includes("already registered")) {
          setError("❌ This email is already registered. Please log in instead.");
        } else {
          setError(`❌ ${signUpError.message}`);
        }
        setLoading(false);
        setStep("email");
        return;
      }

      if (!data.user?.id) {
        setError("❌ Failed to create account. Please try again.");
        setLoading(false);
        setStep("email");
        return;
      }

      setSuccess("📧 Account created. Setting up profile...");
      setStep("profile");

      // Step 2: Get session token
      const { data: sessionData, error: sessionError } = await supabase.auth.getSession();
      if (sessionError || !sessionData.session?.access_token) {
        setError("❌ Failed to get session. Please try logging in.");
        setLoading(false);
        setStep("email");
        return;
      }

      // Step 3: Create user profile in database via backend
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${apiUrl}/api/users/signup`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          user_id: data.user.id,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to set up profile");
      }

      setSuccess("✅ All set! Welcome to Tally 🎉");
      setTimeout(() => {
        router.push("/dashboard");
      }, 1500);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      console.error("Signup error:", err);

      if (message.includes("not reachable") || message.includes("Failed to fetch")) {
        setError(
          "❌ Backend server is not running. Make sure to start it with: python -m app.main"
        );
      } else if (message.includes("Failed to set up profile")) {
        setError(
          `❌ Account created but profile setup failed. Error: ${message}. Try logging in.`
        );
      } else {
        setError(`❌ ${message}`);
      }
      setLoading(false);
      setStep("email");
    }
  };

  const isLoginMode = mode === "login";
  const passwordsMatch = password === confirmPassword;
  const isEmailValid = validateEmail(email);
  const isPasswordValid = validatePassword(password);
  const canSubmit = isEmailValid && isPasswordValid && (isLoginMode || passwordsMatch);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-5xl font-bold text-blue-600 mb-2">Tally</h1>
          <p className="text-gray-600 font-medium">Personal Finance OS</p>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-8 bg-gray-100 p-1 rounded-lg">
          <button
            onClick={() => {
              setMode("login");
              setError("");
              setSuccess("");
            }}
            className={`flex-1 py-2 rounded font-medium transition ${
              isLoginMode
                ? "bg-blue-600 text-white"
                : "bg-transparent text-gray-700 hover:text-gray-900"
            }`}
          >
            Sign In
          </button>
          <button
            onClick={() => {
              setMode("signup");
              setError("");
              setSuccess("");
            }}
            className={`flex-1 py-2 rounded font-medium transition ${
              !isLoginMode
                ? "bg-blue-600 text-white"
                : "bg-transparent text-gray-700 hover:text-gray-900"
            }`}
          >
            Create Account
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border-l-4 border-red-500 rounded text-red-700 text-sm font-medium">
            {error}
          </div>
        )}

        {/* Success Message */}
        {success && (
          <div className="mb-6 p-4 bg-green-50 border-l-4 border-green-500 rounded text-green-700 text-sm font-medium">
            {success}
          </div>
        )}

        {/* Form */}
        <form onSubmit={isLoginMode ? handleLogin : handleSignUp} className="space-y-4">
          {/* Email */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              disabled={loading}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 transition"
            />
            {email && !isEmailValid && (
              <p className="mt-1 text-xs text-red-600">Invalid email format</p>
            )}
          </div>

          {/* Password */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={isLoginMode ? "••••••••" : "At least 8 characters"}
              disabled={loading}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 transition"
            />
            {password && !isPasswordValid && (
              <p className="mt-1 text-xs text-red-600">Password must be at least 8 characters</p>
            )}
          </div>

          {/* Confirm Password (Signup Only) */}
          {!isLoginMode && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Confirm Password
              </label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm password"
                disabled={loading}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 transition"
              />
              {confirmPassword && !passwordsMatch && (
                <p className="mt-1 text-xs text-red-600">Passwords do not match</p>
              )}
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading || !canSubmit}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-bold py-3 rounded-lg transition mt-6"
          >
            {loading ? (
              <div className="flex items-center justify-center gap-2">
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                {step === "auth" && "Creating account..."}
                {step === "profile" && "Setting up profile..."}
                {step === "email" && "Processing..."}
              </div>
            ) : isLoginMode ? (
              "Sign In"
            ) : (
              "Create Account"
            )}
          </button>
        </form>

        {/* Footer */}
        <div className="mt-8 pt-6 border-t border-gray-200 text-center text-xs text-gray-600">
          <p>
            {isLoginMode ? "Don't have an account? " : "Already have an account? "}
            <button
              onClick={() => {
                setMode(isLoginMode ? "signup" : "login");
                setEmail("");
                setPassword("");
                setConfirmPassword("");
                setError("");
                setSuccess("");
              }}
              className="text-blue-600 font-medium hover:underline"
            >
              {isLoginMode ? "Sign up" : "Sign in"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
