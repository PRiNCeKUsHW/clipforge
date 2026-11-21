"""Stream a zip of stored objects without buffering whole files in memory or on disk."""

from __future__ import annotations

import zipfile
from collections.abc import Iterator

from app.core.storage import Storage


class _Sink:
    """Write-only buffer. Having no seek()/tell() makes zipfile use streaming mode (data descriptors)."""

    def __init__(self) -> None:
        self._chunks: list[bytes] = []

    def write(self, data: bytes) -> int:
        self._chunks.append(bytes(data))
        return len(data)

    def flush(self) -> None:
        pass

    def drain(self) -> bytes:
        data = b"".join(self._chunks)
        self._chunks.clear()
        return data


def iter_zip(storage: Storage, entries: list[tuple[str, str]], chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
    """entries: [(name inside the zip, storage key)]. MP4s are already compressed, so store them."""
    sink = _Sink()
    with zipfile.ZipFile(sink, mode="w", compression=zipfile.ZIP_STORED, allowZip64=True) as zf:  # type: ignore[arg-type]
        for name, key in entries:
            body = storage.client.get_object(Bucket=storage.bucket, Key=key)["Body"]
            with zf.open(name, mode="w", force_zip64=True) as dest:
                for chunk in body.iter_chunks(chunk_size):
                    dest.write(chunk)
                    if out := sink.drain():
                        yield out
            if out := sink.drain():
                yield out
    if out := sink.drain():
        yield out
