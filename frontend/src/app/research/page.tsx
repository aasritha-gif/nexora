"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api";
import { ResourceSummary, SearchResponse } from "@/types";
import ResourceCard from "@/components/ResourceCard";
import { Sparkles, BookOpen, Filter, Loader2 } from "lucide-react";

export default function ResearchPortalPage() {
  const [papers, setPapers] = useState<ResourceSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedType, setSelectedType] = useState("research_paper");

  useEffect(() => {
    fetchResearch();
  }, [selectedType]);

  const fetchResearch = async () => {
    setLoading(true);
    try {
      const data = await apiClient<SearchResponse>(
        `/search?type=${selectedType}&page=1&page_size=18`
      );
      setPapers(data.items || []);
      setTotal(data.total || 0);
    } catch {
      setPapers([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="mb-8">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-violet-brand/10 border border-violet-brand/20 text-violet-glow text-xs font-medium tracking-wide uppercase mb-3">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Academic Research Discovery</span>
        </div>
        <h1 className="text-3xl font-extrabold text-white tracking-tight mb-2">
          Research Papers, Journals & Dissertations
        </h1>
        <p className="text-xs text-slate-300">
          Peer-reviewed articles, arXiv preprints, theses, and university academic reports.
        </p>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-2 mb-8 border-b border-white/10 pb-4">
        {[
          { label: "Research Papers", value: "research_paper" },
          { label: "Journals & Articles", value: "journal" },
          { label: "Theses & Dissertations", value: "thesis" },
          { label: "Academic Reports", value: "academic_report" },
        ].map((tab) => (
          <button
            key={tab.value}
            onClick={() => setSelectedType(tab.value)}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition-colors ${
              selectedType === tab.value
                ? "bg-violet-brand text-white shadow-md shadow-violet-brand/20"
                : "glass-panel text-slate-300 hover:text-white"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center text-slate-400">
          <Loader2 className="w-8 h-8 animate-spin text-violet-glow mb-3" />
          <p className="text-sm">Fetching research publications...</p>
        </div>
      ) : papers.length === 0 ? (
        <div className="glass-panel rounded-2xl p-12 text-center text-slate-400 max-w-md mx-auto">
          <BookOpen className="w-10 h-10 text-violet-glow/50 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-200 mb-1">No research items found</h3>
          <p className="text-xs">
            Trigger automated ingestion in the Admin dashboard to discover recent open-access publications.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {papers.map((p) => (
            <ResourceCard key={p.resource_id} resource={p} />
          ))}
        </div>
      )}
    </div>
  );
}
