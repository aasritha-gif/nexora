"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

type Theme = "dark" | "light";

function apply(theme: Theme) {
  document.documentElement.classList.toggle("light", theme === "light");
  document.documentElement.classList.toggle("dark", theme === "dark");
  localStorage.setItem("nexora-theme", theme);
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const saved: Theme = localStorage.getItem("nexora-theme") === "light" ? "light" : "dark";
    setTheme(saved);
    apply(saved);
  }, []);

  const select = (next: Theme) => {
    setTheme(next);
    apply(next);
  };

  const btn = (active: boolean) =>
    `p-1.5 rounded-md transition-colors ${
      active ? "bg-indigo-brand/30 text-indigo-accent" : "text-slate-400 hover:text-white"
    }`;

  return (
    <div
      className="flex items-center rounded-lg border border-white/10 bg-midnight-800/60 p-0.5"
      role="group"
      aria-label="Color theme"
    >
      <button
        type="button"
        onClick={() => select("light")}
        title="Light mode"
        aria-label="Light mode"
        aria-pressed={theme === "light"}
        className={btn(theme === "light")}
      >
        <Sun className="w-4 h-4" />
      </button>
      <button
        type="button"
        onClick={() => select("dark")}
        title="Dark mode"
        aria-label="Dark mode"
        aria-pressed={theme === "dark"}
        className={btn(theme === "dark")}
      >
        <Moon className="w-4 h-4" />
      </button>
    </div>
  );
}
