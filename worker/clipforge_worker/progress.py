"""Progress reporting: persist to Postgres (source of truth) and publish on Redis (live SSE updates)."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Callable

from app.core.channels import project_channel
from app.models import ProjectStatus

log = logging.getLogger(__name__)

# Overall 0-100 progress bar split across pipeline stages: stage -> (status shown, start %, end %)
STAGES: dict[str, tuple[ProjectStatus, int, int]] = {
    "downloading": (ProjectStatus.downloading, 0, 15),
    "extracting_audio": (ProjectStatus.transcribing, 15, 20),
    "transcribing": (ProjectStatus.transcribing, 20, 70),
    "finding_highlights": (ProjectStatus.finding_highlights, 70, 76),
    "reframing": (ProjectStatus.reframing, 76, 82),
    "rendering": (ProjectStatus.rendering, 82, 99),
}


def stage_progress(stage: str, fraction: float) -> tuple[ProjectStatus, int]:
    status, lo, hi = STAGES[stage]
    fraction = min(max(fraction, 0.0), 1.0)
    return status, int(lo + (hi - lo) * fraction)


# Writer signature: (project_id, fields) -> None. Injected so tests don't need a DB.
Writer = Callable[[uuid.UUID, dict], None]
Publisher = Callable[[str, str], None]


class ProgressReporter:
    def __init__(self, project_id: uuid.UUID, write: Writer, publish: Publisher, min_interval: float = 1.0) -> None:
        self.project_id = project_id
        self._write = write
        self._publish = publish
        self._min_interval = min_interval
        self._last: tuple[str, int] | None = None
        self._last_time = 0.0

    def stage(self, stage: str, fraction: float, message: str | None = None, *, force: bool = False) -> None:
        status, pct = stage_progress(stage, fraction)
        self.update(status=status, progress=pct, message=message, force=force)

    def update(
        self,
        *,
        status: ProjectStatus,
        progress: int,
        message: str | None = None,
        error: str | None = None,
        force: bool = False,
    ) -> None:
        now = time.monotonic()
        key = (status.value, progress)
        # Throttle: transcription can report hundreds of times; only write meaningful changes.
        if not force and key == self._last:
            return
        if not force and self._last and self._last[0] == status.value and now - self._last_time < self._min_interval:
            return
        self._last, self._last_time = key, now

        fields = {"status": status, "progress": progress, "status_message": message, "error": error}
        try:
            self._write(self.project_id, fields)
        except Exception:
            log.exception("Failed to persist progress for %s", self.project_id)
        payload = json.dumps(
            {"id": str(self.project_id), "status": status.value, "progress": progress, "status_message": message, "error": error}
        )
        try:
            self._publish(project_channel(str(self.project_id)), payload)
        except Exception:  # live updates are best-effort; the DB row is the source of truth
            log.warning("Failed to publish progress for %s", self.project_id, exc_info=True)
