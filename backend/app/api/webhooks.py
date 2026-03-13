from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class WebhookTrigger(BaseModel):
    event_type: str  # e.g. "breaking_news", "market_move", "resolution"
    data: dict


@router.post("/trigger")
async def trigger_collection(payload: WebhookTrigger):
    """Trigger an event-driven collection cycle."""
    # TODO: Phase 2 - dispatch Celery task based on event_type
    return {"status": "accepted", "event_type": payload.event_type}
