# Graph Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static SVG graph tab with an interactive Cytoscape.js visualization featuring 3 view modes (Hubs, Clusters, Search) and filtered subgraph API endpoints.

**Architecture:** New API endpoints serve filtered subgraphs (hubs by connection count, clusters by event_type aggregation, search by title matching + hop traversal). Dashboard HTML loads Cytoscape.js via CDN and renders an interactive force-directed graph with view mode switching, tooltips, and expand-on-click.

**Tech Stack:** Cytoscape.js (CDN), FastAPI, SQLAlchemy async, existing dashboard HTML SPA

---

### Task 1: Add `/api/graph/hubs` Endpoint

**Files:**
- Modify: `backend/app/api/event_graph.py`

- [ ] **Step 1: Add the hubs endpoint after the existing `/` endpoint**

Add after line 74 of `event_graph.py`:

```python
@router.get("/hubs", response_model=GraphResponse)
async def get_hub_nodes(
    limit: int = Query(default=20, le=50),
    min_strength: float = Query(default=0.1, ge=0.0, le=1.0),
    event_type: str | None = None,
    relationship_type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get the most-connected nodes and their neighborhoods."""
    from sqlalchemy import func, union_all

    # Count edges per node (both directions)
    out_counts = (
        select(EventEdge.source_node_id.label("node_id"), func.count().label("cnt"))
        .group_by(EventEdge.source_node_id)
    )
    in_counts = (
        select(EventEdge.target_node_id.label("node_id"), func.count().label("cnt"))
        .group_by(EventEdge.target_node_id)
    )
    combined = union_all(out_counts, in_counts).subquery()
    hub_query = (
        select(combined.c.node_id, func.sum(combined.c.cnt).label("total"))
        .group_by(combined.c.node_id)
        .order_by(func.sum(combined.c.cnt).desc())
        .limit(limit)
    )

    hub_result = await db.execute(hub_query)
    hub_ids = {row.node_id for row in hub_result.all()}

    if not hub_ids:
        return GraphResponse(nodes=[], edges=[])

    # Get edges where at least one endpoint is a hub
    edge_query = (
        select(EventEdge)
        .where(
            (EventEdge.source_node_id.in_(hub_ids)) | (EventEdge.target_node_id.in_(hub_ids))
        )
        .where(EventEdge.strength >= min_strength)
    )
    if relationship_type:
        edge_query = edge_query.where(EventEdge.relationship_type == relationship_type)

    edges_result = await db.execute(edge_query)
    edges = edges_result.scalars().all()

    # Collect all node IDs referenced by edges
    all_node_ids = set(hub_ids)
    for e in edges:
        all_node_ids.add(e.source_node_id)
        all_node_ids.add(e.target_node_id)

    # Fetch nodes
    node_query = select(EventNode).where(EventNode.id.in_(all_node_ids))
    if event_type:
        node_query = node_query.where(EventNode.event_type == event_type)
    nodes_result = await db.execute(node_query)
    nodes = nodes_result.scalars().all()

    # Re-filter edges to only include nodes we actually returned
    returned_ids = {n.id for n in nodes}
    edges = [e for e in edges if e.source_node_id in returned_ids and e.target_node_id in returned_ids]

    return GraphResponse(nodes=nodes, edges=edges)
```

- [ ] **Step 2: Verify endpoint loads**

Run: `cd /home/oshrin/projects/future_prediction/backend && python3 -c "from app.api.event_graph import router; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Test against live API**

Run: `curl -s 'http://localhost:8000/api/graph/hubs?limit=5' | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'nodes={len(d[\"nodes\"])}, edges={len(d[\"edges\"])}')" `
Expected: nodes and edges counts > 0

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/event_graph.py
git commit -m "feat: add /api/graph/hubs endpoint for most-connected nodes"
```

---

### Task 2: Add `/api/graph/clusters` Endpoint

**Files:**
- Modify: `backend/app/api/event_graph.py`

- [ ] **Step 1: Add clusters response model and endpoint**

Add after the hubs endpoint:

```python
class ClusterInfo(BaseModel):
    event_type: str
    node_count: int
    edge_count: int

