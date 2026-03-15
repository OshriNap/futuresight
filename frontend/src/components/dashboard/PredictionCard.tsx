"use client";

import { useState } from "react";
import { Prediction } from "@/lib/types";

interface PredictionCardProps {
  prediction: Prediction;
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.7) return "bg-confidence-high";
  if (confidence >= 0.5) return "bg-confidence-medium";
  return "bg-confidence-low";
}

function getConfidenceTextColor(confidence: number): string {
  if (confidence >= 0.7) return "text-confidence-high";
  if (confidence >= 0.5) return "text-confidence-medium";
  return "text-confidence-low";
}

function getStatusBadge(status: string): string {
  switch (status) {
    case "active":
      return "badge-active";
    case "resolved":
      return "badge-resolved";
    case "expired":
      return "badge-expired";
    default:
      return "badge-expired";
  }
}

function getTimeHorizonLabel(horizon: string): string {
  switch (horizon) {
    case "short":
      return "Short-term";
    case "medium":
      return "Medium-term";
    case "long":
      return "Long-term";
    default:
      return horizon;
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function getReliabilityColor(score: number): string {
  if (score >= 0.7) return "bg-confidence-high";
  if (score >= 0.5) return "bg-confidence-medium";
  return "bg-confidence-low";
}

export default function PredictionCard({ prediction }: PredictionCardProps) {
  const [expanded, setExpanded] = useState(false);
  const confidencePercent = Math.round(prediction.confidence * 100);
  const factors = prediction.data_signals?.factors;
  const sources = prediction.data_signals?.sources;
  const hasDetails = prediction.reasoning || (factors && factors.length > 0) || (sources && sources.length > 0);

  return (
    <div
      className={`card-hover cursor-pointer transition-all ${expanded ? "ring-1 ring-accent-blue/30" : ""}`}
      onClick={() => hasDetails && setExpanded(!expanded)}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-white truncate">
            {prediction.title}
          </h3>
          <p className="mt-1 text-sm text-gray-400 line-clamp-2">
            {prediction.description}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={getStatusBadge(prediction.status)}>
            {prediction.status}
          </span>
          {hasDetails && (
            <svg
              className={`w-4 h-4 text-gray-500 transition-transform ${expanded ? "rotate-180" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
          )}
        </div>
      </div>

      {/* Confidence bar */}
      <div className="mt-4">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-400">Confidence</span>
          <span className={getConfidenceTextColor(prediction.confidence)}>
            {confidencePercent}%
          </span>
        </div>
        <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-bg-primary">
          <div
            className={`h-full rounded-full transition-all ${getConfidenceColor(prediction.confidence)}`}
            style={{ width: `${confidencePercent}%` }}
          />
        </div>
      </div>

      {/* Probability */}
      <div className="mt-3 flex items-center justify-between text-sm">
        <span className="text-gray-400">Probability</span>
        <span className="font-medium text-white">
          {Math.round(prediction.probability * 100)}%
        </span>
      </div>

      {/* Meta */}
      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-gray-500">
        <span className="rounded bg-bg-primary px-2 py-1">
          {getTimeHorizonLabel(prediction.time_horizon)}
        </span>
        {prediction.source && (
          <span className="rounded bg-bg-primary px-2 py-1">
            {prediction.source}
          </span>
        )}
        {prediction.agent_name && (
          <span className="rounded bg-accent-purple/10 px-2 py-1 text-accent-purple">
            {prediction.agent_name}
          </span>
        )}
        <span className="ml-auto">{formatDate(prediction.created_at)}</span>
      </div>

      {/* Expanded detail section */}
      {expanded && hasDetails && (
        <div className="mt-4 space-y-4 border-t border-border pt-4" onClick={(e) => e.stopPropagation()}>
          {/* Reasoning */}
          {prediction.reasoning && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">
                Reasoning
              </h4>
              <p className="text-sm text-gray-300 leading-relaxed">
                {prediction.reasoning}
              </p>
            </div>
          )}

          {/* Key Factors / Counterfactuals */}
          {factors && factors.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">
                Key Factors
              </h4>
              <div className="space-y-2">
                {factors.map((factor, i) => (
                  <div key={i} className="rounded-lg bg-bg-primary p-3">
                    <div className="flex items-start gap-2">
                      <span className="mt-0.5 flex-shrink-0">
                        {factor.direction === "supports" ? (
                          <svg className="w-4 h-4 text-confidence-high" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 10.5L12 3m0 0l7.5 7.5M12 3v18" />
                          </svg>
                        ) : factor.direction === "contradicts" ? (
                          <svg className="w-4 h-4 text-confidence-low" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 13.5L12 21m0 0l-7.5-7.5M12 21V3" />
                          </svg>
                        ) : (
                          <svg className="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14" />
                          </svg>
                        )}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm text-gray-200">{factor.signal}</p>
                          <span className="flex-shrink-0 text-xs text-gray-500">
                            {Math.round(factor.weight * 100)}%
                          </span>
                        </div>
                        {factor.counterfactual && (
                          <p className="mt-1 text-xs text-gray-500 italic">
                            {factor.counterfactual}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sources */}
          {sources && sources.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">
                Sources
              </h4>
              <div className="space-y-2">
                {sources.map((src, i) => (
                  <div key={i} className="flex items-center gap-3 rounded-lg bg-bg-primary p-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-gray-200">{src.name}</p>
                        <span className="rounded bg-bg-secondary px-1.5 py-0.5 text-xs text-gray-500">
                          {src.platform}
                        </span>
                      </div>
                      {src.signal && (
                        <p className="mt-0.5 text-xs text-gray-500">{src.signal}</p>
                      )}
                    </div>
                    <div className="flex-shrink-0 text-right">
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 overflow-hidden rounded-full bg-bg-secondary">
                          <div
                            className={`h-full rounded-full ${getReliabilityColor(src.reliability)}`}
                            style={{ width: `${Math.round(src.reliability * 100)}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-400 w-8 text-right">
                          {Math.round(src.reliability * 100)}%
                        </span>
                      </div>
                      {src.articles_used !== undefined && (
                        <p className="mt-0.5 text-xs text-gray-600">
                          {src.articles_used} articles
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tools used */}
          {prediction.data_signals?.tools_used && prediction.data_signals.tools_used.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              <span className="text-xs text-gray-600">Tools:</span>
              {prediction.data_signals.tools_used.map((tool) => (
                <span key={tool} className="rounded bg-accent-blue/10 px-2 py-0.5 text-xs text-accent-blue">
                  {tool.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
