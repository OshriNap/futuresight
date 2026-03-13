import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.event_graph import EventEdge, EventNode

router = APIRouter()


class EventNodeResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    category: str | None
    event_type: str
    occurred_at: datetime | None
    confidence: float | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EventEdgeResponse(BaseModel):
    id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    relationship_type: str
    strength: float
    reasoning: str | None
    detected_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class GraphResponse(BaseModel):
    nodes: list[EventNodeResponse]
    edges: list[EventEdgeResponse]


@router.get("/", response_model=GraphResponse)
async def get_event_graph(
    category: str | None = None,
    event_type: str | None = None,
    min_strength: float = Query(default=0.0, ge=0.0, le=1.0),
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
):
    node_query = select(EventNode).order_by(EventNode.created_at.desc()).limit(limit)
    if category:
        node_query = node_query.where(EventNode.category == category)
    if event_type:
        node_query = node_query.where(EventNode.event_type == event_type)

    nodes_result = await db.execute(node_query)
    nodes = nodes_result.scalars().all()
    node_ids = {n.id for n in nodes}

    edge_query = (
        select(EventEdge)
        .where(EventEdge.source_node_id.in_(node_ids) | EventEdge.target_node_id.in_(node_ids))
        .where(EventEdge.strength >= min_strength)
    )
    edges_result = await db.execute(edge_query)
    edges = edges_result.scalars().all()

    return GraphResponse(nodes=nodes, edges=edges)


@router.get("/node/{node_id}/connections", response_model=GraphResponse)
async def get_node_connections(node_id: uuid.UUID, depth: int = Query(default=2, le=5), db: AsyncSession = Depends(get_db)):
    """Get a node and its connections up to N hops deep."""
    visited_ids = set()
    current_ids = {node_id}
    all_nodes = []
    all_edges = []

    for _ in range(depth):
        if not current_ids:
            break
        edge_query = select(EventEdge).where(
            EventEdge.source_node_id.in_(current_ids) | EventEdge.target_node_id.in_(current_ids)
        )
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
    if all_node_ids:
        nodes_result = await db.execute(select(EventNode).where(EventNode.id.in_(all_node_ids)))
        all_nodes = nodes_result.scalars().all()

    return GraphResponse(nodes=all_nodes, edges=all_edges)
