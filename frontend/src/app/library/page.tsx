"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api";
import { ResourceSummary } from "@/types";
import ResourceCard from "@/components/ResourceCard";
import { Bookmark, Clock, BookOpen, Loader2, Sparkles } from "lucide-react";

export default function LibraryPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const [activeTab, setActiveTab] = useState<"bookmarks" | "history" | "recommendations">("recommendations");
  const [bookmarks, setBookmarks] = useState<ResourceSummary[]>([]);
  const [history, setHistory] = useState<ResourceSummary[]>([]);
  const [recommendations, setRecommendations] = useState<ResourceSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login");
      return;
    }

    if (user) {
      loadLibraryData();
    }
  }, [user, authLoading]);

  const loadLibraryData = async () => {
    setLoading(true);
    try {
      const [bmData, histData, recData] = await Promise.all([
        apiClient<any>("/engagement/me/bookmarks")
          .then((res) => res.items || res || [])
          .catch(() => []),
        apiClient<any>("/engagement/me/history")
          .then((res) => {
            const list = res.items || res || [];
            return list.map((item: any) => item.resource || item);
          })
          .catch(() => []),
        apiClient<any>("/engagement/recommendations")
          .then((res) => res.items || res || [])
          .catch(async () => {
            // Fallback to top rated/popular resources
            const searchRes = await apiClient<any>("/resources?limit=6").catch(() => ({ items: [] }));
            return searchRes.items || [];
          }),
      ]);
      const safeArray = (data: any): ResourceSummary[] => {
        if (Array.isArray(data)) return data;
        if (data && Array.isArray(data.items)) return data.items;
        if (data && Array.isArray(data.resources)) return data.resources;
        return [];
      };

      setBookmarks(safeArray(bmData));
      setHistory(safeArray(histData));
      setRecommendations(safeArray(recData));
    } finally {
      setLoading(false);
    }
  };

  if (authLoading || loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-accent mb-3" />
        <p className="text-sm">Loading your personal library...</p>
      </div>
    );
  }

  const currentItems =
    activeTab === "recommendations"
      ? recommendations
      : activeTab === "bookmarks"
      ? bookmarks
      : history;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="mb-8">
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight mb-2">
          My Academic Library
        </h1>
        <p className="text-xs text-slate-400">
          Personalized recommendations, saved bookmarks, and your recent reading progress
        </p>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-3 mb-8 border-b border-white/10 pb-4">
        <button
          onClick={() => setActiveTab("recommendations")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-colors ${
            activeTab === "recommendations"
              ? "bg-gradient-to-r from-indigo-brand to-cyan-glow/80 text-white shadow-md shadow-indigo-brand/20"
              : "glass-panel text-slate-300 hover:text-white"
          }`}
        >
          <Sparkles className="w-4 h-4 text-cyan-accent" />
          Recommended For You ({recommendations.length})
        </button>

        <button
          onClick={() => setActiveTab("bookmarks")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-colors ${
            activeTab === "bookmarks"
              ? "bg-indigo-brand text-white shadow-md shadow-indigo-brand/20"
              : "glass-panel text-slate-300 hover:text-white"
          }`}
        >
          <Bookmark className="w-4 h-4" />
          Saved Bookmarks ({bookmarks.length})
        </button>

        <button
          onClick={() => setActiveTab("history")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-colors ${
            activeTab === "history"
              ? "bg-indigo-brand text-white shadow-md shadow-indigo-brand/20"
              : "glass-panel text-slate-300 hover:text-white"
          }`}
        >
          <Clock className="w-4 h-4" />
          Reading History ({history.length})
        </button>
      </div>

      {currentItems.length === 0 ? (
        <div className="glass-panel rounded-2xl p-12 text-center text-slate-400 max-w-md mx-auto">
          <BookOpen className="w-10 h-10 text-indigo-accent/50 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-200 mb-1">
            {activeTab === "recommendations"
              ? "No recommendations available yet"
              : activeTab === "bookmarks"
              ? "No bookmarks saved yet"
              : "No reading history recorded"}
          </h3>
          <p className="text-xs">
            {activeTab === "recommendations"
              ? "Read or bookmark resources in your department to generate personalized recommendations."
              : activeTab === "bookmarks"
              ? "Bookmark interesting papers, books, and lecture notes as you explore."
              : "Resources you read or explore will automatically appear here."}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {currentItems.map((item) => (
            <ResourceCard key={item.resource_id} resource={item} />
          ))}
        </div>
      )}
    </div>
  );
}
