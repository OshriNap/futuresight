import asyncio

from app.tasks.celery_app import celery


def run_async(coro):
    """Helper to run async code inside a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery.task(name="app.tasks.collection_tasks.collect_polymarket")
def collect_polymarket():
    from app.agents.collector.polymarket import PolymarketCollector

    async def _run():
        collector = PolymarketCollector()
        return await collector.collect()

    return run_async(_run())


@celery.task(name="app.tasks.collection_tasks.collect_manifold")
def collect_manifold():
    # TODO: Phase 2
    return {"status": "not_implemented"}


@celery.task(name="app.tasks.collection_tasks.collect_gdelt")
def collect_gdelt():
    # TODO: Phase 2
    return {"status": "not_implemented"}
