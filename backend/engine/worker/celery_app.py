import os

from celery import Celery
from celery.schedules import crontab

_broker = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "aios_bizbrain",
    broker=_broker,
    backend=_broker,
    include=[
        "engine.worker.tasks.reflection",
        "engine.worker.tasks.consolidation",
        "engine.worker.tasks.reconciliation",
        "engine.worker.tasks.notifications",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    beat_schedule={
        "send-digest-daily": {
            "task": "engine.worker.tasks.notifications.send_digest",
            "schedule": crontab(hour=7, minute=0),
            "kwargs": {
                "items": [],
                "to_address": os.getenv("DIGEST_EMAIL_ADDRESS", "partners@northpath.example.com"),
            },
        },
    },
)
