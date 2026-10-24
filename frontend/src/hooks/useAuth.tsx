"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { User, AuthResponse } from "@/types";
import { apiClient } from "@/lib/api";

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (tokens: AuthResponse["tokens"], user: User) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    try {
      const storedToken = localStorage.getItem("nexora_access_token");
      const storedUser = localStorage.getItem("nexora_user");
      if (storedToken && storedUser) {
        setToken(storedToken);
        setUser(JSON.parse(storedUser));
      }
    } catch {
      // ignore parsing error
    } finally {
      setLoading(false);
    }
  }, []);

  const login = (tokens: AuthResponse["tokens"], newUser: User) => {
    localStorage.setItem("nexora_access_token", tokens.access_token);
    localStorage.setItem("nexora_refresh_token", tokens.refresh_token);
    localStorage.setItem("nexora_user", JSON.stringify(newUser));
    setToken(tokens.access_token);
    setUser(newUser);
  };

  const logout = async () => {
    try {
      const refreshToken = localStorage.getItem("nexora_refresh_token");
      if (refreshToken) {
        await apiClient("/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      }
    } catch {
      // ignore
    } finally {
      localStorage.removeItem("nexora_access_token");
      localStorage.removeItem("nexora_refresh_token");
      localStorage.removeItem("nexora_user");
      setToken(null);
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
