"use client";

export default function AccuracyPage() {
  const stats = [
    { label: "Overall Brier Score", value: "0.182", good: true },
    { label: "Calibration Error", value: "0.045", good: true },
    { label: "Resolution Score", value: "0.312", good: true },
    { label: "Total Scored", value: "856", good: null },
  ];

  const recentScores = [
    { category: "Economics", brier: 0.15, count: 234, accuracy: 78 },
    { category: "Technology", brier: 0.19, count: 189, accuracy: 72 },
    { category: "Geopolitics", brier: 0.22, count: 156, accuracy: 68 },
    { category: "Finance", brier: 0.21, count: 143, accuracy: 69 },
    { category: "Energy", brier: 0.17, count: 78, accuracy: 75 },
    { category: "Health", brier: 0.24, count: 56, accuracy: 64 },
  ];

  return (
    <div className="space-y-8">
      {/* Stats summary */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.label} className="card">
            <p className="text-sm text-gray-400">{stat.label}</p>
            <p
              className={`mt-2 text-2xl font-bold ${
                stat.good === true
                  ? "text-confidence-high"
                  : stat.good === false
                    ? "text-confidence-low"
                    : "text-white"
              }`}
            >
              {stat.value}
            </p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Calibration plot placeholder */}
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">
            Calibration Plot
          </h3>
          <div className="flex h-72 items-center justify-center rounded-lg border border-dashed border-border">
            <div className="text-center">
              <svg className="mx-auto w-12 h-12 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 3v18h18" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M7 17l4-8 4 4 4-10" />
              </svg>
              <p className="mt-3 text-sm text-gray-500">
                Calibration Plot
              </p>
              <p className="mt-1 text-xs text-gray-600">
                Shows predicted probability vs. actual outcome frequency.
                <br />
                A perfectly calibrated model follows the diagonal.
              </p>
            </div>
          </div>
        </div>

        {/* Accuracy over time placeholder */}
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">
            Accuracy Over Time
          </h3>
          <div className="flex h-72 items-center justify-center rounded-lg border border-dashed border-border">
            <div className="text-center">
              <svg className="mx-auto w-12 h-12 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
              </svg>
              <p className="mt-3 text-sm text-gray-500">
                Accuracy Trend
              </p>
              <p className="mt-1 text-xs text-gray-600">
                Brier score trend over time.
                <br />
                Lower is better. Connect API for live data.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Category breakdown */}
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4">
          Performance by Category
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border text-left">
                <th className="pb-3 text-sm font-medium text-gray-400">
                  Category
                </th>
                <th className="pb-3 text-sm font-medium text-gray-400">
                  Brier Score
                </th>
                <th className="pb-3 text-sm font-medium text-gray-400">
                  Accuracy
                </th>
                <th className="pb-3 text-sm font-medium text-gray-400">
                  Predictions
                </th>
                <th className="pb-3 text-sm font-medium text-gray-400">
                  Performance
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {recentScores.map((row) => (
                <tr key={row.category}>
                  <td className="py-3 text-sm font-medium text-white">
                    {row.category}
                  </td>
                  <td className="py-3 text-sm text-gray-300">
                    {row.brier.toFixed(3)}
                  </td>
                  <td
                    className={`py-3 text-sm font-medium ${
                      row.accuracy >= 70
                        ? "text-confidence-high"
                        : row.accuracy >= 50
                          ? "text-confidence-medium"
                          : "text-confidence-low"
                    }`}
                  >
                    {row.accuracy}%
                  </td>
                  <td className="py-3 text-sm text-gray-300">{row.count}</td>
                  <td className="py-3">
                    <div className="h-1.5 w-24 overflow-hidden rounded-full bg-bg-primary">
                      <div
                        className={`h-full rounded-full ${
                          row.accuracy >= 70
                            ? "bg-confidence-high"
                            : row.accuracy >= 50
                              ? "bg-confidence-medium"
                              : "bg-confidence-low"
                        }`}
                        style={{ width: `${row.accuracy}%` }}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
