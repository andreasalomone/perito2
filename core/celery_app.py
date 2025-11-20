import os
from celery import Celery
from core.config import settings

def make_celery(app_name=__name__):
    redis_url = settings.REDIS_URL
    celery = Celery(
        app_name,
        backend=redis_url,
        broker=redis_url
    )
    celery.conf.update(
        broker_connection_retry_on_startup=True,
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
    )
    # Auto-discover tasks from the services module
    celery.autodiscover_tasks(['services'])
    return celery

celery_app = make_celery()

# Import tasks to ensure they're registered
from services import tasks  # noqa: E402, F401
