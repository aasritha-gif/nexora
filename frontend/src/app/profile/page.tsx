"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { User, Mail, GraduationCap, Calendar, Shield, Hash, LogOut } from "lucide-react";

export default function ProfilePage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading]);

  if (loading || !user) {
    return (
      <div className="py-24 text-center text-slate-400">
        <p className="text-sm">Loading student profile...</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="glass-panel rounded-2xl p-8 border border-white/10 mb-8 relative">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-indigo-brand via-violet-brand to-cyan-glow flex items-center justify-center font-bold text-2xl text-white shadow-lg shadow-indigo-brand/20">
              {user.name.charAt(0).toUpperCase()}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl sm:text-2xl font-bold text-white">{user.name}</h1>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-indigo-brand/20 text-indigo-accent border border-indigo-brand/30">
                  {user.role}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1 flex items-center gap-1.5">
                <Mail className="w-3.5 h-3.5" />
                {user.email}
              </p>
            </div>
          </div>

          <button
            onClick={() => {
              logout();
              router.push("/login");
            }}
            className="self-start sm:self-auto px-4 py-2 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 text-xs font-semibold flex items-center gap-2 transition-colors border border-red-500/20"
          >
            <LogOut className="w-3.5 h-3.5" />
            Sign Out
          </button>
        </div>
      </div>

      {/* Academic Information Card */}
      <div className="glass-panel rounded-2xl p-6 border border-white/10">
        <h2 className="text-base font-bold text-white mb-4 flex items-center gap-2">
          <GraduationCap className="w-4 h-4 text-cyan-accent" />
          Academic Information
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 text-xs">
          <div>
            <span className="text-slate-400 block mb-1">Student ID</span>
            <span className="font-mono text-slate-200 text-sm font-semibold">
              {user.student_id || "N/A"}
            </span>
          </div>

          <div>
            <span className="text-slate-400 block mb-1">Department</span>
            <span className="text-slate-200 text-sm font-semibold">
              {user.department_code || "General"}
            </span>
          </div>

          <div>
            <span className="text-slate-400 block mb-1">Academic Year</span>
            <span className="text-slate-200 text-sm font-semibold">
              {user.academic_year ? `Year ${user.academic_year}` : "N/A"}
            </span>
          </div>

          <div>
            <span className="text-slate-400 block mb-1">Semester</span>
            <span className="text-slate-200 text-sm font-semibold">
              {user.semester ? `Semester ${user.semester}` : "N/A"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
