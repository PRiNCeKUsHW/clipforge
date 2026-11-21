# Build context is the repo root (see docker-compose.yml): the worker also needs backend/app (shared models).
FROM python:3.12-slim

ARG INSTALL_WHISPERX=false
ARG WHISPER_GPU=false

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Model caches live on the "whisper-models" volume so rebuilds don't re-download them
    HF_HOME=/models/huggingface \
    TORCH_HOME=/models/torch \
    XDG_CACHE_HOME=/models/cache

# ffmpeg for media; libGL/glib/EGL for OpenCV + MediaPipe; PortAudio because MediaPipe imports sounddevice.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl \
       libgl1 libglib2.0-0 libegl1 libgles2 libportaudio2 \
    && rm -rf /var/lib/apt/lists/*

# MediaPipe BlazeFace model for face tracking (kept outside the /models volume so it isn't hidden).
RUN mkdir -p /opt/models && curl -fsSL -o /opt/models/blaze_face_short_range.tflite \
    https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite

# yt-dlp needs a JavaScript runtime to solve YouTube's player challenges.
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

WORKDIR /app

COPY worker/requirements.txt worker/requirements-whisperx.txt ./
RUN pip install -r requirements.txt
RUN if [ "$INSTALL_WHISPERX" = "true" ]; then pip install -r requirements-whisperx.txt; fi
# GPU: faster-whisper (CTranslate2) needs cuBLAS + cuDNN 9 for CUDA 12. The pip wheels are the
# simplest way to get them; the host only needs the NVIDIA driver.
RUN if [ "$WHISPER_GPU" = "true" ]; then pip install "nvidia-cublas-cu12" "nvidia-cudnn-cu12==9.*"; fi
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.12/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.12/site-packages/nvidia/cudnn/lib

COPY backend/app ./app
COPY worker/clipforge_worker ./clipforge_worker

RUN mkdir -p /data/work /models

CMD ["celery", "-A", "clipforge_worker.celery_app", "worker", "-Q", "default,render", "-c", "2", "--loglevel=INFO"]
