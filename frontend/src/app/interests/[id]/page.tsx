"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { getInterests, getIndicatorHistory, getInsights } from "@/lib/api";
import { UserInterest, IndicatorHistory, Insight } from "@/lib/types";

const CHART_COLORS = [
  "#3b82f6",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#ec4899",
  "#06b6d4",
  "#f97316",
];

function getPriorityBadge(priority: string): string {
  switch (priority) {
    case "high":
      return "bg-confidence-low/15 text-confidence-low";
    case "medium":
      return "bg-confidence-medium/15 text-confidence-medium";
    case "low":
      return "bg-gray-500/15 text-gray-400";
    default:
      return "bg-gray-500/15 text-gray-400";
  }
}

export default function InterestDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const [interest, setInterest] = useState<UserInterest | null>(null);
  const [histories, setHistories] = useState<IndicatorHistory[]>([]);
  const [insight, setInsight] = useState<Insight | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);

        const interests = await getInterests();
        const found = interests.find(
          (i) => String(i.id) === String(id)
        );

        if (!found) {
          setError("Interest not found");
          setLoading(false);
          return;
        }

        setInterest(found);

        // Fetch indicator histories
        if (found.indicators && found.indicators.length > 0) {
          const historyPromises = found.indicators.map((seriesId) =>
            getIndicatorHistory(seriesId).catch(() => null)
          );
          const results = await Promise.all(historyPromises);
          setHistories(
            results.filter((h): h is IndicatorHistory => h !== null)
          );
        }

        // Fetch insights for this domain (use category or name)
        try {
          const domain = found.category || found.name;
          const insights = await getInsights(domain);
          if (insights.length > 0) {
            setInsight(insights[0]);
          }
        } catch {
          // No insights available
        }
      } catch {
        setError("Failed to load interest data");
      } finally {
        setLoading(false);
      }
    }

    if (id) loadData();
  }, [id]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-gray-400">Loading interest details...</div>
      </div>
    );
  }

  if (error || !interest) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-4">
        <p className="text-gray-400">{error || "Interest not found"}</p>
        <Link
          href="/interests"
          className="text-accent-blue hover:underline"
        >
          Back to Interests
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/interests"
        className="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-white transition-colors"
      >
        <svg
          className="h-4 w-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15.75 19.5L8.25 12l7.5-7.5"
          />
        </svg>
        Back to Interests
      </Link>

      {/* Header */}
      <div className="card">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-white">
                {interest.name}
              </h1>
              <span
                className={`badge ${getPriorityBadge(interest.priority)}`}
              >
                {interest.priority}
              </span>
              {interest.region && (
                <span className="badge bg-purple-500/15 text-purple-400">
                  {interest.region}
                </span>
              )}
              <span
                className={`badge ${
                  interest.enabled !== false
                    ? "bg-green-500/15 text-green-400"
                    : "bg-gray-500/15 text-gray-500"
                }`}
              >
                {interest.enabled !== false ? "Enabled" : "Disabled"}
              </span>
            </div>
            <p className="mt-2 text-gray-400">
              Category: {interest.category || "General"}
            </p>
          </div>
        </div>
      </div>

      {/* Indicator Charts */}
      {histories.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-white">
            Indicator Charts
          </h2>
          {histories.map((history, idx) => (
            <div key={history.series_id} className="card">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-white">{history.name}</h3>
                  <p className="text-sm text-gray-500">
                    {history.series_id} &middot; {history.agency}
                    {history.unit ? ` &middot; ${history.unit}` : ""}
                  </p>
                </div>
                <span className="text-sm text-gray-500">
                  {history.data.length} data points
                </span>
              </div>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={history.data}>
                    <XAxis
                      dataKey="period"
                      stroke="#6b7280"
                      tick={{ fill: "#9ca3af", fontSize: 12 }}
                      tickLine={{ stroke: "#4b5563" }}
                    />
                    <YAxis
                      stroke="#6b7280"
                      tick={{ fill: "#9ca3af", fontSize: 12 }}
                      tickLine={{ stroke: "#4b5563" }}
                      width={60}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#1f2937",
                        border: "1px solid #374151",
                        borderRadius: "0.5rem",
                        color: "#f3f4f6",
                      }}
                      labelStyle={{ color: "#9ca3af" }}
                    />
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke={CHART_COLORS[idx % CHART_COLORS.length]}
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4, fill: CHART_COLORS[idx % CHART_COLORS.length] }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Market Predictions */}
      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-4">
          Market Predictions
        </h2>
        <div className="space-y-3">
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-2">
              Keywords
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {interest.keywords.map((kw) => (
                <span
                  key={kw}
                  className="rounded bg-accent-blue/10 px-2.5 py-1 text-sm text-accent-blue"
                >
                  {kw}
                </span>
              ))}
            </div>
          </div>
          {interest.market_filters && interest.market_filters.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">
                Market Filters
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {interest.market_filters.map((filter) => (
                  <span
                    key={filter}
                    className="rounded bg-purple-500/10 px-2.5 py-1 text-sm text-purple-400"
                  >
                    {filter}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Latest Insight */}
      {insight && (
        <div className="card">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">
              Latest Insight
            </h2>
            <div className="flex items-center gap-2">
              <span
                className={`badge ${
                  insight.stale
                    ? "bg-yellow-500/15 text-yellow-400"
                    : "bg-green-500/15 text-green-400"
                }`}
              >
                {insight.stale ? "Stale" : "Fresh"}
              </span>
              <span className="text-sm text-gray-500">
                {insight.confidence} confidence
              </span>
            </div>
          </div>
          <h3 className="mb-3 font-medium text-white">{insight.title}</h3>

          <div className="space-y-4">
            <div>
              <h4 className="text-sm font-medium text-accent-blue mb-1">
                Ground Truth
              </h4>
              <p className="text-sm text-gray-300 whitespace-pre-wrap">
                {insight.ground_truth}
              </p>
            </div>
            <div>
              <h4 className="text-sm font-medium text-green-400 mb-1">
                Trend Analysis
              </h4>
              <p className="text-sm text-gray-300 whitespace-pre-wrap">
                {insight.trend_analysis}
              </p>
            </div>
            <div>
              <h4 className="text-sm font-medium text-yellow-400 mb-1">
                Prediction
              </h4>
              <p className="text-sm text-gray-300 whitespace-pre-wrap">
                {insight.prediction}
              </p>
            </div>
            {insight.action_items && insight.action_items.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-purple-400 mb-1">
                  Action Items
                </h4>
                <ul className="list-disc list-inside space-y-1">
                  {insight.action_items.map((item, idx) => (
                    <li key={idx} className="text-sm text-gray-300">
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Configuration */}
      <div className="card">
        <h2 className="text-lg font-semibold text-white mb-4">
          Configuration
        </h2>
        <div className="space-y-3">
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-2">
              Keywords
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {interest.keywords.map((kw) => (
                <span
                  key={kw}
                  className="rounded bg-bg-primary px-2.5 py-1 text-sm text-gray-300"
                >
                  {kw}
                </span>
              ))}
            </div>
          </div>
          {interest.indicators && interest.indicators.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">
                Indicators
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {interest.indicators.map((ind) => (
                  <span
                    key={ind}
                    className="rounded bg-bg-primary px-2.5 py-1 text-sm text-gray-300"
                  >
                    {ind}
                  </span>
                ))}
              </div>
            </div>
          )}
          {interest.market_filters && interest.market_filters.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">
                Market Filters
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {interest.market_filters.map((filter) => (
                  <span
                    key={filter}
                    className="rounded bg-bg-primary px-2.5 py-1 text-sm text-gray-300"
                  >
                    {filter}
                  </span>
                ))}
              </div>
            </div>
          )}
          {!interest.indicators?.length && !interest.market_filters?.length && (
            <p className="text-sm text-gray-500">
              No indicators or market filters configured.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
