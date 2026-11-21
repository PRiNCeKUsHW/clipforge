import re
import unicodedata
from typing import Any


def safe_filename(name: str, default: str = "file", max_len: int = 80) -> str:
    """ASCII-only, filesystem/header safe file name stem."""
    norm = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    norm = re.sub(r"[^A-Za-z0-9._ -]+", "", norm).strip().replace(" ", "-")
    norm = re.sub(r"-{2,}", "-", norm).strip("-.")
    return (norm[:max_len] or default).rstrip("-.") or default


def words_to_text(words: list[dict[str, Any]]) -> str:
    return " ".join(t for w in words if (t := str(w.get("word", "")).strip()))
