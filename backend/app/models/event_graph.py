import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EventNode(Base):
    __tablename__ = "event_nodes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100), index=True)
    event_type: Mapped[str] = mapped_column(String(50))  # geopolitical, economic, tech, social, environmental
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id"))
    prediction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("predictions.id"))
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default="active")  # active, resolved, expired
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Edges where this node is the source
    outgoing_edges: Mapped[list["EventEdge"]] = relationship(
        back_populates="source_node", foreign_keys="EventEdge.source_node_id"
    )
    # Edges where this node is the target
    incoming_edges: Mapped[list["EventEdge"]] = relationship(
        back_populates="target_node", foreign_keys="EventEdge.target_node_id"
    )


class EventEdge(Base):
    __tablename__ = "event_edges"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event_nodes.id"))
    target_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event_nodes.id"))
    relationship_type: Mapped[str] = mapped_column(String(30))  # causes, correlates, precedes, amplifies, mitigates
    strength: Mapped[float] = mapped_column(Float)  # 0.0 - 1.0
    reasoning: Mapped[str | None] = mapped_column(Text)
    detected_by: Mapped[str] = mapped_column(String(30))  # agent, user, market
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source_node: Mapped["EventNode"] = relationship(back_populates="outgoing_edges", foreign_keys=[source_node_id])
    target_node: Mapped["EventNode"] = relationship(back_populates="incoming_edges", foreign_keys=[target_node_id])