class InterClusterEdge(BaseModel):
    source_type: str
    target_type: str
    count: int
    dominant_relationship: str

class ClusterResponse(BaseModel):
    clusters: list[ClusterInfo]
    inter_cluster_edges: list[InterClusterEdge]


@router.get("/clusters", response_model=ClusterResponse)
async def get_clusters(db: AsyncSession = Depends(get_db)):
    """Get aggregated cluster view — nodes grouped by event_type."""
    from sqlalchemy import func

    # Count nodes per event_type
    node_counts = await db.execute(
        select(EventNode.event_type, func.count(EventNode.id))
        .group_by(EventNode.event_type)
    )
    node_count_map = {row[0]: row[1] for row in node_counts.all()}

    # Count intra-cluster edges per event_type
    # Join edges to both source and target nodes to get their types
    src_alias = select(EventNode.id, EventNode.event_type).subquery("src")
    tgt_alias = select(EventNode.id, EventNode.event_type).subquery("tgt")

    edge_types_query = (
        select(
            src_alias.c.event_type.label("src_type"),
            tgt_alias.c.event_type.label("tgt_type"),
            EventEdge.relationship_type,
            func.count().label("cnt"),
        )
        .join(src_alias, EventEdge.source_node_id == src_alias.c.id)
        .join(tgt_alias, EventEdge.target_node_id == tgt_alias.c.id)
        .group_by(src_alias.c.event_type, tgt_alias.c.event_type, EventEdge.relationship_type)
    )
    edge_types_result = await db.execute(edge_types_query)
    rows = edge_types_result.all()

    # Build intra counts and inter-cluster edges
    intra_counts: dict[str, int] = {}
    inter_raw: dict[tuple[str, str], dict[str, int]] = {}

    for src_type, tgt_type, rel_type, cnt in rows:
        if src_type == tgt_type:
            intra_counts[src_type] = intra_counts.get(src_type, 0) + cnt
        else:
            key = (src_type, tgt_type)
            if key not in inter_raw:
                inter_raw[key] = {}
            inter_raw[key][rel_type] = inter_raw[key].get(rel_type, 0) + cnt

    clusters = [
        ClusterInfo(
            event_type=et,
            node_count=nc,
            edge_count=intra_counts.get(et, 0),
        )
        for et, nc in node_count_map.items()
    ]

    inter_edges = []
    for (src_t, tgt_t), rels in inter_raw.items():
        total = sum(rels.values())
        dominant = max(rels, key=rels.get)
        inter_edges.append(InterClusterEdge(
            source_type=src_t,
            target_type=tgt_t,
            count=total,
            dominant_relationship=dominant,
        ))

    return ClusterResponse(clusters=clusters, inter_cluster_edges=inter_edges)
```

- [ ] **Step 2: Test against live API**

Run: `curl -s 'http://localhost:8000/api/graph/clusters' | python3 -m json.tool | head -20`
Expected: JSON with clusters array and inter_cluster_edges

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/event_graph.py
git commit -m "feat: add /api/graph/clusters endpoint for aggregated cluster view"
```

---

### Task 3: Add `/api/graph/search` Endpoint

**Files:**
- Modify: `backend/app/api/event_graph.py`

- [ ] **Step 1: Add search endpoint**

Add after the clusters endpoint:

