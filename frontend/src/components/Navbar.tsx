"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import ThemeToggle from "@/components/ThemeToggle";
import {
  BookOpen,
  Search,
  Compass,
  Bookmark,
  Shield,
  LogOut,
  User as UserIcon,
  Sparkles,
} from "lucide-react";

export default function Navbar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const navLinks = [
    { href: "/search", label: "Search", icon: Search },
    { href: "/explore", label: "Universe", icon: Compass },
    { href: "/research", label: "Research", icon: Sparkles },
    { href: "/library", label: "Library", icon: Bookmark, authRequired: true },
    { href: "/admin", label: "Admin", icon: Shield, adminRequired: true },
  ];

  return (
    <header className="sticky top-0 z-50 glass-panel border-b border-white/10 bg-midnight-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand Logo */}
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-brand via-violet-brand to-cyan-glow flex items-center justify-center shadow-lg shadow-indigo-brand/20 group-hover:scale-105 transition-transform duration-300">
            <span className="font-bold text-xl text-white tracking-wider font-mono">N</span>
          </div>
          <div>
            <span className="text-xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-indigo-accent bg-clip-text text-transparent">
              NEXORA
            </span>
            <span className="hidden sm:inline-block ml-2 text-xs font-medium text-cyan-accent/80 tracking-widest uppercase">
              Universe
            </span>
          </div>
        </Link>

        {/* Navigation links */}
        <nav className="hidden md:flex items-center gap-1">
          {navLinks.map((link) => {
            if (link.authRequired && !user) return null;
            if (link.adminRequired && user?.role !== "admin") return null;

            const Icon = link.icon;
            const isActive = pathname.startsWith(link.href);

            return (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-indigo-brand/15 text-indigo-accent border border-indigo-brand/30"
                    : "text-slate-300 hover:text-white hover:bg-white/5"
                }`}
              >
                <Icon className="w-4 h-4" />
                {link.label}
              </Link>
            );
          })}
        </nav>

        {/* User profile / Auth buttons */}
        <div className="flex items-center gap-3">
          <ThemeToggle />
          {user ? (
            <div className="flex items-center gap-3">
              <Link
                href="/profile"
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-midnight-800 border border-white/10 hover:border-indigo-brand/40 transition-colors text-sm"
              >
                <UserIcon className="w-4 h-4 text-cyan-accent" />
                <span className="max-w-[120px] truncate font-medium text-slate-200">
                  {user.name}
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-brand/20 text-indigo-accent uppercase font-mono">
                  {user.role}
                </span>
              </Link>
              <button
                onClick={logout}
                title="Sign out"
                className="p-2 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                href="/login"
                className="px-4 py-2 rounded-lg text-sm font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-colors"
              >
                Sign In
              </Link>
              <Link
                href="/register"
                className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-gradient-to-r from-indigo-brand to-violet-brand hover:from-indigo-accent hover:to-violet-glow shadow-md shadow-indigo-brand/25 transition-all"
              >
                Get Started
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
