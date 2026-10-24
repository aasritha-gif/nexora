"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Search, Sparkles, BookOpen, Compass, Layers, ArrowRight } from "lucide-react";

export default function HomePage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  const sampleQueries = [
    "Find beginner resources for operating systems",
    "Research papers about AI in healthcare",
    "DBMS FAT question papers 2025",
    "Best videos to learn graph algorithms",
  ];

  const featuredDepartments = [
    { code: "CS", name: "Computer Science", count: "1,240+", icon: "💻" },
    { code: "SE", name: "Software Engineering", count: "890+", icon: "⚙️" },
    { code: "IT", name: "Information Technology", count: "750+", icon: "🌐" },
    { code: "ECE", name: "Electronics & Communication", count: "620+", icon: "📡" },
    { code: "MATH", name: "Mathematics", count: "540+", icon: "📐" },
    { code: "BIO", name: "Biotechnology", count: "410+", icon: "🧬" },
  ];

  return (
    <div className="relative min-h-[calc(100vh-4rem)] flex flex-col justify-between">
      {/* Background ambient cosmos glow */}
      <div className="absolute inset-0 bg-cosmos-glow pointer-events-none -z-10" />

      {/* Hero Section */}
      <section className="pt-20 pb-16 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-brand/10 border border-indigo-brand/20 text-indigo-accent text-xs font-medium tracking-wide uppercase mb-8">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Next-Generation Knowledge Universe</span>
        </div>

        <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white mb-6">
          <span className="block">NEXORA</span>
          <span className="block mt-2 text-2xl sm:text-3xl font-medium bg-gradient-to-r from-slate-200 via-indigo-accent to-cyan-accent bg-clip-text text-transparent">
            Your Knowledge. One Intelligent Universe.
          </span>
        </h1>

        <p className="max-w-2xl mx-auto text-slate-300 text-base sm:text-lg mb-10 leading-relaxed">
          Discover, search, read, research, and understand academic resources with intelligent AI tutors, interactive knowledge graphs, and multi-source discovery.
        </p>

        {/* Global Search Bar */}
        <form onSubmit={handleSearch} className="max-w-3xl mx-auto mb-6">
          <div className="relative flex items-center glass-panel rounded-2xl p-2 glow-indigo focus-within:border-indigo-brand/60 transition-all">
            <Search className="w-6 h-6 text-indigo-accent ml-3 mr-2 shrink-0" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="What do you want to learn, research, or discover?"
              className="w-full bg-transparent text-white placeholder-slate-400 text-base px-2 py-2 focus:outline-none"
            />
            <button
              type="submit"
              className="px-6 py-3 rounded-xl bg-gradient-to-r from-indigo-brand to-violet-brand hover:from-indigo-accent hover:to-violet-glow text-white font-semibold text-sm shadow-md transition-all shrink-0"
            >
              Search
            </button>
          </div>
        </form>

        {/* Search Suggestions */}
        <div className="flex flex-wrap items-center justify-center gap-2 max-w-2xl mx-auto text-xs text-slate-400">
          <span className="font-medium text-slate-300">Try searching:</span>
          {sampleQueries.map((query, i) => (
            <button
              key={i}
              onClick={() => {
                setSearchQuery(query);
                router.push(`/search?q=${encodeURIComponent(query)}`);
              }}
              className="px-2.5 py-1 rounded-lg bg-midnight-850 hover:bg-midnight-800 text-slate-300 hover:text-white border border-white/5 hover:border-indigo-brand/30 transition-colors"
            >
              &quot;{query}&quot;
            </button>
          ))}
        </div>
      </section>

      {/* Knowledge Universe Department Nodes */}
      <section className="py-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-xl sm:text-2xl font-bold text-white flex items-center gap-2">
              <Compass className="w-5 h-5 text-cyan-accent" />
              Explore Your Knowledge Universe
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Traverse interconnected departments, subjects, and topics
            </p>
          </div>
          <Link
            href="/explore"
            className="flex items-center gap-1 text-xs font-semibold text-indigo-accent hover:text-white transition-colors"
          >
            Full Universe Map
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          {featuredDepartments.map((dept) => (
            <Link
              key={dept.code}
              href={`/explore?department=${dept.code}`}
              className="glass-panel glass-panel-hover rounded-xl p-4 flex flex-col items-center text-center group"
            >
              <div className="text-3xl mb-2 group-hover:scale-110 transition-transform">
                {dept.icon}
              </div>
              <h3 className="text-sm font-semibold text-white group-hover:text-cyan-accent transition-colors">
                {dept.name}
              </h3>
              <span className="text-[11px] text-slate-400 mt-1">{dept.count} resources</span>
            </Link>
          ))}
        </div>
      </section>

      {/* Feature Highlights Grid */}
      <section className="py-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full border-t border-white/5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="glass-panel rounded-xl p-6">
            <div className="w-10 h-10 rounded-lg bg-indigo-brand/20 text-indigo-accent flex items-center justify-center mb-4">
              <BookOpen className="w-5 h-5" />
            </div>
            <h3 className="text-base font-semibold text-white mb-2">Automated Discovery</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Ingests academic papers, textbooks, and open courseware from verified repositories (arXiv, Open Library, DOAJ, YouTube) with zero manual data entry.
            </p>
          </div>

          <div className="glass-panel rounded-xl p-6">
            <div className="w-10 h-10 rounded-lg bg-violet-brand/20 text-violet-glow flex items-center justify-center mb-4">
              <Sparkles className="w-5 h-5" />
            </div>
            <h3 className="text-base font-semibold text-white mb-2">RAG AI Reading & Chat</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Split-screen AI reader with instantaneous concept simplification, flashcards, and resource-specific AI tutor grounded in genuine chunked text.
            </p>
          </div>

          <div className="glass-panel rounded-xl p-6">
            <div className="w-10 h-10 rounded-lg bg-cyan-glow/20 text-cyan-accent flex items-center justify-center mb-4">
              <Layers className="w-5 h-5" />
            </div>
            <h3 className="text-base font-semibold text-white mb-2">Polyglot NoSQL Engine</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Spans MongoDB (canonical documents), Redis (real-time cache & rate limits), Neo4j (relational knowledge graph), and MonetDB (columnar analytics).
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
