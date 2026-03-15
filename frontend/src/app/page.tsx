"use client";

import { useEffect, useState } from "react";
import StatsCard from "@/components/dashboard/StatsCard";
import PredictionCard from "@/components/dashboard/PredictionCard";
import { Prediction } from "@/lib/types";

interface SystemStats {
  total_sources: number;
  total_predictions: number;
  scored_predictions: number;
  avg_brier_score: number | null;
  platforms: Record<string, number>;
}

interface DashboardData {
  total_predictions: number;
  total_sources: number;
  total_agents: number;
  avg_brier_score: number | null;
  predictions_by_horizon: Record<string, number>;
}

interface SentimentData {
  total_scored: number;
  total_sources: number;
  coverage_pct: number;
  avg_sentiment: number | null;
  by_label: Record<string, number>;
  by_platform: Record<string, { total: number; scored: number }>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function DashboardPage() {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [dashData, setDashData] = useState<DashboardData | null>(null);
  const [sentiment, setSentiment] = useState<SentimentData | null>(null);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [metaRes, dashRes, predsRes, sentRes] = await Promise.all([
          fetch(`${API_BASE}/api/meta/stats`),
          fetch(`${API_BASE}/api/dashboard/stats`),
          fetch(`${API_BASE}/api/predictions/`),
          fetch(`${API_BASE}/api/dashboard/sentiment`),
        ]);

        if (metaRes.ok) setStats(await metaRes.json());
        if (dashRes.ok) setDashData(await dashRes.json());
        if (sentRes.ok) setSentiment(await sentRes.json());

        if (predsRes.ok) {
          const predsData = await predsRes.json();
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const mapped = (Array.isArray(predsData) ? predsData : []).slice(0, 5).map((p: any) => ({
            id: p.id,
            title: p.prediction_text || "Prediction",
            description: p.reasoning || "",
            probability: p.confidence || 0.5,
            confidence: p.confidence || 0.5,
            time_horizon: p.time_horizon || "medium",
            status: "active" as const,
            source: "System",
            category: p.data_signals?.category || "general",
            created_at: p.created_at || new Date().toISOString(),
            updated_at: p.created_at || new Date().toISOString(),
            reasoning: p.reasoning || undefined,
            data_signals: p.data_signals || undefined,
          }));
          setPredictions(mapped);
        }
      } catch {
        // API unavailable
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const platformColors: Record<string, string> = {
    polymarket: "bg-purple-500",
    gdelt: "bg-blue-500",
    reddit: "bg-orange-500",
    simulated: "bg-gray-500",
  };

  const platformLabels: Record<string, string> = {
    polymarket: "Polymarket",
    gdelt: "GDELT News",
    reddit: "Reddit",
    simulated: "Simulated",
  };

  const totalSources = stats?.total_sources || dashData?.total_sources || 0;

  return (
    <div className="space-y-8">
      {/* Welcome section */}
      <div className="card bg-gradient-to-r from-accent-blue/10 to-accent-purple/10 border-accent-blue/20">
        <h2 className="text-2xl font-bold text-white">
          Welcome to FutureSight
        </h2>
        <p className="mt-2 text-gray-400 max-w-2xl">
          AI-powered prediction platform. Aggregating data from prediction markets, news, and social media to forecast future events.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <div className="text-gray-400">Loading dashboard data...</div>
        </div>
      ) : (
        <>
          {/* Stats grid */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatsCard
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 7.5h1.5m-1.5 3h1.5m-7.5 3h7.5m-7.5 3h7.5m3-9h3.375c.621 0 1.125.504 1.125 1.125V18a2.25 2.25 0 01-2.25 2.25M16.5 7.5V18a2.25 2.25 0 002.25 2.25M16.5 7.5V4.875c0-.621-.504-1.125-1.125-1.125H4.125C3.504 3.75 3 4.254 3 4.875V18a2.25 2.25 0 002.25 2.25h13.5M6 7.5h3v3H6v-3z" />
                </svg>
              }
              label="Data Sources"
              value={totalSources.toLocaleString()}
            />
            <StatsCard
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5" />
                </svg>
              }
              label="Predictions"
              value={stats?.total_predictions || dashData?.total_predictions || 0}
            />
            <StatsCard
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              }
              label="Scored"
              value={stats?.scored_predictions || 0}
            />
            <StatsCard
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                </svg>
              }
              label="Brier Score"
              value={stats?.avg_brier_score != null ? stats.avg_brier_score.toFixed(3) : "N/A"}
            />
          </div>

          <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
            {/* Recent predictions */}
            <div className="lg:col-span-2 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-white">
                  Recent Predictions
                </h3>
                <a
                  href="/predictions"
                  className="text-sm text-accent-blue hover:text-accent-blue/80 transition-colors"
                >
                  View all
                </a>
              </div>
              <div className="space-y-3">
                {predictions.length > 0 ? (
                  predictions.map((prediction) => (
                    <PredictionCard key={prediction.id} prediction={prediction} />
                  ))
                ) : (
                  <div className="card text-center py-8 text-gray-500">
                    No predictions yet. Data collectors are gathering sources.
                  </div>
                )}
              </div>
            </div>

            {/* Sidebar */}
            <div className="space-y-4">
              {/* Platform breakdown */}
              <h3 className="text-lg font-semibold text-white">Data Sources</h3>
              <div className="card space-y-4">
                {stats?.platforms && Object.entries(stats.platforms)
                  .sort(([, a], [, b]) => b - a)
                  .map(([platform, count]) => {
                    const pct = totalSources > 0 ? (count / totalSources) * 100 : 0;
                    return (
                      <div key={platform}>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-gray-300">
                            {platformLabels[platform] || platform}
                          </span>
                          <span className="text-gray-400">{count}</span>
                        </div>
                        <div className="h-2 w-full rounded-full bg-bg-primary">
                          <div
                            className={`h-full rounded-full ${platformColors[platform] || "bg-gray-500"}`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                {!stats?.platforms && (
                  <p className="text-sm text-gray-500">Loading platform data...</p>
                )}
              </div>

              {/* Prediction horizons */}
              {dashData?.predictions_by_horizon && Object.keys(dashData.predictions_by_horizon).length > 0 && (
                <div className="card space-y-3">
                  <h4 className="font-medium text-gray-300">By Time Horizon</h4>
                  {Object.entries(dashData.predictions_by_horizon).map(([horizon, count]) => (
                    <div key={horizon} className="flex items-center justify-between">
                      <span className="text-sm text-gray-400 capitalize">{horizon} term</span>
                      <span className="text-sm font-medium text-white">{count}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Sentiment */}
              {sentiment && sentiment.total_scored > 0 && (
                <div className="card space-y-3">
                  <h4 className="font-medium text-gray-300">Sentiment Analysis</h4>
                  <div className="flex items-baseline gap-2">
                    <span className={`text-2xl font-bold ${
                      (sentiment.avg_sentiment ?? 0) > 0.05 ? "text-green-400" :
                      (sentiment.avg_sentiment ?? 0) < -0.05 ? "text-red-400" : "text-gray-400"
                    }`}>
                      {(sentiment.avg_sentiment ?? 0) > 0 ? "+" : ""}{sentiment.avg_sentiment?.toFixed(3) ?? "0.000"}
                    </span>
                    <span className="text-xs text-gray-500">avg</span>
                  </div>
                  <div className="text-xs text-gray-500">
                    {sentiment.total_scored}/{sentiment.total_sources} sources ({sentiment.coverage_pct}%)
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    {Object.entries(sentiment.by_label).map(([label, count]) => (
                      <span
                        key={label}
                        className={`text-xs px-2 py-0.5 rounded-full ${
                          label === "positive" ? "bg-green-500/10 text-green-400" :
                          label === "negative" ? "bg-red-500/10 text-red-400" :
                          "bg-blue-500/10 text-blue-400"
                        }`}
                      >
                        {label}: {count}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* System health */}
              <div className="card space-y-3">
                <h4 className="font-medium text-gray-300">System Health</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Agents</span>
                    <span className="text-sm font-medium text-white">{dashData?.total_agents || 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Event Nodes</span>
                    <span className="text-sm font-medium text-white">{dashData?.total_event_nodes || 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Event Edges</span>
                    <span className="text-sm font-medium text-white">{dashData?.total_event_edges || 0}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
