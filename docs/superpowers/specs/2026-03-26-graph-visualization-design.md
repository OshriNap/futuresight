# Graph Visualization — Interactive 3-Mode Dashboard Tab

## Problem

The Event Graph tab in the dashboard HTML SPA renders a static SVG circle layout with no pan, zoom, or interaction. With 8,961 nodes and 8,947 edges, it's useless — just a blob of overlapping circles.

## Solution

Replace the static SVG with an interactive Cytoscape.js graph with three switchable view modes: Hubs, Clusters, and Search. Add new API endpoints to serve filtered subgraphs so the browser never loads all 9k nodes at once.

## JS Library: Cytoscape.js

Cytoscape.js via CDN (`<script>` tag, no build step). Chosen over D3-force because:
- Built-in compound/parent nodes (needed for cluster view)
- Built-in pan/zoom, box selection, event handling
- Cola/COSE layout algorithms out of the box
- Works inline in the dashboard HTML SPA

## View Modes

### 1. Hubs (default)

**What it shows:** Top 20 most-connected nodes + all edges between them and their direct neighbors.

**API:** `GET /api/graph/hubs?limit=20&min_strength=0.1`
- Returns nodes ranked by edge count (outgoing + incoming)
- Includes all edges where at least one endpoint is a hub node
- Response: `GraphResponse` (same schema as existing)

**Interactions:**
- Click node → expand its 1-hop neighborhood (fetches `/api/graph/node/{id}/expand?hops=1`)
- Double-click node → re-center graph on that node, collapse others
- Hover node → tooltip with title, event_type, confidence, connection count
- Hover edge → tooltip with relationship_type, strength, reasoning

**Layout:** COSE (compound spring-embedded) — organic force-directed.

### 2. Clusters

**What it shows:** 5 super-nodes (one per event_type), sized by node count, with edges between them showing inter-cluster relationship counts.

**API:** `GET /api/graph/clusters`
- Returns aggregated data:
  ```json
  {
    "clusters": [
      {"event_type": "geopolitical", "node_count": 2341, "edge_count": 1823},
      ...
    ],
    "inter_cluster_edges": [
      {"source_type": "geopolitical", "target_type": "economic", "count": 412, "dominant_relationship": "causes"},
      ...
    ]
  }
  ```

**Interactions:**
- Click cluster → expand into individual nodes for that event_type (fetches `/api/graph/hubs?limit=30&event_type=geopolitical`)
- Hover cluster → tooltip with node count, edge count, top event titles

**Layout:** Circle layout for the 5 clusters, COSE when expanded.

### 3. Search

**What it shows:** Empty initially. User types a search query, sees matching nodes + their N-hop neighborhood.

**API:** `GET /api/graph/search?q=fed+rates&hops=2&limit=50`
- Text search against node titles (case-insensitive LIKE)
- For each matching node, expand N hops (reuses existing traversal logic)
- Deduplicates nodes/edges across matches
- Response: `GraphResponse`

**Interactions:**
- Type in search bar → debounced API call (300ms)
- Hop depth slider (1-3, default 2)
- Click node → expand further
- Clear button to reset

**Layout:** COSE centered on search results.

## Shared UI Elements

### Top Bar
- View mode toggle: [Hubs] [Clusters] [Search] — pill buttons
- Legend: colored dots for event_type (geopolitical=red, economic=amber, tech=cyan, social=purple, environmental=green)
- Relationship filter dropdown: All / causes / amplifies / mitigates / correlates / precedes
- Strength slider: min strength threshold (0.1 to 0.9)

### Graph Canvas
- Full-width Cytoscape container, ~500px height
- Nodes colored by event_type, sized by connection count
- Edges colored by relationship_type: causes=green, amplifies=blue, mitigates=red, correlates=gray, precedes=amber
- Edge width scaled by strength
- Edge arrows showing directionality (source → target)

### Bottom Stats Bar
- "Showing X of Y nodes" · "Edges: Z" · "Pan: drag · Zoom: scroll · Expand: click"

### Tooltips
- Node: title, event_type, confidence, connection count
- Edge: source → target, relationship_type, strength, reasoning text

## API Endpoints (New)

All added to `backend/app/api/event_graph.py`, reusing existing `GraphResponse` schema where possible.

### `GET /api/graph/hubs`

Query params: `limit` (default 20, max 50), `min_strength` (default 0.1), `event_type` (optional filter), `relationship_type` (optional filter)

Logic:
1. Count edges per node (both directions) via SQL
2. Take top N by edge count
3. Fetch all edges where at least one endpoint is in the hub set, filtered by min_strength and relationship_type
4. Fetch all nodes referenced by those edges (hubs + their neighbors)

### `GET /api/graph/clusters`

No query params.

Logic:
1. Count nodes per event_type
2. Count edges per event_type (both endpoints in same type)
3. Count inter-cluster edges: group by (source_event_type, target_event_type), return counts and dominant relationship

### `GET /api/graph/search`

Query params: `q` (search string, required), `hops` (default 2, max 3), `limit` (default 50, max 100), `min_strength` (default 0.1), `relationship_type` (optional)

Logic:
1. Find nodes where title ILIKE `%q%`, limit to 10 direct matches
2. For each match, traverse N hops (reuse existing traversal logic from `/node/{id}/connections`)
3. Merge and deduplicate all nodes/edges
4. Apply min_strength and relationship_type filters to edges
5. Return as GraphResponse

### `GET /api/graph/node/{id}/expand` (modify existing)

Already exists as `/node/{id}/connections`. Add `min_strength` and `relationship_type` query params for filtering.

## Dashboard HTML Changes

Replace `loaders.graph` function (lines 553-665 of dashboard.html) with:
1. Cytoscape.js `<script>` tag in the `<head>` (CDN)
2. New `loaders.graph` that renders the top bar, Cytoscape container, and bottom stats
3. View mode switching logic
4. Cytoscape initialization with COSE layout
5. Event handlers for click/hover/search

## Files to Change

| File | Change |
|------|--------|
| `backend/app/api/event_graph.py` | Add `/hubs`, `/clusters`, `/search` endpoints; add filters to existing `/node/{id}/connections` |
| `backend/app/dashboard.html` | Replace graph tab with Cytoscape.js interactive visualization |

## Out of Scope

- Next.js frontend graph page (separate effort)
- Persisting graph layout positions
- User-created manual edges
- Graph editing/annotation
