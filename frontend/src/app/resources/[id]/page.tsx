"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api";
import { ResourceDetail } from "@/types";
import {
  BookOpen,
  Sparkles,
  Bot,
  Bookmark,
  Star,
  Eye,
  ExternalLink,
  ShieldAlert,
  Loader2,
  Share2,
} from "lucide-react";
import BookCover from "@/components/BookCover";

export default function ResourceDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const resourceId = resolvedParams.id;

  const [resource, setResource] = useState<ResourceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // AI Tab state: overview, reader, chat
  const [activeTab, setActiveTab] = useState<"details" | "ai_overview" | "ai_chat">("details");
  const [aiOverview, setAiOverview] = useState<any | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  // Chat message state
  const [chatMessages, setChatMessages] = useState<Array<{ role: string; content: string }>>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatSending, setChatSending] = useState(false);

  // Citation & Bookmarking State
  const [showCitationModal, setShowCitationModal] = useState(false);
  const [citationFormat, setCitationFormat] = useState<"apa" | "bibtex" | "ieee">("apa");
  const [copiedCitation, setCopiedCitation] = useState(false);
  const [isBookmarked, setIsBookmarked] = useState(false);
  const [bookmarkLoading, setBookmarkLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    apiClient<ResourceDetail>(`/resources/${resourceId}`)
      .then((data) => setResource(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [resourceId]);

  const loadAiOverview = async () => {
    setActiveTab("ai_overview");
    if (aiOverview) return;
    setAiLoading(true);
    setAiError(null);
    try {
      const data = await apiClient<any>(`/ai/resources/${resourceId}/overview`);
      setAiOverview(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setAiError(err.message);
      } else {
        setAiError("AI features are currently not configured.");
      }
    } finally {
      setAiLoading(false);
    }
  };

  const handleSendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || chatSending) return;

    const userMsg = chatInput.trim();
    setChatMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setChatInput("");
    setChatSending(true);

    try {
      const res = await apiClient<any>(`/ai/resources/${resourceId}/chat`, {
        method: "POST",
        body: JSON.stringify({ message: userMsg }),
      });
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.reply || res.answer || "No response received." },
      ]);
    } catch (err: unknown) {
      setChatMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: err instanceof Error ? `Notice: ${err.message}` : "AI tutor unavailable.",
        },
      ]);
    } finally {
      setChatSending(false);
    }
  };

  const generateCitation = (format: "apa" | "bibtex" | "ieee") => {
    if (!resource) return "";
    const authors = resource.authors?.join(", ") || "Unknown Author";
    const year = resource.year || new Date().getFullYear();
    const title = resource.title;
    const publisher = resource.publisher || "Academic Press";

    if (format === "apa") {
      return `${authors} (${year}). ${title}. ${publisher}.`;
    } else if (format === "ieee") {
      return `[1] ${authors}, "${title}," ${publisher}, ${year}.`;
    } else {
      // BibTeX
      const citeKey = (resource.authors?.[0]?.split(" ").pop()?.toLowerCase() || "res") + year;
      return `@article{${citeKey},\n  title={${title}},\n  author={${authors}},\n  publisher={${publisher}},\n  year={${year}}\n}`;
    }
  };

  const handleCopyCitation = () => {
    const text = generateCitation(citationFormat);
    navigator.clipboard.writeText(text);
    setCopiedCitation(true);
    setTimeout(() => setCopiedCitation(false), 2000);
  };

  const handleToggleBookmark = async () => {
    setBookmarkLoading(true);
    try {
      await apiClient(`/engagement/bookmarks/${resourceId}`, {
        method: isBookmarked ? "DELETE" : "POST",
      });
      setIsBookmarked(!isBookmarked);
    } catch {
      // fallback toggle for UI feedback
      setIsBookmarked(!isBookmarked);
    } finally {
      setBookmarkLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-accent mb-3" />
        <p className="text-sm">Retrieving academic resource...</p>
      </div>
    );
  }

  if (error || !resource) {
    return (
      <div className="max-w-3xl mx-auto py-16 px-4 text-center">
        <div className="glass-panel rounded-2xl p-8 border border-white/10">
          <ShieldAlert className="w-10 h-10 text-rose-400 mx-auto mb-3" />
          <h2 className="text-lg font-bold text-white mb-2">Resource Not Found</h2>
          <p className="text-xs text-slate-400 mb-6">{error || "Could not retrieve the requested resource."}</p>
          <Link
            href="/search"
            className="px-4 py-2 rounded-xl bg-indigo-brand text-white text-xs font-semibold"
          >
            Back to Search
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Top Banner */}
      <div className="glass-panel rounded-2xl p-6 sm:p-8 mb-8 relative border border-white/10">
        {resource.is_seed_data && (
          <span className="absolute top-4 right-4 text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
            DEVELOPMENT DATA
          </span>
        )}

        <div className="flex flex-col sm:flex-row gap-6 items-start">
          <BookCover
            title={resource.title}
            type={resource.type}
            department={resource.taxonomy?.department || "CSE"}
            authors={resource.authors}
            size="lg"
            className="shadow-2xl hover:rotate-1 transition-transform duration-300"
          />

          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-4">
              <span className="text-xs uppercase px-2.5 py-0.5 rounded bg-indigo-brand/20 text-indigo-accent border border-indigo-brand/30 font-medium">
                {resource.type.replace("_", " ")}
              </span>
              <span
                className={`text-xs uppercase px-2.5 py-0.5 rounded font-semibold ${
                  resource.access === "premium"
                    ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                    : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                }`}
              >
                {resource.access === "premium" ? `$${resource.premium_price_usd || "4.99"}` : "FREE ACCESS"}
              </span>
              {resource.year && <span className="text-xs text-slate-400 ml-2">Published: {resource.year}</span>}
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold text-white mb-3 tracking-tight">
              {resource.title}
            </h1>

            {resource.authors && resource.authors.length > 0 && (
              <p className="text-sm text-slate-300 mb-4">
                Authors: <span className="text-white font-medium">{resource.authors.join(", ")}</span>
              </p>
            )}

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center gap-3 pt-2">
          {resource.external_url && (
            <a
              href={resource.external_url}
              target="_blank"
              rel="noreferrer"
              className="px-4 py-2 rounded-xl bg-white text-midnight-950 hover:bg-slate-200 font-semibold text-xs flex items-center gap-2 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Access Official Source
            </a>
          )}

          <button
            onClick={loadAiOverview}
            className={`px-4 py-2 rounded-xl border text-xs font-semibold flex items-center gap-2 transition-colors ${
              activeTab === "ai_overview"
                ? "bg-indigo-brand/20 border-indigo-brand text-indigo-accent"
                : "border-white/10 hover:border-indigo-brand/40 text-slate-200"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-cyan-accent" />
            AI Overview
          </button>

          <button
            onClick={() => setActiveTab("ai_chat")}
            className={`px-4 py-2 rounded-xl border text-xs font-semibold flex items-center gap-2 transition-colors ${
              activeTab === "ai_chat"
                ? "bg-indigo-brand/20 border-indigo-brand text-indigo-accent"
                : "border-white/10 hover:border-indigo-brand/40 text-slate-200"
            }`}
          >
            <Bot className="w-3.5 h-3.5 text-indigo-accent" />
            AI Tutor Chat
          </button>

          <button
            onClick={handleToggleBookmark}
            disabled={bookmarkLoading}
            className={`px-4 py-2 rounded-xl border text-xs font-semibold flex items-center gap-2 transition-colors ${
              isBookmarked
                ? "bg-amber-500/20 border-amber-500/40 text-amber-300"
                : "border-white/10 hover:border-amber-500/30 text-slate-200"
            }`}
          >
            <Bookmark className={`w-3.5 h-3.5 ${isBookmarked ? "fill-amber-400 text-amber-400" : ""}`} />
            {isBookmarked ? "Bookmarked" : "Bookmark"}
          </button>

          <button
            onClick={() => setShowCitationModal(true)}
            className="px-4 py-2 rounded-xl border border-white/10 hover:border-cyan-accent/40 text-slate-200 text-xs font-semibold flex items-center gap-2 transition-colors"
          >
            <Share2 className="w-3.5 h-3.5 text-cyan-accent" />
            Cite & Export
          </button>
        </div>
        </div>
      </div>
      </div>

      {/* Main Tab View */}
      {activeTab === "details" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <div className="glass-panel rounded-2xl p-6">
              <h2 className="text-base font-semibold text-white mb-3">Abstract / Description</h2>
              <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">
                {resource.description || "No description provided for this academic resource."}
              </p>
            </div>

            {resource.keywords && resource.keywords.length > 0 && (
              <div className="glass-panel rounded-2xl p-6">
                <h3 className="text-sm font-semibold text-white mb-3">Keywords & Concepts</h3>
                <div className="flex flex-wrap gap-2">
                  {resource.keywords.map((kw, i) => (
                    <span
                      key={i}
                      className="px-2.5 py-1 rounded-lg bg-midnight-900 border border-white/5 text-xs text-slate-300"
                    >
                      {kw}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right Sidebar Metadata */}
          <div className="space-y-6">
            <div className="glass-panel rounded-2xl p-6 text-xs space-y-4">
              <h3 className="text-sm font-semibold text-white border-b border-white/10 pb-2">
                Resource Metadata
              </h3>
              <div>
                <span className="text-slate-400 block mb-0.5">Resource ID</span>
                <span className="font-mono text-slate-200">{resource.resource_id}</span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Department</span>
                <span className="text-slate-200">{resource.taxonomy?.department_name || "General"}</span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Rating</span>
                <span className="text-amber-400 font-semibold">
                  ★ {resource.rating_average ? resource.rating_average.toFixed(1) : "Unrated"} ({resource.rating_count} reviews)
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Reads & Views</span>
                <span className="text-slate-200">{resource.views} views · {resource.reads} reads</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* AI Overview Tab */}
      {activeTab === "ai_overview" && (
        <div className="glass-panel rounded-2xl p-8 border border-white/10">
          <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/10">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-cyan-accent" />
              <h2 className="text-lg font-bold text-white">Resource AI Overview</h2>
            </div>
            <button
              onClick={() => setActiveTab("details")}
              className="text-xs text-slate-400 hover:text-white"
            >
              Back to Details
            </button>
          </div>

          {aiLoading ? (
            <div className="py-12 text-center text-slate-400 flex flex-col items-center">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-accent mb-2" />
              <p className="text-xs">Synthesizing key insights, prerequisites, and concepts...</p>
            </div>
          ) : aiError ? (
            <div className="p-6 rounded-xl bg-midnight-900 border border-amber-500/20 text-sm text-slate-300 flex flex-col items-center text-center gap-3">
              <div className="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-amber-400" />
              </div>
              <div>
                <p className="font-semibold text-amber-400 mb-1">AI Features Not Configured</p>
                <p className="text-slate-400 text-xs max-w-md">
                  AI Overview requires an AI provider (OpenAI or Anthropic) to be set up.
                  The platform is running without an AI key — all other features work normally.
                </p>
              </div>
            </div>
          ) : aiOverview ? (
            <div className="space-y-5 text-sm text-slate-300">
              {/* Summary */}
              <div>
                <h3 className="font-semibold text-white mb-2">📋 Executive Summary</h3>
                <p className="leading-relaxed">{aiOverview.summary || "Summary generated."}</p>
              </div>

              {/* Difficulty + Who Should Read */}
              {(aiOverview.difficulty || aiOverview.who_should_read) && (
                <div className="flex flex-wrap gap-4">
                  {aiOverview.difficulty && (
                    <div className="px-3 py-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-xs">
                      <span className="text-slate-400">Difficulty: </span>
                      <span className="text-indigo-300 font-semibold capitalize">{aiOverview.difficulty}</span>
                    </div>
                  )}
                  {aiOverview.who_should_read && (
                    <div className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-slate-400">
                      👤 {aiOverview.who_should_read}
                    </div>
                  )}
                </div>
              )}

              {/* Key Concepts */}
              {(aiOverview.key_concepts || aiOverview.key_points) && (
                <div>
                  <h3 className="font-semibold text-white mb-2">🔑 Key Concepts</h3>
                  <div className="flex flex-wrap gap-2">
                    {(aiOverview.key_concepts || aiOverview.key_points || []).map((c: string, i: number) => (
                      <span key={i} className="px-2.5 py-1 rounded-lg bg-midnight-900 border border-white/10 text-xs text-slate-300">{c}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Important Points */}
              {aiOverview.important_points && aiOverview.important_points.length > 0 && (
                <div>
                  <h3 className="font-semibold text-white mb-2">📌 Important Points</h3>
                  <ul className="list-disc pl-5 space-y-1">
                    {aiOverview.important_points.map((pt: string, i: number) => (
                      <li key={i}>{pt}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Prerequisites */}
              {aiOverview.prerequisites && aiOverview.prerequisites.length > 0 && (
                <div>
                  <h3 className="font-semibold text-white mb-2">📚 Prerequisites</h3>
                  <ul className="list-disc pl-5 space-y-1">
                    {aiOverview.prerequisites.map((p: string, i: number) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Key Takeaways */}
              {aiOverview.key_takeaways && aiOverview.key_takeaways.length > 0 && (
                <div>
                  <h3 className="font-semibold text-white mb-2">✅ Key Takeaways</h3>
                  <ul className="list-disc pl-5 space-y-1">
                    {aiOverview.key_takeaways.map((t: string, i: number) => (
                      <li key={i}>{t}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Research Analysis (for papers/journals) */}
              {aiOverview.research && (
                <div>
                  <h3 className="font-semibold text-white mb-2">🔬 Research Analysis</h3>
                  <div className="space-y-2 text-xs">
                    {Object.entries(aiOverview.research).map(([key, val]) => (
                      <div key={key} className="flex gap-2">
                        <span className="text-slate-500 capitalize min-w-[90px]">{key.replace("_", " ")}:</span>
                        <span className="text-slate-300">{val as string}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>
      )}

      {/* AI Chat Tab */}
      {activeTab === "ai_chat" && (
        <div className="glass-panel rounded-2xl p-6 border border-white/10 flex flex-col h-[550px]">
          <div className="flex items-center justify-between pb-3 border-b border-white/10 mb-4">
            <div className="flex items-center gap-2">
              <Bot className="w-5 h-5 text-indigo-accent" />
              <div>
                <h2 className="text-sm font-bold text-white">Resource AI Tutor</h2>
                <span className="text-[10px] text-slate-400">Context-grounded RAG assistance</span>
              </div>
            </div>
            <button
              onClick={() => setActiveTab("details")}
              className="text-xs text-slate-400 hover:text-white"
            >
              Back to Details
            </button>
          </div>

          {/* Message List */}
          <div className="flex-1 overflow-y-auto space-y-3 pr-2 text-xs">
            {chatMessages.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-slate-400 text-center px-4">
                <Bot className="w-8 h-8 text-indigo-accent/50 mb-2" />
                <p className="font-medium text-slate-300">Ask the Resource Tutor</p>
                <p className="text-[11px] mt-1 max-w-sm">
                  Ask questions about specific chapters, methodologies, key equations, or exam concepts covered in this resource.
                </p>
              </div>
            )}
            {chatMessages.map((msg, i) => (
              <div
                key={i}
                className={`p-3 rounded-xl max-w-[85%] ${
                  msg.role === "user"
                    ? "ml-auto bg-indigo-brand/20 text-indigo-200 border border-indigo-brand/30"
                    : "mr-auto bg-midnight-900 text-slate-200 border border-white/10"
                }`}
              >
                <p className="leading-relaxed">{msg.content}</p>
              </div>
            ))}
          </div>

          {/* Chat Input */}
          <form onSubmit={handleSendChat} className="pt-3 border-t border-white/10 flex gap-2">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Ask a question about this resource..."
              className="flex-1 px-3.5 py-2.5 rounded-xl bg-midnight-900 border border-white/10 text-white placeholder-slate-500 text-xs focus:outline-none focus:border-indigo-brand"
            />
            <button
              type="submit"
              disabled={chatSending}
              className="px-4 py-2.5 rounded-xl bg-indigo-brand hover:bg-indigo-accent text-white text-xs font-semibold disabled:opacity-50"
            >
              Send
            </button>
          </form>
        </div>
      )}

      {/* Citation Modal */}
      {showCitationModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-panel border border-white/20 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative">
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-white/10">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Share2 className="w-4 h-4 text-cyan-accent" />
                Export Citation
              </h3>
              <button
                onClick={() => setShowCitationModal(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-300 mb-4">
              Select format to copy the standard academic citation:
            </p>

            <div className="flex gap-2 mb-4">
              {(["apa", "ieee", "bibtex"] as const).map((fmt) => (
                <button
                  key={fmt}
                  onClick={() => setCitationFormat(fmt)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition-colors ${
                    citationFormat === fmt
                      ? "bg-indigo-brand text-white border border-indigo-brand"
                      : "bg-midnight-900 text-slate-400 hover:text-white border border-white/5"
                  }`}
                >
                  {fmt}
                </button>
              ))}
            </div>

            <div className="p-3 rounded-xl bg-midnight-950 border border-white/10 text-xs font-mono text-slate-200 mb-5 break-words whitespace-pre-wrap select-all max-h-48 overflow-y-auto">
              {generateCitation(citationFormat)}
            </div>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowCitationModal(false)}
                className="px-4 py-2 rounded-xl text-xs text-slate-400 hover:text-white"
              >
                Close
              </button>
              <button
                onClick={handleCopyCitation}
                className="px-5 py-2 rounded-xl bg-gradient-to-r from-indigo-brand to-violet-brand hover:from-indigo-accent hover:to-violet-glow text-white text-xs font-semibold shadow-md transition-all flex items-center gap-1.5"
              >
                {copiedCitation ? "✓ Copied!" : "Copy to Clipboard"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
