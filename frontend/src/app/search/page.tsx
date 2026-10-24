"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import ResourceCard from "@/components/ResourceCard";
import { apiClient } from "@/lib/api";
import { SearchResponse, ResourceSummary } from "@/types";
import { Search, Filter, Sparkles, Loader2 } from "lucide-react";

function SearchContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const initialQuery = searchParams.get("q") || "";
  const initialDept = searchParams.get("department") || "";
  const initialType = searchParams.get("type") || "";

  const [query, setQuery] = useState(initialQuery);
  const [department, setDepartment] = useState(initialDept);
  const [resourceType, setResourceType] = useState(initialType);
  const [accessType, setAccessType] = useState("");

  const [results, setResults] = useState<ResourceSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchResults = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (query.trim()) params.set("q", query.trim());
      if (department) params.set("department", department);
      if (resourceType) params.set("type", resourceType);
      if (accessType) params.set("access", accessType);
      params.set("page", "1");
      params.set("page_size", "24");

      const data = await apiClient<any>(`/search?${params.toString()}`);
      setResults(data.results || data.items || []);
      setTotal(data.total || 0);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to execute search");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResults();
  }, [department, resourceType, accessType]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchResults();
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header and Search bar */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white mb-2 flex items-center gap-2">
          <Search className="w-6 h-6 text-indigo-accent" />
          Academic Search Engine
        </h1>
        <p className="text-xs text-slate-400 mb-6">
          Search textbooks, papers, lectures, videos, and exams across all university disciplines
        </p>

        <form onSubmit={handleSearchSubmit} className="flex gap-2">
          <div className="relative flex-1">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by keywords, author, DOI, topics, or ask a question..."
              className="w-full px-4 py-3 rounded-xl bg-midnight-900 border border-white/10 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-brand transition-colors"
            />
          </div>
          <button
            type="submit"
            className="px-6 py-3 rounded-xl bg-indigo-brand hover:bg-indigo-accent text-white font-medium text-sm transition-colors flex items-center gap-2"
          >
            <Search className="w-4 h-4" />
            Search
          </button>
        </form>
      </div>

      {/* Filter Row */}
      <div className="glass-panel rounded-xl p-4 mb-8 flex flex-wrap items-center gap-4 text-xs">
        <div className="flex items-center gap-2 text-slate-400 font-medium">
          <Filter className="w-4 h-4 text-cyan-accent" />
          <span>Filters:</span>
        </div>

        {/* Department Filter */}
        <select
          value={department}
          onChange={(e) => setDepartment(e.target.value)}
          className="px-3 py-1.5 rounded-lg bg-midnight-950 border border-white/10 text-slate-200 focus:outline-none focus:border-indigo-brand"
        >
          <option value="">All Departments</option>
          <option value="CSE">Computer Science & Engineering</option>
          <option value="ECE">Electronics & Communication</option>
          <option value="EEE">Electrical & Electronics</option>
          <option value="MECH">Mechanical Engineering</option>
          <option value="CIVIL">Civil Engineering</option>
          <option value="BIOTECH">Biotechnology</option>
          <option value="MATH">Mathematics</option>
          <option value="PHYS">Physics</option>
          <option value="CHEM">Chemistry</option>
        </select>

        {/* Type Filter */}
        <select
          value={resourceType}
          onChange={(e) => setResourceType(e.target.value)}
          className="px-3 py-1.5 rounded-lg bg-midnight-950 border border-white/10 text-slate-200 focus:outline-none focus:border-indigo-brand"
        >
          <option value="">All Resource Types</option>
          <option value="book">Books</option>
          <option value="research_paper">Research Papers</option>
          <option value="journal">Journals</option>
          <option value="question_paper">Question Papers</option>
          <option value="video">Videos</option>
          <option value="lecture_notes">Lecture Notes</option>
        </select>

        {/* Access Filter */}
        <select
          value={accessType}
          onChange={(e) => setAccessType(e.target.value)}
          className="px-3 py-1.5 rounded-lg bg-midnight-950 border border-white/10 text-slate-200 focus:outline-none focus:border-indigo-brand"
        >
          <option value="">All Access</option>
          <option value="free">Free Only</option>
          <option value="premium">Premium Only</option>
        </select>

        <span className="ml-auto text-slate-400">
          Showing <span className="font-semibold text-white">{results.length}</span> of {total} resources
        </span>
      </div>

      {/* Results or Loading */}
      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center text-slate-400">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-accent mb-3" />
          <p className="text-sm">Searching knowledge universe...</p>
        </div>
      ) : error ? (
        <div className="py-16 text-center text-rose-400 text-sm glass-panel rounded-xl p-8">
          {error}
        </div>
      ) : results.length === 0 ? (
        <div className="py-16 text-center text-slate-400 glass-panel rounded-xl p-8">
          <p className="text-base font-medium text-slate-300 mb-1">No academic resources found</p>
          <p className="text-xs">Try adjusting your filters or searching with different keywords</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {results.map((res) => (
            <ResourceCard key={res.resource_id} resource={res} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="p-12 text-center text-slate-400">Loading search...</div>}>
      <SearchContent />
    </Suspense>
  );
}