```python
@router.get("/search", response_model=GraphResponse)
async def search_graph(
    q: str = Query(min_length=2, max_length=200),
    hops: int = Query(default=2, ge=1, le=3),
    limit: int = Query(default=50, le=100),
    min_strength: float = Query(default=0.1, ge=0.0, le=1.0),
    relationship_type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Search for nodes by title and return their N-hop neighborhood."""
    # Find matching nodes
    match_result = await db.execute(
        select(EventNode)
        .where(EventNode.title.ilike(f"%{q}%"))
        .limit(10)
    )
    match_nodes = match_result.scalars().all()

    if not match_nodes:
        return GraphResponse(nodes=[], edges=[])

    # Traverse N hops from each match
    visited_ids = set()
    current_ids = {n.id for n in match_nodes}
    all_edges = []

    for _ in range(hops):
        if not current_ids:
            break
        edge_query = (
            select(EventEdge)
            .where(
                (EventEdge.source_node_id.in_(current_ids)) | (EventEdge.target_node_id.in_(current_ids))
            )
            .where(EventEdge.strength >= min_strength)
        )
        if relationship_type:
            edge_query = edge_query.where(EventEdge.relationship_type == relationship_type)

        edges_result = await db.execute(edge_query)
        new_edges = edges_result.scalars().all()
        all_edges.extend(new_edges)

        next_ids = set()
        for e in new_edges:
            next_ids.add(e.source_node_id)
            next_ids.add(e.target_node_id)
        visited_ids.update(current_ids)
        current_ids = next_ids - visited_ids

    # Fetch all referenced nodes
    all_node_ids = visited_ids | current_ids
    if all_node_ids:
        nodes_result = await db.execute(
            select(EventNode).where(EventNode.id.in_(all_node_ids))
        )
        all_nodes = list(nodes_result.scalars().all())[:limit]
    else:
        all_nodes = list(match_nodes)

    # Deduplicate edges
    seen_edges = set()
    deduped_edges = []
    for e in all_edges:
        if e.id not in seen_edges:
            seen_edges.add(e.id)
            deduped_edges.append(e)

    # Filter edges to returned nodes only
    returned_ids = {n.id for n in all_nodes}
    deduped_edges = [e for e in deduped_edges if e.source_node_id in returned_ids and e.target_node_id in returned_ids]

    return GraphResponse(nodes=all_nodes, edges=deduped_edges)
```

- [ ] **Step 2: Add min_strength and relationship_type filters to existing `/node/{id}/connections`**

Replace the existing `get_node_connections` function:

```python
@router.get("/node/{node_id}/connections", response_model=GraphResponse)
async def get_node_connections(
    node_id: uuid.UUID,
    depth: int = Query(default=2, le=5),
    min_strength: float = Query(default=0.0, ge=0.0, le=1.0),
    relationship_type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get a node and its connections up to N hops deep."""
    visited_ids = set()
    current_ids = {node_id}
    all_edges = []

    for _ in range(depth):
        if not current_ids:
            break
        edge_query = (
            select(EventEdge)
            .where(
                EventEdge.source_node_id.in_(current_ids) | EventEdge.target_node_id.in_(current_ids)
            )
            .where(EventEdge.strength >= min_strength)
        )
        if relationship_type:
            edge_query = edge_query.where(EventEdge.relationship_type == relationship_type)

        edges_result = await db.execute(edge_query)
        new_edges = edges_result.scalars().all()
        all_edges.extend(new_edges)

        next_ids = set()
        for e in new_edges:
            next_ids.add(e.source_node_id)
            next_ids.add(e.target_node_id)
        visited_ids.update(current_ids)
        current_ids = next_ids - visited_ids

    all_node_ids = visited_ids | current_ids
    all_nodes = []
    if all_node_ids:
        nodes_result = await db.execute(select(EventNode).where(EventNode.id.in_(all_node_ids)))
        all_nodes = nodes_result.scalars().all()

    return GraphResponse(nodes=all_nodes, edges=all_edges)
```

- [ ] **Step 3: Test search**

Run: `curl -s 'http://localhost:8000/api/graph/search?q=climate&hops=1' | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'nodes={len(d[\"nodes\"])}, edges={len(d[\"edges\"])}')" `
Expected: nodes and edges counts > 0

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/event_graph.py
git commit -m "feat: add /api/graph/search endpoint and filters to /node/{id}/connections"
```

---

### Task 4: Replace Dashboard Graph Tab with Cytoscape.js

**Files:**
- Modify: `backend/app/dashboard.html`

This is the main task — replaces the entire graph tab rendering (lines 553-665 of dashboard.html).

- [ ] **Step 1: Add Cytoscape.js CDN script tag**

In `dashboard.html`, add after the `<title>` tag (line 6):

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.30.4/cytoscape.min.js"></script>
```

