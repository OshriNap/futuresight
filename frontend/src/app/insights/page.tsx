"use client";

import { useEffect, useState } from "react";
import { getInsights } from "@/lib/api";
import { Insight } from "@/lib/types";

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const colors: Record<string, string> = {
    high: "bg-green-500/20 text-green-400 border-green-500/30",
    medium: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    low: "bg-red-500/20 text-red-400 border-red-500/30",
  };
  const cls = colors[confidence] || colors.medium;
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {confidence}
    </span>
  );
}

function DomainTag({ domain }: { domain: string }) {
  return (
    <span className="inline-flex items-center rounded-md bg-accent-blue/15 px-2 py-0.5 text-xs font-medium text-accent-blue">
      {domain}
    </span>
  );
}

function CollapsibleSection({
  title,
  children,
  defaultOpen = false,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-t border-border">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-sm font-medium text-gray-300 hover:text-white transition-colors"
      >
        {title}
        <svg
          className={`w-4 h-4 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && <div className="px-4 pb-3 text-sm text-gray-400 leading-relaxed">{children}</div>}
    </div>
  );
}

function InsightCard({ insight }: { insight: Insight }) {
  const date = new Date(insight.created_at);
  const timeAgo = getTimeAgo(date);

  return (
    <div className={`card overflow-hidden ${insight.stale ? "opacity-60" : ""}`}>
      {/* Header */}
      <div className="p-4 pb-2">
        <div className="flex items-start justify-between gap-3">
          <h3 className={`text-base font-semibold text-white leading-snug ${insight.stale ? "line-through" : ""}`}>
            {insight.title}
          </h3>
          <div className="flex items-center gap-2 shrink-0">
            <ConfidenceBadge confidence={insight.confidence} />
            <DomainTag domain={insight.domain} />
          </div>
        </div>
        <div className="mt-1.5 flex items-center gap-2 text-xs text-gray-500">
          <span>{timeAgo}</span>
          {insight.stale && (
            <span className="inline-flex items-center gap-1 text-yellow-500/70">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
              Stale
            </span>
          )}
        </div>
      </div>

      {/* Collapsible sections */}
      <CollapsibleSection title="Ground Truth" defaultOpen>
        {insight.ground_truth}
      </CollapsibleSection>

      <CollapsibleSection title="Trend Analysis">
        {insight.trend_analysis}
      </CollapsibleSection>

      <CollapsibleSection title="Prediction">
        {insight.prediction}
      </CollapsibleSection>

      <CollapsibleSection title="Action Items">
        {insight.action_items && insight.action_items.length > 0 ? (
          <ul className="list-disc list-inside space-y-1">
            {insight.action_items.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        ) : (
          <span className="text-gray-600">No action items.</span>
        )}
      </CollapsibleSection>

      {/* Sources */}
      {insight.sources && (
        <div className="border-t border-border px-4 py-2.5">
          <p className="text-xs font-medium text-gray-500 mb-1.5">Sources</p>
          <div className="flex flex-wrap gap-1.5">
            {insight.sources.indicators?.map((s, i) => (
              <span key={`ind-${i}`} className="rounded bg-bg-primary px-2 py-0.5 text-xs text-gray-400">
                {s}
              </span>
            ))}
            {insight.sources.market_sources?.map((s, i) => (
              <span key={`mkt-${i}`} className="rounded bg-bg-primary px-2 py-0.5 text-xs text-blue-400">
                {s}
              </span>
            ))}
            {insight.sources.news_sources?.map((s, i) => (
              <span key={`news-${i}`} className="rounded bg-bg-primary px-2 py-0.5 text-xs text-purple-400">
                {s}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function getTimeAgo(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDays = Math.floor(diffHr / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export default function InsightsPage() {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [domainFilter, setDomainFilter] = useState<string>("all");

  useEffect(() => {
    async function loadData() {
      try {
        const data = await getInsights();
        setInsights(data);
      } catch {
        // No data available
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const domains = Array.from(new Set(insights.map((i) => i.domain))).sort();

  const filtered = domainFilter === "all"
    ? insights
    : insights.filter((i) => i.domain === domainFilter);

  // Sort reverse-chronological
  const sorted = [...filtered].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <div className="space-y-6">
      {/* Filter bar */}
      <div className="card">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400">Domain:</span>
            <select
              value={domainFilter}
              onChange={(e) => setDomainFilter(e.target.value)}
              className="rounded-lg border border-border bg-bg-primary px-3 py-1.5 text-sm text-gray-200 focus:border-accent-blue focus:outline-none"
            >
              <option value="all">All domains</option>
              {domains.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>
          <p className="ml-auto text-sm text-gray-400">
            Showing <span className="text-white font-medium">{sorted.length}</span> insights
          </p>
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="card flex h-40 items-center justify-center">
          <p className="text-gray-500">Loading insights...</p>
        </div>
      )}

      {/* Insights feed */}
      {!loading && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {sorted.map((insight) => (
            <InsightCard key={insight.id} insight={insight} />
          ))}
        </div>
      )}

      {!loading && sorted.length === 0 && (
        <div className="card flex h-40 items-center justify-center">
          <p className="text-gray-500">
            No insights available{domainFilter !== "all" ? ` for domain "${domainFilter}"` : ""}.
          </p>
        </div>
      )}
    </div>
  );
}
