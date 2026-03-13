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

export default function PredictionCard({ prediction }: PredictionCardProps) {
  const confidencePercent = Math.round(prediction.confidence * 100);

  return (
    <div className="card-hover">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-white truncate">
            {prediction.title}
          </h3>
          <p className="mt-1 text-sm text-gray-400 line-clamp-2">
            {prediction.description}
          </p>
        </div>
        <span className={getStatusBadge(prediction.status)}>
          {prediction.status}
        </span>
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
    </div>
  );
}
