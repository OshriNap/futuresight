"use client";

import { useEffect, useState } from "react";
import StatsCard from "@/components/dashboard/StatsCard";
import PredictionCard from "@/components/dashboard/PredictionCard";
import { getDashboardStats, getPredictions } from "@/lib/api";
import { DashboardStats, Prediction } from "@/lib/types";

const mockStats: DashboardStats = {
  total_predictions: 1247,
  active_predictions: 342,
  resolved_predictions: 856,
  average_accuracy: 0.73,
  average_brier_score: 0.18,
  active_sources: 24,
  active_agents: 8,
  predictions_today: 47,
  accuracy_trend: 3.2,
};

const mockPredictions: Prediction[] = [
  {
    id: "1",
    title: "Federal Reserve interest rate decision",
    description: "The Federal Reserve will maintain current interest rates at the next FOMC meeting, keeping rates unchanged.",
    probability: 0.78,
    confidence: 0.85,
    time_horizon: "short",
    status: "active",
    source: "Economic Analysis",
    agent_name: "MacroEcon Agent",
    category: "Economics",
    created_at: "2026-03-12T10:30:00Z",
    updated_at: "2026-03-12T10:30:00Z",
    tags: ["fed", "interest-rates", "monetary-policy"],
  },
  {
    id: "2",
    title: "AI regulation framework in the EU",
    description: "The EU will pass additional AI regulation amendments by Q3 2026 focusing on foundation model governance.",
    probability: 0.65,
    confidence: 0.6,
    time_horizon: "medium",
    status: "active",
    source: "Policy Watch",
    agent_name: "Policy Agent",
    category: "Technology",
    created_at: "2026-03-11T14:00:00Z",
    updated_at: "2026-03-11T14:00:00Z",
    tags: ["ai", "regulation", "eu"],
  },
  {
    id: "3",
    title: "Global semiconductor supply normalization",
    description: "Semiconductor supply chain disruptions will be largely resolved, with chip availability returning to pre-shortage levels.",
    probability: 0.52,
    confidence: 0.45,
    time_horizon: "long",
    status: "active",
    source: "Tech Industry Analysis",
    agent_name: "Tech Agent",
    category: "Technology",
    created_at: "2026-03-10T09:15:00Z",
    updated_at: "2026-03-10T09:15:00Z",
    tags: ["semiconductors", "supply-chain"],
  },
  {
    id: "4",
    title: "Renewable energy capacity milestone",
    description: "Global renewable energy capacity will surpass 50% of total electricity generation capacity.",
    probability: 0.71,
    confidence: 0.72,
    time_horizon: "long",
    status: "active",
    source: "Energy Monitor",
    category: "Energy",
    created_at: "2026-03-09T16:45:00Z",
    updated_at: "2026-03-09T16:45:00Z",
    tags: ["renewable", "energy", "climate"],
  },
];

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats>(mockStats);
  const [predictions, setPredictions] = useState<Prediction[]>(mockPredictions);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [statsData, predsData] = await Promise.all([
          getDashboardStats(),
          getPredictions({ page_size: 5 }),
        ]);
        setStats(statsData);
        setPredictions(predsData.items);
      } catch {
        // Use mock data on error (API not connected)
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div className="space-y-8">
      {/* Welcome section */}
      <div className="card bg-gradient-to-r from-accent-blue/10 to-accent-purple/10 border-accent-blue/20">
        <h2 className="text-2xl font-bold text-white">
          Welcome to FutureSight
        </h2>
        <p className="mt-2 text-gray-400 max-w-2xl">
          Your AI-powered prediction platform. Track forecasts, monitor agent
          performance, and explore the interconnected web of future events.
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatsCard
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5" />
            </svg>
          }
          label="Total Predictions"
          value={stats.total_predictions.toLocaleString()}
          trend={5.2}
          trendLabel="vs last week"
        />
        <StatsCard
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
          label="Average Accuracy"
          value={`${Math.round(stats.average_accuracy * 100)}%`}
          trend={stats.accuracy_trend}
          trendLabel="improving"
        />
        <StatsCard
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 7.5h1.5m-1.5 3h1.5m-7.5 3h7.5m-7.5 3h7.5m3-9h3.375c.621 0 1.125.504 1.125 1.125V18a2.25 2.25 0 01-2.25 2.25M16.5 7.5V18a2.25 2.25 0 002.25 2.25M16.5 7.5V4.875c0-.621-.504-1.125-1.125-1.125H4.125C3.504 3.75 3 4.254 3 4.875V18a2.25 2.25 0 002.25 2.25h13.5M6 7.5h3v3H6v-3z" />
            </svg>
          }
          label="Active Sources"
          value={stats.active_sources}
        />
        <StatsCard
          icon={
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
          }
          label="Active Agents"
          value={stats.active_agents}
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
            {predictions.map((prediction) => (
              <PredictionCard key={prediction.id} prediction={prediction} />
            ))}
          </div>
        </div>

        {/* Chart placeholder & quick stats */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-white">Quick Overview</h3>

          {/* Chart placeholder */}
          <div className="card flex h-52 items-center justify-center">
            <div className="text-center">
              <svg className="mx-auto w-10 h-10 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
              </svg>
              <p className="mt-2 text-sm text-gray-500">
                Accuracy chart
              </p>
              <p className="text-xs text-gray-600">
                Connect API for live data
              </p>
            </div>
          </div>

          {/* Quick stats */}
          <div className="card space-y-4">
            <h4 className="font-medium text-gray-300">Today&apos;s Activity</h4>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">New predictions</span>
                <span className="text-sm font-medium text-white">
                  {stats.predictions_today}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">
                  Avg Brier Score
                </span>
                <span className="text-sm font-medium text-confidence-high">
                  {stats.average_brier_score.toFixed(3)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">
                  Active predictions
                </span>
                <span className="text-sm font-medium text-white">
                  {stats.active_predictions}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Resolved</span>
                <span className="text-sm font-medium text-white">
                  {stats.resolved_predictions}
                </span>
              </div>
            </div>
          </div>

          {/* Distribution */}
          <div className="card space-y-3">
            <h4 className="font-medium text-gray-300">Confidence Distribution</h4>
            <div className="space-y-2">
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-confidence-high">High (&gt;70%)</span>
                  <span className="text-gray-400">45%</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-bg-primary">
                  <div className="h-full w-[45%] rounded-full bg-confidence-high" />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-confidence-medium">Medium (50-70%)</span>
                  <span className="text-gray-400">35%</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-bg-primary">
                  <div className="h-full w-[35%] rounded-full bg-confidence-medium" />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-confidence-low">Low (&lt;50%)</span>
                  <span className="text-gray-400">20%</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-bg-primary">
                  <div className="h-full w-[20%] rounded-full bg-confidence-low" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
