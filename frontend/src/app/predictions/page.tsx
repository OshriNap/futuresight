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
    reasoning: "Multiple economic indicators point to the Fed holding rates steady. Core inflation remains at 2.8%, above the 2% target but showing a declining trend. Labor market data shows gradual cooling without sharp deterioration.",
    data_signals: {
      factors: [
        { signal: "Core inflation at 2.8%, declining trend over 3 months", direction: "supports", weight: 0.35, counterfactual: "If inflation were rising above 3.5%, probability of a rate hike would increase to ~60%" },
        { signal: "Unemployment at 4.1%, gradually rising", direction: "supports", weight: 0.25, counterfactual: "If unemployment spiked to 5%+, probability of a rate cut would increase to ~70%" },
        { signal: "GDP growth at 2.1%, moderate pace", direction: "supports", weight: 0.2, counterfactual: "If GDP contracted for 2 consecutive quarters, rate cut probability would jump to ~85%" },
        { signal: "Market pricing implies 82% chance of hold", direction: "supports", weight: 0.2, counterfactual: "If futures markets shifted to pricing a cut, our model would lower hold probability to ~55%" },
      ],
      sources: [
        { name: "Reddit r/economics", platform: "reddit", reliability: 0.62, articles_used: 45, signal: "Community sentiment leans toward rate hold" },
        { name: "GDELT News", platform: "gdelt", reliability: 0.74, articles_used: 128, signal: "News tone on Fed policy is neutral-to-dovish" },
        { name: "Federal Reserve Statements", platform: "official", reliability: 0.95, signal: "Latest FOMC minutes suggest patience" },
      ],
      method: "ensemble",
      tools_used: ["market_consensus", "trend_extrapolator", "llm_reasoner"],
    },
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
    reasoning: "The EU AI Act implementation is underway with several amendment proposals in committee. Political momentum exists but timeline is uncertain due to competing legislative priorities.",
    data_signals: {
      factors: [
        { signal: "3 amendment proposals currently in committee", direction: "supports", weight: 0.3, counterfactual: "Without active proposals, probability would drop to ~30%" },
        { signal: "EU Parliament elections may shift priorities", direction: "contradicts", weight: 0.25, counterfactual: "If no elections were pending, probability would rise to ~75%" },
        { signal: "Industry lobbying increasing against strict rules", direction: "contradicts", weight: 0.2, counterfactual: "Without industry opposition, probability would be ~80%" },
        { signal: "Public support for AI regulation at 68%", direction: "supports", weight: 0.25 },
      ],
      sources: [
        { name: "GDELT News", platform: "gdelt", reliability: 0.74, articles_used: 67, signal: "Strong coverage of EU AI regulatory activity" },
        { name: "Reddit r/technology", platform: "reddit", reliability: 0.58, articles_used: 23, signal: "Mixed sentiment on EU AI regulation effectiveness" },
      ],
      method: "ensemble",
      tools_used: ["trend_extrapolator", "llm_reasoner"],
    },
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
    reasoning: "New fab capacity coming online in Q3-Q4 2026 should ease shortages, but geopolitical tensions and demand surges from AI hardware create uncertainty.",
    data_signals: {
      factors: [
        { signal: "TSMC Arizona fab production starting Q3 2026", direction: "supports", weight: 0.3, counterfactual: "If fab delays occur, probability drops to ~35%" },
        { signal: "AI chip demand growing 40% YoY", direction: "contradicts", weight: 0.35, counterfactual: "If AI demand plateaued, probability would rise to ~70%" },
        { signal: "Taiwan Strait tensions elevated", direction: "contradicts", weight: 0.2, counterfactual: "If tensions de-escalated, probability would rise to ~65%" },
      ],
      sources: [
        { name: "GDELT News", platform: "gdelt", reliability: 0.74, articles_used: 89 },
        { name: "Reddit r/technology", platform: "reddit", reliability: 0.58, articles_used: 34, signal: "Industry insiders report mixed signals on supply" },
      ],
      method: "ensemble",
      tools_used: ["market_consensus", "advanced_extrapolator"],
    },
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
    reasoning: "Current unemployment at 4.1% with gradual upward trend. Job openings declining but layoffs remain contained. Historical patterns suggest slow deterioration rather than sharp spike.",
    data_signals: {
      factors: [
        { signal: "Job openings down 15% from peak", direction: "supports", weight: 0.3 },
        { signal: "Weekly jobless claims stable at 220k", direction: "contradicts", weight: 0.35, counterfactual: "If claims rose above 300k, probability would jump to ~65%" },
        { signal: "Consumer spending still resilient", direction: "contradicts", weight: 0.2 },
      ],
      sources: [
        { name: "GDELT News", platform: "gdelt", reliability: 0.74, articles_used: 56, signal: "Labor market coverage is cautiously optimistic" },
        { name: "Reddit r/economics", platform: "reddit", reliability: 0.62, articles_used: 18 },
      ],
      method: "ensemble",
      tools_used: ["base_rate", "trend_extrapolator"],
    },
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
    reasoning: "Post-halving cycle historically bullish, but current macro environment and regulatory uncertainty limit upside potential. ETF inflows provide a floor but institutional adoption pace is uncertain.",
    data_signals: {
      factors: [
        { signal: "Post-halving cycle (historically +200-400%)", direction: "supports", weight: 0.3, counterfactual: "Without halving cycle dynamics, probability would be ~10%" },
        { signal: "Spot ETF inflows slowing month-over-month", direction: "contradicts", weight: 0.25 },
        { signal: "Regulatory crackdown risk in multiple jurisdictions", direction: "contradicts", weight: 0.25, counterfactual: "If clear pro-crypto regulation passed, probability would rise to ~45%" },
        { signal: "On-chain metrics show accumulation phase", direction: "supports", weight: 0.2 },
      ],
      sources: [
        { name: "Reddit r/economics", platform: "reddit", reliability: 0.62, articles_used: 67, signal: "Mixed crypto sentiment, cautious optimism" },
        { name: "GDELT News", platform: "gdelt", reliability: 0.74, articles_used: 43, signal: "Crypto coverage tone slightly negative" },
      ],
      method: "ensemble",
      tools_used: ["market_consensus", "trend_extrapolator", "base_rate"],
    },
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
    reasoning: "Diplomatic channels were active with multiple mediators involved. International pressure and humanitarian concerns created strong incentives for agreement.",
    data_signals: {
      factors: [
        { signal: "Multiple mediator nations actively engaged", direction: "supports", weight: 0.35 },
        { signal: "Humanitarian crisis intensifying pressure", direction: "supports", weight: 0.3 },
        { signal: "Domestic political opposition to continued conflict", direction: "supports", weight: 0.2 },
        { signal: "Hardliner factions resisting compromise", direction: "contradicts", weight: 0.15 },
      ],
      sources: [
        { name: "GDELT News", platform: "gdelt", reliability: 0.74, articles_used: 312, signal: "Intensive coverage of diplomatic efforts" },
        { name: "Reddit r/worldnews", platform: "reddit", reliability: 0.55, articles_used: 89, signal: "Strong public sentiment for ceasefire" },
      ],
      method: "ensemble",
      tools_used: ["llm_reasoner", "market_consensus"],
    },
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
        const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://192.168.50.114";
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
            reasoning: p.reasoning || undefined,
            data_signals: p.data_signals || undefined,
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
