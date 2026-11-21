"""Read frames from the source video and run face detection on a sparse sample of them."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from clipforge_worker.errors import PipelineError
from clipforge_worker.reframe.detect import FaceDetector
from clipforge_worker.reframe.types import FaceBox, Sample

PATCH_SIZE = (24, 16)  # (w, h) of the mouth-area patch used for "who is talking"


def mouth_patch(gray: np.ndarray, face: FaceBox) -> np.ndarray | None:
    import cv2

    h, w = gray.shape[:2]
    x0 = int(max(0, (face.cx - face.w / 2) * w))
    x1 = int(min(w, (face.cx + face.w / 2) * w))
    y0 = int(max(0, face.cy * h))  # lower half of the face box
    y1 = int(min(h, (face.cy + face.h / 2) * h))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    return cv2.resize(gray[y0:y1, x0:x1], PATCH_SIZE, interpolation=cv2.INTER_AREA)


def video_size(path: str | Path) -> tuple[int, int]:
    import cv2

    cap = cv2.VideoCapture(str(path))
    try:
        return int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        cap.release()


def sample_faces(
    path: str | Path,
    start: float,
    end: float,
    detector: FaceDetector,
    sample_fps: float = 3.0,
    max_width: int = 640,
) -> list[Sample]:
    """Detect faces every ~1/sample_fps seconds between start and end (source seconds).
    Frames are decoded sequentially (grab) and only sampled frames are converted (retrieve)."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise PipelineError("Couldn't open the video for face tracking.")
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, round(fps / max(sample_fps, 0.1)))
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, start) * 1000)
        samples: list[Sample] = []
        idx = 0
        while True:
            if not cap.grab():
                break
            t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if t > end:
                break
            if t >= start and idx % step == 0:
                ok, frame = cap.retrieve()
                if ok and frame is not None:
                    h, w = frame.shape[:2]
                    if w > max_width:
                        frame = cv2.resize(frame, (max_width, int(h * max_width / w)), interpolation=cv2.INTER_AREA)
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = detector.detect(rgb)
                    for f in faces:
                        f.patch = mouth_patch(gray, f)
                    samples.append(Sample(t=round(t - start, 3), faces=faces))
            idx += 1
        return samples
    finally:
        cap.release()
