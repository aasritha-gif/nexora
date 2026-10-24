import Link from "next/link";
import { ResourceSummary } from "@/types";
import { BookOpen, Star, Eye, Calendar, Sparkles } from "lucide-react";
import BookCover from "@/components/BookCover";

interface ResourceCardProps {
  resource: ResourceSummary;
}

export default function ResourceCard({ resource }: ResourceCardProps) {
  const isPremium = resource.access === "premium";
  const deptCode = resource.taxonomy?.department || "CSE";

  return (
    <div className="glass-panel glass-panel-hover rounded-xl p-5 flex flex-col justify-between relative group">
      {/* Seed Badge if development data */}
      {resource.is_seed_data && (
        <span className="absolute top-3 right-3 text-[10px] font-mono tracking-wider px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 z-20">
          DEVELOPMENT DATA
        </span>
      )}

      <div>
        {/* Cover + Basic Info Row */}
        <div className="flex gap-4 mb-4">
          <Link href={`/resources/${resource.resource_id}`} className="shrink-0 transition-transform group-hover:scale-105 duration-200">
            <BookCover
              title={resource.title}
              type={resource.type}
              department={deptCode}
              authors={resource.authors}
              size="sm"
            />
          </Link>
          <div className="flex-1 min-w-0">
            {/* Type & Access pills */}
            <div className="flex flex-wrap items-center gap-1.5 mb-2">
              <span className="text-[10px] font-medium tracking-wide uppercase px-2 py-0.5 rounded bg-indigo-brand/15 text-indigo-accent border border-indigo-brand/20">
                {resource.type.replace("_", " ")}
              </span>
              <span
                className={`text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded ${
                  isPremium
                    ? "bg-amber-500/15 text-amber-300 border border-amber-500/25"
                    : "bg-emerald-500/15 text-emerald-400 border border-emerald-500/25"
                }`}
              >
                {isPremium ? `$${resource.premium_price_usd || "4.99"}` : "FREE"}
              </span>
            </div>

            {/* Title */}
            <Link href={`/resources/${resource.resource_id}`}>
              <h3 className="text-sm font-semibold text-white group-hover:text-indigo-accent transition-colors line-clamp-2 leading-snug mb-1">
                {resource.title}
              </h3>
            </Link>

            {/* Authors */}
            {resource.authors && resource.authors.length > 0 && (
              <p className="text-[11px] text-slate-400 line-clamp-1">
                By {resource.authors.join(", ")}
              </p>
            )}
          </div>
        </div>

        {/* Description snippet */}
        {resource.description && (
          <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed mb-4">
            {resource.description}
          </p>
        )}

        {/* Taxonomy breadcrumb */}
        {resource.taxonomy && (
          <div className="flex flex-wrap gap-1 mb-4">
            {resource.taxonomy.department_name && (
              <span className="text-[10px] px-2 py-0.5 rounded bg-midnight-800 text-slate-300 border border-white/5">
                {resource.taxonomy.department_name}
              </span>
            )}
            {resource.taxonomy.subject_names && resource.taxonomy.subject_names[0] && (
              <span className="text-[10px] px-2 py-0.5 rounded bg-midnight-800 text-slate-300 border border-white/5">
                {resource.taxonomy.subject_names[0]}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Footer stats & Actions */}
      <div className="border-t border-white/5 pt-3 mt-2 flex items-center justify-between text-xs text-slate-400">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1 text-amber-400">
            <Star className="w-3.5 h-3.5 fill-amber-400" />
            <span className="font-semibold text-slate-200">
              {resource.rating_average ? resource.rating_average.toFixed(1) : "New"}
            </span>
          </span>
          <span className="flex items-center gap-1">
            <Eye className="w-3.5 h-3.5" />
            {resource.views || 0}
          </span>
        </div>

        <Link
          href={`/resources/${resource.resource_id}`}
          className="flex items-center gap-1 text-indigo-accent hover:text-white font-medium text-xs group-hover:translate-x-0.5 transition-all"
        >
          Explore
          <span>→</span>
        </Link>
      </div>
    </div>
  );
}
