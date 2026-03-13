"use client";

import { useEffect, useState } from "react";
import PredictionCard from "@/components/dashboard/PredictionCard";
import { getPredictions } from "@/lib/api";
import { Prediction } from "@/lib/types";

const mockPredictions: Prediction[] = [
  {
    id: "1",
    title: "Federal Reserve interest rate decision",
    description: "The Federal Reserve will maintain current interest rates at the next FOMC meeting.",
    probability: 0.78,
    confidence: 0.85,
    time_horizon: "short",
    status: "active",
    source: "Economic Analysis",
    agent_name: "MacroEcon Agent",
    category: "Economics",
    created_at: "2026-03-12T10:30:00Z",
    updated_at: "2026-03-12T10:30:00Z",
  },
  {
    id: "2",
    title: "AI regulation framework in the EU",
    description: "The EU will pass additional AI regulation amendments by Q3 2026.",
    probability: 0.65,
    confidence: 0.6,
    time_horizon: "medium",
    status: "active",
    source: "Policy Watch",
    agent_name: "Policy Agent",
    category: "Technology",
    created_at: "2026-03-11T14:00:00Z",
    updated_at: "2026-03-11T14:00:00Z",
  },
  {
    id: "3",
    title: "Global semiconductor supply normalization",
    description: "Semiconductor supply chain disruptions will be largely resolved by end of year.",
    probability: 0.52,
    confidence: 0.45,
    time_horizon: "long",
    status: "active",
    source: "Tech Industry Analysis",
    agent_name: "Tech Agent",
    category: "Technology",
    created_at: "2026-03-10T09:15:00Z",
    updated_at: "2026-03-10T09:15:00Z",
  },
  {
    id: "4",
    title: "US unemployment rate above 4.5%",
    description: "US unemployment will exceed 4.5% within the next 6 months due to economic slowdown.",
    probability: 0.35,
    confidence: 0.55,
    time_horizon: "medium",
    status: "active",
    source: "Labor Market Monitor",
    category: "Economics",
    created_at: "2026-03-09T11:00:00Z",
    updated_at: "2026-03-09T11:00:00Z",
  },
  {
    id: "5",
    title: "Bitcoin exceeds $150k",
    description: "Bitcoin price will surpass $150,000 before the end of 2026.",
    probability: 0.28,
    confidence: 0.4,
    time_horizon: "long",
    status: "active",
    source: "Crypto Analysis",
    agent_name: "Finance Agent",
    category: "Finance",
    created_at: "2026-03-08T16:30:00Z",
    updated_at: "2026-03-08T16:30:00Z",
  },
  {
    id: "6",
    title: "Middle East ceasefire agreement",
    description: "A comprehensive ceasefire agreement was reached between the involved parties.",
    probability: 0.82,
    confidence: 0.88,
    time_horizon: "short",
    status: "resolved",
    source: "Geopolitical Watch",
    agent_name: "Geopolitics Agent",
    category: "Geopolitics",
    created_at: "2026-02-15T08:00:00Z",
    updated_at: "2026-03-05T12:00:00Z",
    resolution: true,
  },
];

type TimeHorizon = "all" | "short" | "medium" | "long";
type Status = "all" | "active" | "resolved" | "expired";

export default function PredictionsPage() {
  const [predictions, setPredictions] = useState<Prediction[]>(mockPredictions);
  const [timeHorizon, setTimeHorizon] = useState<TimeHorizon>("all");
  const [status, setStatus] = useState<Status>("all");
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    async function loadData() {
      try {
        const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const params = new URLSearchParams();
        if (timeHorizon !== "all") params.set("time_horizon", timeHorizon);
        const query = params.toString();
        const res = await fetch(`${API_BASE}/api/predictions/${query ? `?${query}` : ""}`);
        if (res.ok) {
          const data = await res.json();
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const mapped = (Array.isArray(data) ? data : []).map((p: any) => ({
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
          }));
          if (mapped.length > 0) setPredictions(mapped);
        }
      } catch {
        // Use mock data
      }
    }
    loadData();
  }, [timeHorizon, status]);

  const filtered = predictions.filter((p) => {
    if (timeHorizon !== "all" && p.time_horizon !== timeHorizon) return false;
    if (status !== "all" && p.status !== status) return false;
    if (
      searchQuery &&
      !p.title.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !p.description.toLowerCase().includes(searchQuery.toLowerCase())
    )
      return false;
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="card">
        <div className="flex flex-wrap items-center gap-4">
          {/* Search */}
          <div className="flex-1 min-w-[200px]">
            <input
              type="text"
              placeholder="Search predictions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-field"
            />
          </div>

          {/* Time horizon filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400">Horizon:</span>
            {(["all", "short", "medium", "long"] as TimeHorizon[]).map((h) => (
              <button
                key={h}
                onClick={() => setTimeHorizon(h)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                  timeHorizon === h
                    ? "bg-accent-blue text-white"
                    : "bg-bg-primary text-gray-400 hover:text-gray-200"
                }`}
              >
                {h === "all" ? "All" : h.charAt(0).toUpperCase() + h.slice(1)}
              </button>
            ))}
          </div>

          {/* Status filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400">Status:</span>
            {(["all", "active", "resolved", "expired"] as Status[]).map(
              (s) => (
                <button
                  key={s}
                  onClick={() => setStatus(s)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                    status === s
                      ? "bg-accent-blue text-white"
                      : "bg-bg-primary text-gray-400 hover:text-gray-200"
                  }`}
                >
                  {s === "all" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              )
            )}
          </div>
        </div>
      </div>

      {/* Results count */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-400">
          Showing <span className="text-white font-medium">{filtered.length}</span>{" "}
          predictions
        </p>
      </div>

      {/* Predictions grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {filtered.map((prediction) => (
          <PredictionCard key={prediction.id} prediction={prediction} />
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="card flex h-40 items-center justify-center">
          <p className="text-gray-500">
            No predictions match your filters.
          </p>
        </div>
      )}
    </div>
  );
}
