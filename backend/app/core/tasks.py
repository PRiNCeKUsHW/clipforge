"""Enqueue work for the worker.

The API never imports worker code: it sends tasks *by name* over Redis, so the two
services can be deployed and scaled independently.
"""

import uuid

from celery import Celery

from app.core.config import get_settings

celery_client = Celery("clipforge-api", broker=get_settings().redis_url)
celery_client.conf.task_ignore_result = True

START_PIPELINE_TASK = "clipforge.pipeline.start"
RENDER_CLIP_TASK = "clipforge.render.clip"
PUBLISH_TASK = "clipforge.publish.run"


def enqueue_pipeline(project_id: uuid.UUID) -> None:
    celery_client.send_task(START_PIPELINE_TASK, args=[str(project_id)], queue="default")


def enqueue_render(clip_id: uuid.UUID) -> None:
    celery_client.send_task(RENDER_CLIP_TASK, args=[str(clip_id)], queue="render")


def enqueue_publish(job_id: uuid.UUID) -> None:
    celery_client.send_task(PUBLISH_TASK, args=[str(job_id)], queue="default")
