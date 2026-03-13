from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery = Celery("future_prediction", broker=settings.redis_url, backend=settings.redis_url)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "collect-polymarket": {
            "task": "app.tasks.collection_tasks.collect_polymarket",
            "schedule": settings.collection_interval,
        },
        "collect-manifold": {
            "task": "app.tasks.collection_tasks.collect_manifold",
            "schedule": settings.collection_interval,
        },
        "collect-gdelt-news": {
            "task": "app.tasks.collection_tasks.collect_gdelt",
            "schedule": settings.collection_interval,
        },
        "score-resolved-predictions": {
            "task": "app.tasks.scoring_tasks.score_resolved_predictions",
            "schedule": crontab(hour=0, minute=0),  # daily at midnight
        },
        # Meta-agents: periodic system self-improvement
        "meta-source-evaluator": {
            "task": "app.tasks.meta_tasks.run_source_evaluator",
            "schedule": crontab(hour=6, minute=0),  # daily at 6 AM
        },
        "meta-strategy-optimizer": {
            "task": "app.tasks.meta_tasks.run_strategy_optimizer",
            "schedule": crontab(hour=6, minute=15),  # daily at 6:15 AM
        },
        "meta-method-researcher": {
            "task": "app.tasks.meta_tasks.run_method_researcher",
            "schedule": crontab(hour="*/12", minute=30),  # every 12 hours
        },
        "meta-feature-ideator": {
            "task": "app.tasks.meta_tasks.run_feature_ideator",
            "schedule": crontab(hour=7, minute=0, day_of_week="mon,thu"),  # Mon & Thu
        },
    },
)

celery.autodiscover_tasks(["app.tasks"])
