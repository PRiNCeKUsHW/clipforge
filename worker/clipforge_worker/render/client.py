"""HTTP client for the Remotion render service (renderer/server.mjs)."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from clipforge_worker.errors import PipelineError, TransientError


class RendererClient:
    def __init__(self, base_url: str, timeout_seconds: float = 1800, poll_interval: float = 1.0, transport=None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.poll_interval = poll_interval
        self._http = httpx.Client(base_url=self.base_url, timeout=30, transport=transport)

    def render(
        self,
        input_path: Path,
        output_path: Path,
        props: dict[str, Any],
        on_progress: Callable[[float], None] | None = None,
    ) -> None:
        try:
            r = self._http.post("/render", json={"input": str(input_path), "output": str(output_path), "props": props})
        except httpx.TransportError as exc:
            raise TransientError(f"Render service not reachable at {self.base_url}: {exc}") from exc
        if r.status_code >= 500:
            raise TransientError(f"Render service error ({r.status_code}): {r.text[:300]}")
        if r.status_code >= 400:
            raise PipelineError(f"Render request rejected: {r.json().get('error', r.text)[:300]}")
        job_id = r.json()["id"]

        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            try:
                st = self._http.get(f"/jobs/{job_id}").json()
            except httpx.TransportError as exc:
                raise TransientError(f"Lost connection to the render service: {exc}") from exc
            if "status" not in st:
                # the service restarted and forgot the job: retrying re-submits it
                raise TransientError("Render service restarted during rendering")
            if on_progress:
                on_progress(float(st.get("progress") or 0.0))
            if st["status"] == "done":
                return
            if st["status"] == "failed":
                raise PipelineError(f"Rendering failed: {st.get('error') or 'unknown error'}")
            time.sleep(self.poll_interval)
        raise PipelineError(f"Rendering took longer than {self.timeout_seconds:.0f}s and was abandoned.")
