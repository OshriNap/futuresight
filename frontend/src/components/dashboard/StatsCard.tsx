interface StatsCardProps {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  trend?: number;
  trendLabel?: string;
}

export default function StatsCard({
  icon,
  label,
  value,
  trend,
  trendLabel,
}: StatsCardProps) {
  return (
    <div className="card">
      <div className="flex items-start justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent-blue/10 text-accent-blue">
          {icon}
        </div>
        {trend !== undefined && (
          <span
            className={`flex items-center gap-1 text-xs font-medium ${
              trend >= 0 ? "text-confidence-high" : "text-confidence-low"
            }`}
          >
            {trend >= 0 ? (
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 19.5l15-15m0 0H8.25m11.25 0v11.25" />
              </svg>
            ) : (
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 4.5l15 15m0 0V8.25m0 11.25H8.25" />
              </svg>
            )}
            {Math.abs(trend)}%
          </span>
        )}
      </div>
      <div className="mt-4">
        <p className="text-2xl font-bold text-white">{value}</p>
        <p className="mt-1 text-sm text-gray-400">{label}</p>
        {trendLabel && (
          <p className="mt-1 text-xs text-gray-500">{trendLabel}</p>
        )}
      </div>
    </div>
  );
}
