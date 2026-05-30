import os
from celery import Celery

_broker = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "aios_bizbrain",
    broker=_broker,
    backend=_broker,
    include=["engine.worker.tasks.reflection"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)
