import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

CPU_DEFAULT_MODEL = "small"
GPU_DEFAULT_MODEL = "large-v3-turbo"


@dataclass(frozen=True)
class WhisperConfig:
    model: str
    device: str  # "cpu" | "cuda"
    compute_type: str


def cuda_available() -> bool:
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:  # library missing or no driver: treat as CPU-only
        return False


def resolve_whisper_config(device: str = "auto", model: str = "auto", compute_type: str = "auto") -> WhisperConfig:
    """Fill in "auto" values: GPU if CUDA is visible, otherwise CPU, with sensible model/precision."""
    device = (device or "auto").lower()
    if device == "auto":
        device = "cuda" if cuda_available() else "cpu"
    elif device == "cuda" and not cuda_available():
        log.warning("WHISPER_DEVICE=cuda but no CUDA device is visible; falling back to CPU")
        device = "cpu"

    if not model or model == "auto":
        model = GPU_DEFAULT_MODEL if device == "cuda" else CPU_DEFAULT_MODEL
    if not compute_type or compute_type == "auto":
        compute_type = "float16" if device == "cuda" else "int8"
    return WhisperConfig(model=model, device=device, compute_type=compute_type)
