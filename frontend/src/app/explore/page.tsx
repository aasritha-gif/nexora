"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api";
import { Department } from "@/types";
import { Compass, BookOpen, Layers, ArrowRight, Loader2 } from "lucide-react";

export default function ExplorePage() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient<{ code: string; name: string }[]>("/auth/departments")
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setDepartments(data.map((d) => ({
            code: d.code,
            name: d.name,
            description: `Faculty of ${d.name} resources, lecture notes, and research.`,
          })));
        } else {
          throw new Error("No departments returned");
        }
      })
      .catch(() => {
        // Fallback standard academic departments
        setDepartments([
          { code: "CSE", name: "Computer Science & Engineering", description: "Computing systems, algorithms, distributed networks, and AI" },
          { code: "ECE", name: "Electronics & Communication", description: "VLSI, embedded microcontrollers, signal processing, and robotics" },
          { code: "EEE", name: "Electrical & Electronics", description: "Power systems, control theory, electric machines, and circuits" },
          { code: "MECH", name: "Mechanical Engineering", description: "Thermodynamics, fluid mechanics, CAD/CAM, and design" },
          { code: "CIVIL", name: "Civil Engineering", description: "Structural analysis, geotechnical, and construction engineering" },
          { code: "MATH", name: "Mathematics", description: "Linear algebra, discrete math, calculus, and numerical methods" },
          { code: "PHYS", name: "Physics", description: "Quantum mechanics, electromagnetic theory, and semiconductor physics" },
          { code: "CHEM", name: "Chemistry", description: "Organic chemistry, molecular engineering, and material science" },
          { code: "BIOTECH", name: "Biotechnology", description: "Genetics, molecular biology, bioinformatics, and bioprocesses" },
        ]);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="text-center max-w-3xl mx-auto mb-12">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-cyan-glow/10 border border-cyan-glow/20 text-cyan-accent text-xs font-medium tracking-wide uppercase mb-4">
          <Compass className="w-3.5 h-3.5" />
          <span>Knowledge Universe Explorer</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight mb-3">
          Explore by Department
        </h1>
        <p className="text-sm text-slate-300 leading-relaxed">
          Navigate through academic faculties, subjects, and topics connected in the NEXORA knowledge graph.
        </p>
      </div>

      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center text-slate-400">
          <Loader2 className="w-8 h-8 animate-spin text-cyan-accent mb-3" />
          <p className="text-sm">Mapping universe nodes...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {departments.map((dept) => (
            <Link
              key={dept.code}
              href={`/search?department=${dept.code}`}
              className="glass-panel glass-panel-hover rounded-2xl p-6 flex flex-col justify-between group"
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="w-10 h-10 rounded-xl bg-midnight-900 border border-white/10 flex items-center justify-center font-mono font-bold text-sm text-cyan-accent group-hover:scale-105 transition-transform">
                    {dept.code}
                  </div>
                  <span className="text-xs text-indigo-accent font-medium flex items-center gap-1 group-hover:translate-x-1 transition-transform">
                    Browse
                    <ArrowRight className="w-3.5 h-3.5" />
                  </span>
                </div>

                <h3 className="text-lg font-bold text-white group-hover:text-cyan-accent transition-colors mb-2">
                  {dept.name}
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  {dept.description || "Explore curated textbooks, papers, exams, and lectures."}
                </p>
              </div>

              <div className="border-t border-white/5 pt-4 mt-6 flex items-center justify-between text-xs text-slate-400">
                <span className="flex items-center gap-1.5">
                  <BookOpen className="w-3.5 h-3.5" />
                  Academic Resources
                </span>
                <span className="font-semibold text-slate-300">View Node</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
