"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api";
import { AuthResponse } from "@/types";
import { Lock, Mail, AlertCircle, ArrowRight } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await apiClient<AuthResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          identifier: identifier.trim(),
          password,
          remember_me: rememberMe,
        }),
      });

      login(res.tokens, res.user);
      router.push("/explore");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to sign in. Please verify your credentials.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-8rem)] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md glass-panel rounded-2xl p-8 border border-white/10 glow-indigo">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-indigo-brand to-violet-brand flex items-center justify-center mx-auto mb-3 text-white font-mono font-bold text-xl shadow-lg shadow-indigo-brand/20">
            N
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Sign In to NEXORA</h1>
          <p className="text-xs text-slate-400 mt-1">Access your intelligent university resource universe</p>
        </div>

        {error && (
          <div className="mb-6 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Email or Student ID
            </label>
            <div className="relative">
              <input
                type="text"
                required
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="student@university.edu or STU-1029"
                className="w-full px-3.5 py-2.5 rounded-xl bg-midnight-900 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-brand transition-colors"
              />
              <Mail className="w-4 h-4 text-slate-500 absolute right-3.5 top-3" />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-medium text-slate-300">Password</label>
              <Link href="/forgot-password" className="text-xs text-indigo-accent hover:underline">
                Forgot?
              </Link>
            </div>
            <div className="relative">
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full px-3.5 py-2.5 rounded-xl bg-midnight-900 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-brand transition-colors"
              />
              <Lock className="w-4 h-4 text-slate-500 absolute right-3.5 top-3" />
            </div>
          </div>

          <div className="flex items-center">
            <input
              id="remember_me"
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="w-4 h-4 rounded bg-midnight-900 border-white/10 text-indigo-brand focus:ring-indigo-brand"
            />
            <label htmlFor="remember_me" className="ml-2 block text-xs text-slate-300 cursor-pointer">
              Remember me on this device
            </label>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-indigo-brand to-violet-brand hover:from-indigo-accent hover:to-violet-glow text-white font-semibold text-sm shadow-md transition-all flex items-center justify-center gap-2 mt-2 disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign In"}
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        <p className="text-center text-xs text-slate-400 mt-6">
          New to NEXORA?{" "}
          <Link href="/register" className="text-indigo-accent font-medium hover:underline">
            Register your student account
          </Link>
        </p>
      </div>
    </div>
  );
}
