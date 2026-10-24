import React from "react";
import { BookOpen, GraduationCap, FileText, Video, Award, Code, Database, Brain, Sparkles } from "lucide-react";

interface BookCoverProps {
  title: string;
  type?: string;
  department?: string | null;
  authors?: string[];
  size?: "sm" | "md" | "lg";
  className?: string;
}

// Preset color themes mapped cleanly across departments and resource types
const THEMES: Record<string, { bg: string; border: string; accent: string; badge: string }> = {
  CSE: {
    bg: "from-blue-900 via-indigo-950 to-slate-950",
    border: "border-cyan-500/30",
    accent: "text-cyan-400",
    badge: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
  },
  ECE: {
    bg: "from-violet-900 via-purple-950 to-slate-950",
    border: "border-purple-500/30",
    accent: "text-purple-400",
    badge: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  },
  MECH: {
    bg: "from-amber-900 via-stone-950 to-slate-950",
    border: "border-amber-500/30",
    accent: "text-amber-400",
    badge: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  },
  MATH: {
    bg: "from-emerald-900 via-teal-950 to-slate-950",
    border: "border-emerald-500/30",
    accent: "text-emerald-400",
    badge: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  },
  DEFAULT: {
    bg: "from-indigo-950 via-slate-900 to-slate-950",
    border: "border-indigo-500/30",
    accent: "text-indigo-400",
    badge: "bg-indigo-500/20 text-indigo-300 border-indigo-500/30",
  },
};

export default function BookCover({
  title,
  type = "book",
  department,
  authors = [],
  size = "md",
  className = "",
}: BookCoverProps) {
  const deptKey = department?.toUpperCase() || "DEFAULT";
  const theme = THEMES[deptKey] || THEMES.DEFAULT;

  const sizeClasses = {
    sm: "w-20 h-28 text-[9px] p-2",
    md: "w-32 h-44 text-[11px] p-3",
    lg: "w-44 h-60 text-xs p-4 sm:w-52 sm:h-72",
  }[size];

  const displayAuthor = authors && authors.length > 0 ? authors[0] : "Academic Faculty";

  return (
    <div
      className={`relative rounded-xl overflow-hidden shadow-2xl flex flex-col justify-between shrink-0 select-none border bg-gradient-to-br ${theme.bg} ${theme.border} ${sizeClasses} ${className}`}
      style={{
        boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.6), 0 8px 10px -6px rgba(0, 0, 0, 0.4)",
      }}
    >
      {/* Spine highlight overlay (simulates physical book spine depth) */}
      <div className="absolute inset-y-0 left-0 w-2.5 bg-gradient-to-r from-white/20 via-white/5 to-transparent pointer-events-none" />
      <div className="absolute inset-y-0 left-2.5 w-[1px] bg-black/40 pointer-events-none" />

      {/* Subtle corner sheen */}
      <div className="absolute top-0 right-0 w-16 h-16 bg-gradient-to-bl from-white/10 to-transparent pointer-events-none" />

      {/* Header: Dept Badge / Type Icon */}
      <div className="flex items-center justify-between z-10 pl-1">
        <span
          className={`px-1.5 py-0.5 rounded text-[8px] font-mono font-bold tracking-wider uppercase border ${theme.badge}`}
        >
          {department || "NEXORA"}
        </span>
        <Sparkles className={`w-3 h-3 ${theme.accent} opacity-80`} />
      </div>

      {/* Center: Title & Icon */}
      <div className="my-auto z-10 pl-1">
        <div className="mb-1 opacity-70">
          {type.includes("video") ? (
            <Video className="w-4 h-4 text-slate-300" />
          ) : type.includes("paper") || type.includes("journal") ? (
            <FileText className="w-4 h-4 text-slate-300" />
          ) : (
            <BookOpen className="w-4 h-4 text-slate-300" />
          )}
        </div>
        <h4 className="font-bold text-white leading-tight line-clamp-3 tracking-tight drop-shadow-sm">
          {title}
        </h4>
      </div>

      {/* Footer: Author / Brand */}
      <div className="z-10 pl-1 pt-1 border-t border-white/10 flex items-center justify-between">
        <span className="text-slate-300 font-medium truncate max-w-[80%] text-[8px] opacity-90">
          {displayAuthor}
        </span>
        <span className="text-[7px] font-mono text-slate-400 uppercase tracking-widest">
          EDN
        </span>
      </div>
    </div>
  );
}
