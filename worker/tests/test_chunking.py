import pytest

from clipforge_worker.highlights.chunking import chunk_transcript
from clipforge_worker.transcript import Segment


def segments_every(seconds: float, total: float, length: float = 8.0) -> list[Segment]:
    out, t = [], 0.0
    while t < total:
        out.append(Segment(start=t, end=min(t + length, total), text=f"at {t:.0f}"))
        t += seconds
    return out


def test_short_video_is_a_single_chunk():
    segs = segments_every(10, 1800)
    chunks = chunk_transcript(segs, 1800, threshold=3600)
    assert len(chunks) == 1
    assert chunks[0].segments == segs
    assert (chunks[0].start, chunks[0].end) == (0.0, 1800)


def test_long_video_is_split_with_overlap_and_full_coverage():
    total = 2 * 3600  # 2h
    segs = segments_every(10, total)
    chunks = chunk_transcript(segs, total, threshold=3600, chunk_seconds=1500, overlap_seconds=120)

    assert len(chunks) > 1
    assert chunks[0].start == 0
    assert chunks[-1].end == total
    for a, b in zip(chunks, chunks[1:]):
        assert b.start < a.end, "consecutive windows must overlap"
        assert a.end - b.start == pytest.approx(120)
    # every segment lands in at least one chunk
    covered = {id(s) for c in chunks for s in c.segments}
    assert covered == {id(s) for s in segs}
    # chunk indices are sequential
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_segment_on_a_boundary_appears_in_both_neighbouring_chunks():
    total = 4000
    boundary_seg = Segment(start=1450, end=1460, text="straddles")
    chunks = chunk_transcript([boundary_seg], total, threshold=3600, chunk_seconds=1500, overlap_seconds=120)
    containing = [c.index for c in chunks if boundary_seg in c.segments]
    assert containing == [0, 1]


def test_segments_belong_only_to_overlapping_windows():
    total = 4000
    segs = segments_every(10, total)
    for c in chunk_transcript(segs, total, threshold=3600, chunk_seconds=1500, overlap_seconds=120):
        assert all(s.end > c.start and s.start < c.end for s in c.segments)


def test_silent_windows_are_skipped():
    total = 5000
    segs = [Segment(start=10, end=20, text="intro"), Segment(start=4900, end=4950, text="outro")]
    chunks = chunk_transcript(segs, total, threshold=3600, chunk_seconds=1500, overlap_seconds=120)
    assert all(c.segments for c in chunks)
    assert [s.text for c in chunks for s in c.segments] == ["intro", "outro"]


def test_invalid_overlap_rejected():
    with pytest.raises(ValueError):
        chunk_transcript([], 5000, threshold=10, chunk_seconds=100, overlap_seconds=100)
