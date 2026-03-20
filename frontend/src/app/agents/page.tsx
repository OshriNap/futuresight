"use client";

import { useEffect, useState } from "react";
import { getAgents } from "@/lib/api";
import { Agent } from "@/lib/types";

const mockAgents: Agent[] = [
  {
    id: "1",
    name: "MacroEcon Agent",
    type: "specialist",
    model: "gpt-4",
    brier_score: 0.152,
    total_predictions: 312,
    resolved_predictions: 234,
    accuracy_rate: 0.78,
    active: true,
    created_at: "2025-12-01T00:00:00Z",
    last_active: "2026-03-13T08:00:00Z",
    description: "Specializes in macroeconomic forecasting including interest rates, GDP, and inflation.",
  },
  {
    id: "2",
    name: "Geopolitics Agent",
    type: "specialist",
    model: "claude-3.5-sonnet",
    brier_score: 0.198,
    total_predictions: 187,
    resolved_predictions: 156,
    accuracy_rate: 0.68,
    active: true,
    created_at: "2025-12-15T00:00:00Z",
    last_active: "2026-03-13T07:30:00Z",
    description: "Focuses on geopolitical events, conflicts, and international relations.",
  },
  {
    id: "3",
    name: "Tech Agent",
    type: "specialist",
    model: "gpt-4",
    brier_score: 0.175,
    total_predictions: 245,
    resolved_predictions: 189,
    accuracy_rate: 0.72,
    active: true,
    created_at: "2026-01-01T00:00:00Z",
    last_active: "2026-03-13T09:00:00Z",
    description: "Tracks technology trends, product launches, and industry developments.",
  },
  {
    id: "4",
    name: "Finance Agent",
    type: "specialist",
    model: "claude-3.5-sonnet",
    brier_score: 0.21,
    total_predictions: 198,
    resolved_predictions: 143,
    accuracy_rate: 0.69,
    active: true,
    created_at: "2026-01-15T00:00:00Z",
    last_active: "2026-03-12T22:00:00Z",
    description: "Analyzes financial markets, crypto, and investment opportunities.",
  },
  {
    id: "5",
    name: "Meta Forecaster",
    type: "aggregator",
    model: "gpt-4",
    brier_score: 0.14,
    total_predictions: 156,
    resolved_predictions: 120,
    accuracy_rate: 0.82,
    active: true,
    created_at: "2026-02-01T00:00:00Z",
    last_active: "2026-03-13T09:15:00Z",
    description: "Aggregates predictions from all specialist agents using weighted ensemble methods.",
  },
  {
    id: "6",
    name: "Policy Agent",
    type: "specialist",
    model: "claude-3.5-sonnet",
    brier_score: 0.188,
    total_predictions: 134,
    resolved_predictions: 98,
    accuracy_rate: 0.71,
    active: false,
    created_at: "2026-01-20T00:00:00Z",
    last_active: "2026-03-10T14:00:00Z",
    description: "Monitors government policy, regulation, and legislative developments.",
  },
];

function getBrierColor(score: number): string {
  if (score <= 0.15) return "text-confidence-high";
  if (score <= 0.2) return "text-confidence-medium";
  return "text-confidence-low";
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>(mockAgents);

  useEffect(() => {
    async function loadData() {
      try {
        const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://192.168.50.114";
        const res = await fetch(`${API_BASE}/api/agents`);
        if (res.ok) {
          const data = await res.json();
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const mapped = (Array.isArray(data) ? data : []).map((a: any) => ({
            id: a.id,
            name: a.name || "Agent",
            type: a.type || "specialist",
            model: a.model || undefined,
            brier_score: a.avg_brier_score ?? a.brier_score ?? 0,
            total_predictions: a.total_predictions ?? 0,
            resolved_predictions: a.resolved_predictions ?? 0,
            accuracy_rate: a.accuracy_rate ?? 0,
            active: a.active ?? true,
            created_at: a.created_at || new Date().toISOString(),
            last_active: a.last_active || undefined,
            description: a.description || undefined,
          }));
          if (mapped.length > 0) setAgents(mapped);
        }
      } catch {
        // Use mock data
      }
    }
    loadData();
  }, []);

  return (
    <div className="space-y-8">
      {/* Summary */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="card">
          <p className="text-sm text-gray-400">Total Agents</p>
          <p className="mt-2 text-2xl font-bold text-white">{agents.length}</p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-400">Active Agents</p>
          <p className="mt-2 text-2xl font-bold text-confidence-high">
            {agents.filter((a) => a.active).length}
          </p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-400">Best Brier Score</p>
          <p className="mt-2 text-2xl font-bold text-confidence-high">
            {Math.min(...agents.map((a) => a.brier_score ?? 0)).toFixed(3)}
          </p>
        </div>
      </div>

      {/* Performance comparison placeholder */}
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4">
          Performance Comparison
        </h3>
        <div className="flex h-48 items-center justify-center rounded-lg border border-dashed border-border">
          <div className="text-center">
            <svg className="mx-auto w-12 h-12 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
            </svg>
            <p className="mt-3 text-sm text-gray-500">
              Agent Performance Comparison Chart
            </p>
            <p className="mt-1 text-xs text-gray-600">
              Bar chart comparing Brier scores across agents.
              <br />
              Connect API for live data.
            </p>
          </div>
        </div>
      </div>

      {/* Agent cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {agents.map((agent) => (
          <div key={agent.id} className="card-hover">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div
                  className={`flex h-10 w-10 items-center justify-center rounded-lg ${
                    agent.type === "aggregator"
                      ? "bg-accent-purple/10 text-accent-purple"
                      : "bg-accent-blue/10 text-accent-blue"
                  }`}
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-medium text-white">{agent.name}</h3>
                  <p className="text-xs text-gray-500">
                    {agent.type} {agent.model && `/ ${agent.model}`}
                  </p>
                </div>
              </div>
              <span
                className={`inline-flex h-2 w-2 rounded-full ${
                  agent.active ? "bg-green-500" : "bg-gray-500"
                }`}
              />
            </div>

            {agent.description && (
              <p className="mt-3 text-sm text-gray-400 line-clamp-2">
                {agent.description}
              </p>
            )}

            <div className="mt-4 grid grid-cols-2 gap-3">
              <div>
                <p className="text-xs text-gray-500">Brier Score</p>
                <p
                  className={`text-lg font-bold ${getBrierColor(agent.brier_score)}`}
                >
                  {(agent.brier_score ?? 0).toFixed(3)}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Accuracy</p>
                <p className="text-lg font-bold text-white">
                  {Math.round((agent.accuracy_rate ?? 0) * 100)}%
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Total Predictions</p>
                <p className="text-sm font-medium text-gray-300">
                  {agent.total_predictions}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Resolved</p>
                <p className="text-sm font-medium text-gray-300">
                  {agent.resolved_predictions}
                </p>
              </div>
            </div>

            {/* Accuracy bar */}
            <div className="mt-4">
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-bg-primary">
                <div
                  className={`h-full rounded-full ${
                    (agent.accuracy_rate ?? 0) >= 0.7
                      ? "bg-confidence-high"
                      : (agent.accuracy_rate ?? 0) >= 0.5
                        ? "bg-confidence-medium"
                        : "bg-confidence-low"
                  }`}
                  style={{ width: `${(agent.accuracy_rate ?? 0) * 100}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
