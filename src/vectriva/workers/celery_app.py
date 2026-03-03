"""Celery application for background tasks."""

from celery import Celery

from vectriva.core.config import settings

app = Celery(
    "vectriva",
    broker=settings.celery_broker_url,
    backend=settings.celery_broker_url,
    include=["vectriva.workers.tasks"],
)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
