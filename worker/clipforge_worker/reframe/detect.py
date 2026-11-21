"""Face detectors. MediaPipe BlazeFace is the default; OpenCV's Haar cascade is a no-download fallback."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

import numpy as np

from clipforge_worker.reframe.types import FaceBox

log = logging.getLogger(__name__)


class FaceDetector(Protocol):
    def detect(self, rgb: np.ndarray) -> list[FaceBox]:
        """Faces in an RGB uint8 frame, in normalised coordinates."""
        ...


class MediaPipeFaceDetector:
    def __init__(self, model_path: str, min_confidence: float = 0.5) -> None:
        import mediapipe as mp
        from mediapipe.tasks.python.core.base_options import BaseOptions
        from mediapipe.tasks.python.vision.face_detector import FaceDetector as MpFaceDetector
        from mediapipe.tasks.python.vision.face_detector import FaceDetectorOptions

        if not Path(model_path).exists():
            raise FileNotFoundError(f"MediaPipe face model not found at {model_path}")
        self._mp = mp
        self._detector = MpFaceDetector.create_from_options(
            FaceDetectorOptions(
                base_options=BaseOptions(model_asset_path=model_path), min_detection_confidence=min_confidence
            )
        )

    def detect(self, rgb: np.ndarray) -> list[FaceBox]:
        h, w = rgb.shape[:2]
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        result = self._detector.detect(image)
        faces = []
        for d in result.detections:
            bb = d.bounding_box
            score = d.categories[0].score if d.categories else 1.0
            faces.append(
                FaceBox(
                    cx=(bb.origin_x + bb.width / 2) / w,
                    cy=(bb.origin_y + bb.height / 2) / h,
                    w=bb.width / w,
                    h=bb.height / h,
                    score=float(score or 0.0),
                )
            )
        return faces


class HaarFaceDetector:
    def __init__(self) -> None:
        import cv2

        self._cv2 = cv2
        self._cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def detect(self, rgb: np.ndarray) -> list[FaceBox]:
        cv2 = self._cv2
        h, w = rgb.shape[:2]
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        min_side = max(24, int(min(h, w) * 0.06))
        boxes = self._cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(min_side, min_side))
        return [FaceBox(cx=(x + bw / 2) / w, cy=(y + bh / 2) / h, w=bw / w, h=bh / h) for (x, y, bw, bh) in boxes]


def make_detector(kind: str, model_path: str) -> FaceDetector:
    if kind == "mediapipe":
        try:
            return MediaPipeFaceDetector(model_path)
        except Exception as exc:  # missing package/model: degrade instead of failing the project
            log.warning("MediaPipe face detector unavailable (%s); falling back to OpenCV Haar cascade", exc)
    return HaarFaceDetector()
