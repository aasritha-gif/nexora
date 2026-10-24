import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-white/10 bg-midnight-950 py-12 text-slate-400 text-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="w-7 h-7 rounded-lg bg-indigo-brand flex items-center justify-center font-mono font-bold text-white text-sm">
                N
              </div>
              <span className="font-bold text-white tracking-tight">NEXORA</span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed mb-4">
              Your Knowledge. One Intelligent Universe. Connecting academic discovery, intelligent RAG study companions, and knowledge networks.
            </p>
            <div className="text-[11px] text-slate-400 font-mono">
              MongoDB · Redis · Neo4j · MonetDB
            </div>
          </div>

          <div>
            <h4 className="text-white font-semibold text-xs tracking-wider uppercase mb-3">Discovery</h4>
            <ul className="space-y-2 text-xs">
              <li><Link href="/explore" className="hover:text-indigo-accent transition-colors">Knowledge Universe</Link></li>
              <li><Link href="/search" className="hover:text-indigo-accent transition-colors">Academic Search</Link></li>
              <li><Link href="/research" className="hover:text-indigo-accent transition-colors">Research Portal</Link></li>
              <li><Link href="/explore?type=video" className="hover:text-indigo-accent transition-colors">Video Learning</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="text-white font-semibold text-xs tracking-wider uppercase mb-3">Intelligent AI</h4>
            <ul className="space-y-2 text-xs">
              <li><span className="text-slate-400">Resource AI Overview</span></li>
              <li><span className="text-slate-400">Contextual Reading Assistant</span></li>
              <li><span className="text-slate-400">Resource AI Chatbot (RAG)</span></li>
              <li><span className="text-slate-400">Exam Question Intelligence</span></li>
            </ul>
          </div>

          <div>
            <h4 className="text-white font-semibold text-xs tracking-wider uppercase mb-3">Platform</h4>
            <ul className="space-y-2 text-xs">
              <li><Link href="/profile" className="hover:text-indigo-accent transition-colors">Student Profile</Link></li>
              <li><Link href="/admin" className="hover:text-indigo-accent transition-colors">Admin Dashboard</Link></li>
              <li><a href="http://localhost:8000/docs" target="_blank" rel="noreferrer" className="hover:text-indigo-accent transition-colors">API Docs</a></li>
            </ul>
          </div>
        </div>

        <div className="border-t border-white/5 pt-6 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-400">
          <p>© {new Date().getFullYear()} NEXORA Academic Platform. All rights reserved.</p>
          <p className="mt-2 sm:mt-0 font-mono text-[11px]">
            Academic Engineering Project · Zero Mock Database Protocol
          </p>
        </div>
      </div>
    </footer>
  );
}
