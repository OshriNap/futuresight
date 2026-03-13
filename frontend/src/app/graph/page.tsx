"use client";

export default function GraphPage() {
  return (
    <div className="space-y-6">
      {/* Info card */}
      <div className="card bg-gradient-to-r from-accent-blue/10 to-accent-purple/10 border-accent-blue/20">
        <h2 className="text-xl font-bold text-white">Event Relationship Graph</h2>
        <p className="mt-2 text-gray-400 max-w-2xl">
          Explore the interconnected web of predicted events. Nodes represent
          events and predictions, while edges show causal or correlative
          relationships between them.
        </p>
      </div>

      {/* Graph placeholder */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">
            Force-Directed Graph
          </h3>
          <div className="flex gap-2">
            <button className="btn-secondary text-xs">Zoom In</button>
            <button className="btn-secondary text-xs">Zoom Out</button>
            <button className="btn-secondary text-xs">Reset</button>
          </div>
        </div>

        <div className="flex h-[500px] items-center justify-center rounded-lg border border-dashed border-border bg-bg-primary">
          <div className="text-center max-w-md">
            <svg className="mx-auto w-16 h-16 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={0.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
            </svg>
            <h4 className="mt-4 text-lg font-medium text-gray-400">
              Interactive Event Graph
            </h4>
            <p className="mt-2 text-sm text-gray-500">
              This visualization uses react-force-graph to display a
              force-directed network of events and their relationships.
            </p>
            <div className="mt-6 space-y-2 text-left text-sm text-gray-500">
              <p className="flex items-center gap-2">
                <span className="inline-block h-3 w-3 rounded-full bg-accent-blue" />
                Nodes represent events and predictions
              </p>
              <p className="flex items-center gap-2">
                <span className="inline-block h-3 w-3 rounded-full bg-accent-purple" />
                Node size reflects confidence/importance
              </p>
              <p className="flex items-center gap-2">
                <span className="inline-block h-6 w-px bg-gray-500" />
                Edges represent causal relationships
              </p>
              <p className="flex items-center gap-2">
                <span className="inline-block h-6 w-px bg-accent-cyan" />
                Edge thickness reflects relationship strength
              </p>
            </div>
            <p className="mt-4 text-xs text-gray-600">
              Connect the API to load graph data from /api/graph
            </p>
          </div>
        </div>
      </div>

      {/* Graph stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="card">
          <p className="text-sm text-gray-400">Total Nodes</p>
          <p className="mt-1 text-xl font-bold text-white">--</p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-400">Total Edges</p>
          <p className="mt-1 text-xl font-bold text-white">--</p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-400">Clusters</p>
          <p className="mt-1 text-xl font-bold text-white">--</p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-400">Avg Connections</p>
          <p className="mt-1 text-xl font-bold text-white">--</p>
        </div>
      </div>
    </div>
  );
}