- [ ] **Step 2: Replace the graph loader function**

Replace the entire `loaders.graph` function (from `// ── Event Graph ──` at line 553 through line 665, ending just before `// ── Interests ──`) with:

```javascript
// ── Event Graph ──
loaders.graph = async () => {
  const typeColor = {geopolitical:'#ef4444',economic:'#f59e0b',tech:'#06b6d4',social:'#a855f7',environmental:'#22c55e'};
  const relColor = {causes:'#22c55e',amplifies:'#3b82f6',mitigates:'#ef4444',correlates:'#6b7280',precedes:'#f59e0b'};
  let cy = null;
  let currentMode = 'hubs';

  const container = document.getElementById('tab-graph');
  container.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
      <div style="display:flex;gap:4px" id="graph-mode-btns">
        <button class="btn btn-p btn-sm" data-mode="hubs" onclick="switchGraphMode('hubs')">Hubs</button>
        <button class="btn btn-sm" data-mode="clusters" onclick="switchGraphMode('clusters')">Clusters</button>
        <button class="btn btn-sm" data-mode="search" onclick="switchGraphMode('search')">Search</button>
      </div>
      <div style="display:flex;gap:12px;align-items:center;font-size:11px">
        ${Object.entries(typeColor).map(([t,c]) => `<span><span class="dot" style="background:${c}"></span>${t}</span>`).join('')}
        <select id="graph-rel-filter" onchange="reloadGraph()" style="background:var(--bg3);color:var(--text);border:1px solid var(--border);border-radius:4px;padding:2px 6px;font-size:11px">
          <option value="">All relationships</option>
          <option value="causes">causes</option>
          <option value="amplifies">amplifies</option>
          <option value="mitigates">mitigates</option>
          <option value="correlates">correlates</option>
          <option value="precedes">precedes</option>
        </select>
        <label style="color:var(--text3)">Min str:
          <input id="graph-str-slider" type="range" min="0" max="90" value="10" onchange="reloadGraph()" style="width:80px;vertical-align:middle">
          <span id="graph-str-val">0.1</span>
        </label>
      </div>
    </div>
    <div id="graph-search-bar" style="display:none;margin-bottom:12px">
      <div style="display:flex;gap:8px;align-items:center">
        <input id="graph-search-input" type="text" placeholder="Search events..." style="flex:1;background:var(--bg3);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:8px 12px;font-size:13px" oninput="debounceSearch()">
        <label style="font-size:11px;color:var(--text3)">Hops:
          <select id="graph-hops" onchange="debounceSearch()" style="background:var(--bg3);color:var(--text);border:1px solid var(--border);border-radius:4px;padding:2px;font-size:11px">
            <option value="1">1</option>
            <option value="2" selected>2</option>
            <option value="3">3</option>
          </select>
        </label>
        <button class="btn btn-sm" onclick="document.getElementById('graph-search-input').value='';reloadGraph()">Clear</button>
      </div>
    </div>
    <div id="cy" style="width:100%;height:500px;background:var(--bg);border:1px solid var(--border);border-radius:8px"></div>
    <div id="graph-stats" style="display:flex;gap:24px;padding:8px 0;font-size:11px;color:var(--text3)"></div>
    <div id="graph-tooltip" style="display:none;position:fixed;background:rgba(10,10,15,0.95);border:1px solid var(--border);border-radius:8px;padding:12px;font-size:12px;max-width:300px;z-index:1000;pointer-events:none"></div>
  `;

  function getFilters() {
    const rel = document.getElementById('graph-rel-filter')?.value || '';
    const strVal = (document.getElementById('graph-str-slider')?.value || 10) / 100;
    document.getElementById('graph-str-val').textContent = strVal.toFixed(1);
    return { rel, minStr: strVal };
  }

  function initCy(elements) {
    if (cy) cy.destroy();
    cy = cytoscape({
      container: document.getElementById('cy'),
      elements: elements,
      style: [
        { selector: 'node', style: {
          'background-color': 'data(color)',
          'label': 'data(label)',
          'font-size': '9px',
          'color': '#ccc',
          'text-outline-color': '#0a0a0f',
          'text-outline-width': 2,
          'text-valign': 'bottom',
          'text-margin-y': 4,
          'width': 'data(size)',
          'height': 'data(size)',
          'border-width': 1,
          'border-color': 'data(color)',
          'border-opacity': 0.5,
        }},
        { selector: 'node.hub', style: {
          'font-size': '10px',
          'font-weight': 'bold',
          'border-width': 2,
        }},
        { selector: 'node.cluster-node', style: {
          'shape': 'round-rectangle',
          'width': 'data(size)',
          'height': 'data(size)',
          'font-size': '14px',
          'font-weight': 'bold',
          'text-valign': 'center',
          'text-halign': 'center',
          'background-opacity': 0.3,
          'border-width': 3,
        }},
        { selector: 'node.search-match', style: {
          'border-width': 3,
          'border-color': '#4a9eff',
          'border-style': 'double',
        }},
        { selector: 'edge', style: {
          'width': 'data(width)',
          'line-color': 'data(color)',
          'target-arrow-color': 'data(color)',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'opacity': 0.6,
          'arrow-scale': 0.8,
        }},
        { selector: 'edge.cluster-edge', style: {
          'width': 'data(width)',
          'curve-style': 'bezier',
          'line-style': 'dashed',
          'opacity': 0.8,
          'arrow-scale': 1.2,
        }},
      ],
      layout: { name: 'cose', animate: true, animationDuration: 800, nodeRepulsion: 8000, idealEdgeLength: 120, gravity: 0.3 },
      minZoom: 0.2,
      maxZoom: 5,
    });

    // Tooltips
    const tooltip = document.getElementById('graph-tooltip');
    cy.on('mouseover', 'node', e => {
      const d = e.target.data();
      tooltip.innerHTML = `<div style="font-weight:600;color:white;margin-bottom:4px">${d.fullTitle || d.label}</div>
        <div style="color:#888;margin-bottom:6px">${d.eventType || ''} ${d.confidence != null ? ' · '+Math.round(d.confidence*100)+'%' : ''}</div>
        <div style="color:#aaa">Connections: ${e.target.degree()}</div>
        ${d.nodeCount ? `<div style="color:#aaa">Nodes: ${d.nodeCount} · Edges: ${d.edgeCount}</div>` : ''}
        <div style="color:#666;margin-top:6px;font-size:10px">Click to expand</div>`;
      tooltip.style.display = 'block';
    });
    cy.on('mousemove', 'node', e => {
      tooltip.style.left = e.originalEvent.clientX + 12 + 'px';
      tooltip.style.top = e.originalEvent.clientY + 12 + 'px';
    });
    cy.on('mouseout', 'node', () => { tooltip.style.display = 'none'; });

    cy.on('mouseover', 'edge', e => {
      const d = e.target.data();
      tooltip.innerHTML = `<div style="color:white">${d.relType}</div>
        <div style="color:#aaa">Strength: ${d.strength != null ? (d.strength*100).toFixed(0)+'%' : d.count||''}</div>
        ${d.reasoning ? `<div style="color:#666;margin-top:4px;font-size:11px">${d.reasoning}</div>` : ''}`;
      tooltip.style.display = 'block';
    });
    cy.on('mousemove', 'edge', e => {
      tooltip.style.left = e.originalEvent.clientX + 12 + 'px';
      tooltip.style.top = e.originalEvent.clientY + 12 + 'px';
    });
    cy.on('mouseout', 'edge', () => { tooltip.style.display = 'none'; });

    // Click to expand
    cy.on('tap', 'node', async e => {
      const d = e.target.data();
      if (d.clusterId) {
        // Cluster click — load hubs for this event_type
        await loadHubs(d.clusterId);
        return;
      }
      if (!d.nodeId) return;
      const f = getFilters();
      let url = `/api/graph/node/${d.nodeId}/connections?depth=1&min_strength=${f.minStr}`;
      if (f.rel) url += `&relationship_type=${f.rel}`;
      const data = await api(url);
      const newEls = graphDataToElements(data, []);
      // Add elements that don't already exist
      newEls.forEach(el => {
        if (!cy.getElementById(el.data.id).length) {
          cy.add(el);
        }
      });
      cy.layout({ name: 'cose', animate: true, animationDuration: 500, fit: false, nodeRepulsion: 6000 }).run();
      updateStats();
    });

    updateStats();
  }

  function graphDataToElements(data, hubIds) {
    const elements = [];
    const nodes = data.nodes || [];
    const edges = data.edges || [];

    // Count edges per node for sizing
    const edgeCounts = {};
    edges.forEach(e => {
      edgeCounts[e.source_node_id] = (edgeCounts[e.source_node_id] || 0) + 1;
      edgeCounts[e.target_node_id] = (edgeCounts[e.target_node_id] || 0) + 1;
    });

    nodes.forEach(n => {
      const deg = edgeCounts[n.id] || 1;
      const sz = Math.min(50, 12 + deg * 3);
      const el = {
        data: {
          id: 'n-' + n.id,
          nodeId: n.id,
          label: n.title.length > 40 ? n.title.slice(0, 38) + '…' : n.title,
          fullTitle: n.title,
          color: typeColor[n.event_type] || '#6b7280',
          eventType: n.event_type,
          confidence: n.confidence,
          size: sz,
        },
      };
      if (hubIds.includes(n.id)) el.classes = 'hub';
      elements.push(el);
    });

    edges.forEach(e => {
      elements.push({
        data: {
          id: 'e-' + e.id,
          source: 'n-' + e.source_node_id,
          target: 'n-' + e.target_node_id,
          relType: e.relationship_type,
          color: relColor[e.relationship_type] || '#6b7280',
          width: 1 + e.strength * 4,
          strength: e.strength,
          reasoning: e.reasoning,
        },
      });
    });

    return elements;
  }

  function updateStats() {
    const n = cy ? cy.nodes().length : 0;
    const e = cy ? cy.edges().length : 0;
    document.getElementById('graph-stats').innerHTML =
      `<span>Showing <span style="color:var(--text)">${n}</span> nodes</span>` +
      `<span>Edges: <span style="color:var(--text)">${e}</span></span>` +
      `<span style="margin-left:auto;color:var(--text3)">Pan: drag · Zoom: scroll · Expand: click node</span>`;
  }

  // Mode switching
  window.switchGraphMode = async (mode) => {
    currentMode = mode;
    document.querySelectorAll('#graph-mode-btns button').forEach(b => {
      b.className = b.dataset.mode === mode ? 'btn btn-p btn-sm' : 'btn btn-sm';
    });
    document.getElementById('graph-search-bar').style.display = mode === 'search' ? 'block' : 'none';
    await reloadGraph();
  };

  async function loadHubs(eventType) {
    const f = getFilters();
    let url = `/api/graph/hubs?limit=20&min_strength=${f.minStr}`;
    if (eventType) url += `&event_type=${eventType}`;
    if (f.rel) url += `&relationship_type=${f.rel}`;
    const data = await api(url);
    const hubIds = (data.nodes || []).slice(0, 20).map(n => n.id);
    const elements = graphDataToElements(data, hubIds);
    initCy(elements);
  }

  async function loadClusters() {
    const data = await api('/api/graph/clusters');
    const elements = [];

    (data.clusters || []).forEach(c => {
      const sz = Math.min(100, 30 + Math.sqrt(c.node_count) * 5);
      elements.push({
        data: {
          id: 'cluster-' + c.event_type,
          clusterId: c.event_type,
          label: `${c.event_type}\n${c.node_count} nodes`,
          color: typeColor[c.event_type] || '#6b7280',
          eventType: c.event_type,
          size: sz,
          nodeCount: c.node_count,
          edgeCount: c.edge_count,
        },
        classes: 'cluster-node',
      });
    });

    (data.inter_cluster_edges || []).forEach((e, i) => {
      elements.push({
        data: {
          id: 'ce-' + i,
          source: 'cluster-' + e.source_type,
          target: 'cluster-' + e.target_type,
          relType: e.dominant_relationship,
          color: relColor[e.dominant_relationship] || '#6b7280',
          width: Math.min(8, 1 + Math.sqrt(e.count) * 0.5),
          count: e.count,
        },
        classes: 'cluster-edge',
      });
    });

    initCy(elements);
    cy.layout({ name: 'circle', animate: true }).run();
  }

  let searchTimeout = null;
  window.debounceSearch = () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(reloadGraph, 300);
  };

  async function loadSearch() {
    const q = document.getElementById('graph-search-input')?.value?.trim();
    if (!q || q.length < 2) {
      if (cy) cy.destroy();
      cy = null;
      updateStats();
      return;
    }
    const f = getFilters();
    const hops = document.getElementById('graph-hops')?.value || 2;
    let url = `/api/graph/search?q=${encodeURIComponent(q)}&hops=${hops}&min_strength=${f.minStr}`;
    if (f.rel) url += `&relationship_type=${f.rel}`;
    const data = await api(url);
    const elements = graphDataToElements(data, []);

    // Mark search matches
    const qLower = q.toLowerCase();
    elements.forEach(el => {
      if (el.data.fullTitle && el.data.fullTitle.toLowerCase().includes(qLower)) {
        el.classes = (el.classes || '') + ' search-match';
      }
    });

    initCy(elements);
  }

  window.reloadGraph = async () => {
    if (currentMode === 'hubs') await loadHubs();
    else if (currentMode === 'clusters') await loadClusters();
    else if (currentMode === 'search') await loadSearch();
  };

  // Initial load
  await loadHubs();
};
```

- [ ] **Step 3: Verify the dashboard loads**

Open `http://localhost:8000/` in a browser, click "Event Graph" tab. Verify:
- Cytoscape graph renders with nodes and edges
- Nodes are colored by event_type
- Edges have arrows
- Pan (drag) and zoom (scroll) work
- Hover shows tooltips
- Clicking a node expands its neighborhood

