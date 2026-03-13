from app.tasks.celery_app import celery


@celery.task(name="app.tasks.scoring_tasks.score_resolved_predictions")
def score_resolved_predictions():
    # TODO: Phase 3 - calculate Brier scores for resolved predictions
    return {"status": "not_implemented"}
