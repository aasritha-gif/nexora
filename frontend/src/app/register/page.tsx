"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api";
import { AuthResponse } from "@/types";
import { AlertCircle, ArrowRight, UserCheck } from "lucide-react";

interface DeptOption {
  code: string;
  name: string;
}

export default function RegisterPage() {
  const router = useRouter();
  const { login } = useAuth();

  const [name, setName] = useState("");
  const [studentId, setStudentId] = useState("");
  const [email, setEmail] = useState("");
  const [departmentCode, setDepartmentCode] = useState("");
  const [academicYear, setAcademicYear] = useState(1);
  const [semester, setSemester] = useState(1);
  const [password, setPassword] = useState("");

  const [departments, setDepartments] = useState<DeptOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Fetch valid department list from backend
    apiClient<DeptOption[]>("/auth/departments")
      .then((data) => {
        setDepartments(data);
        if (data.length > 0) setDepartmentCode(data[0].code);
      })
      .catch(() => {
        // Fallback default departments if API unavailable during boot
        const defaults = [
          { code: "CS", name: "Computer Science" },
          { code: "SE", name: "Software Engineering" },
          { code: "IT", name: "Information Technology" },
          { code: "ECE", name: "Electronics & Communication" },
        ];
        setDepartments(defaults);
        setDepartmentCode("CS");
      });
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await apiClient<AuthResponse>("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          student_id: studentId.trim(),
          email: email.trim(),
          department_code: departmentCode.toUpperCase(),
          academic_year: Number(academicYear),
          semester: Number(semester),
          password,
        }),
      });

      login(res.tokens, res.user);
      router.push("/explore");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Registration failed. Please check your details.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-8rem)] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-lg glass-panel rounded-2xl p-8 border border-white/10 glow-indigo">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-cyan-glow to-indigo-brand flex items-center justify-center mx-auto mb-3 text-white font-mono font-bold text-xl shadow-lg shadow-indigo-brand/20">
            N
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Create Student Account</h1>
          <p className="text-xs text-slate-400 mt-1">Join the NEXORA university academic knowledge ecosystem</p>
        </div>

        {error && (
          <div className="mb-6 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Full Name</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ada Lovelace"
              className="w-full px-3.5 py-2.5 rounded-xl bg-midnight-900 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-brand transition-colors"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Student ID</label>
              <input
                type="text"
                required
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
                placeholder="21BCE1029"
                className="w-full px-3.5 py-2.5 rounded-xl bg-midnight-900 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-brand transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">University Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ada@university.edu"
                className="w-full px-3.5 py-2.5 rounded-xl bg-midnight-900 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-brand transition-colors"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Department</label>
            <select
              value={departmentCode}
              onChange={(e) => setDepartmentCode(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-midnight-900 border border-white/10 text-white text-sm focus:outline-none focus:border-indigo-brand transition-colors"
            >
              {departments.map((d) => (
                <option key={d.code} value={d.code}>
                  {d.name} ({d.code})
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Academic Year</label>
              <select
                value={academicYear}
                onChange={(e) => setAcademicYear(Number(e.target.value))}
                className="w-full px-3.5 py-2.5 rounded-xl bg-midnight-900 border border-white/10 text-white text-sm focus:outline-none focus:border-indigo-brand transition-colors"
              >
                {[1, 2, 3, 4, 5, 6].map((y) => (
                  <option key={y} value={y}>
                    Year {y}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Semester</label>
              <select
                value={semester}
                onChange={(e) => setSemester(Number(e.target.value))}
                className="w-full px-3.5 py-2.5 rounded-xl bg-midnight-900 border border-white/10 text-white text-sm focus:outline-none focus:border-indigo-brand transition-colors"
              >
                {[1, 2, 3, 4, 5, 6, 7, 8].map((s) => (
                  <option key={s} value={s}>
                    Semester {s}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Password</label>
            <input
              type="password"
              required
              minLength={10}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Minimum 10 characters"
              className="w-full px-3.5 py-2.5 rounded-xl bg-midnight-900 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-brand transition-colors"
            />
            <p className="text-[11px] text-slate-500 mt-1">Must be at least 10 characters long</p>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-indigo-brand to-violet-brand hover:from-indigo-accent hover:to-violet-glow text-white font-semibold text-sm shadow-md transition-all flex items-center justify-center gap-2 mt-4 disabled:opacity-50"
          >
            {loading ? "Creating Account..." : "Register Account"}
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        <p className="text-center text-xs text-slate-400 mt-6">
          Already registered?{" "}
          <Link href="/login" className="text-indigo-accent font-medium hover:underline">
            Sign in here
          </Link>
        </p>
      </div>
    </div>
  );
}