- [ ] **Step 4: Commit**

```bash
git add backend/app/dashboard.html
git commit -m "feat: replace static SVG graph with interactive Cytoscape.js 3-mode visualization"
```

---

### Task 5: Restart Server and End-to-End Verification

**Files:** None — verification only.

- [ ] **Step 1: Restart the API server**

```bash
pkill -f "uvicorn app.main:app.*8000"
sleep 2
cd /home/oshrin/projects/future_prediction/backend
.venv/bin/python3 .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 &
sleep 3
```

- [ ] **Step 2: Verify all endpoints respond**

```bash
curl -s 'http://localhost:8000/api/graph/hubs?limit=5' | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'hubs: nodes={len(d[\"nodes\"])}, edges={len(d[\"edges\"])}')"
curl -s 'http://localhost:8000/api/graph/clusters' | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'clusters: {len(d[\"clusters\"])}, inter_edges={len(d[\"inter_cluster_edges\"])}')"
curl -s 'http://localhost:8000/api/graph/search?q=climate&hops=1' | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'search: nodes={len(d[\"nodes\"])}, edges={len(d[\"edges\"])}')"
```

Expected: All three return non-empty results.

- [ ] **Step 3: Manual dashboard verification**

Open `http://192.168.50.114/predictions/` and verify:
1. **Hubs mode**: Force-directed graph loads with ~20 hub nodes, click a node expands it
2. **Clusters mode**: 5 cluster bubbles with inter-cluster edges, click a cluster drills down
3. **Search mode**: Type "inflation", results appear after 300ms, nodes highlight
4. **Filters**: Relationship dropdown and strength slider filter edges in real-time
5. **Tooltips**: Hover nodes and edges shows info
