"""Celery app. Celery = a task queue: the API drops a message in Redis, a worker process picks it up.

Queues:
  default    - download, audio extraction, highlight selection
  transcribe - Whisper (separate worker, concurrency 1: one model in memory)
  render     - clip rendering (cut segment, then the Remotion render service composes it)
"""

import logging

from celery import Celery
from celery.signals import after_setup_logger

from clipforge_worker.config import get_settings

settings = get_settings()

app = Celery("clipforge", broker=settings.redis_url, include=["clipforge_worker.tasks.pipeline"])
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_ignore_result=True,
    task_default_queue="default",
    task_routes={
        "clipforge.pipeline.transcribe": {"queue": "transcribe"},
        "clipforge.pipeline.render_clips": {"queue": "render"},
        "clipforge.render.clip": {"queue": "render"},
    },
    # Long jobs: acknowledge a message only once the task finishes, so a crashed worker's job is redelivered...
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # ...and don't let one worker hoard queued jobs while it's busy.
    worker_prefetch_multiplier=1,
    # Redis re-delivers unacked messages after this long; must exceed the longest task (a long transcription).
    broker_transport_options={"visibility_timeout": 6 * 60 * 60},
    broker_connection_retry_on_startup=True,
)


@after_setup_logger.connect
def _quiet_libraries(logger, *args, **kwargs):
    for name in ("botocore", "boto3", "urllib3", "httpx", "faster_whisper"):
        logging.getLogger(name).setLevel(logging.WARNING)
