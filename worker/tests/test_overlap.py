from dataclasses import dataclass

from clipforge_worker.highlights.postprocess import overlap_seconds, remove_overlaps


@dataclass
class C:
    start: float
    end: float
    virality_score: int
    name: str = ""


def test_overlap_seconds():
    assert overlap_seconds(C(0, 10, 1), C(5, 20, 1)) == 5
    assert overlap_seconds(C(0, 10, 1), C(10, 20, 1)) == 0
    assert overlap_seconds(C(0, 10, 1), C(20, 30, 1)) == 0
    assert overlap_seconds(C(0, 30, 1), C(10, 20, 1)) == 10


def test_keeps_higher_score_of_overlapping_pair():
    kept = remove_overlaps([C(0, 30, 70, "low"), C(20, 50, 90, "high")])
    assert [c.name for c in kept] == ["high"]


def test_non_overlapping_all_kept_sorted_by_score():
    kept = remove_overlaps([C(0, 20, 50, "a"), C(30, 50, 80, "b"), C(60, 90, 65, "c")])
    assert [c.name for c in kept] == ["b", "c", "a"]


def test_chain_of_overlaps_is_resolved_greedily():
    # b (best) overlaps both a and c; a and c don't overlap each other
    kept = remove_overlaps([C(0, 30, 60, "a"), C(25, 55, 90, "b"), C(50, 80, 70, "c")])
    assert [c.name for c in kept] == ["b"]
    # if b is worst, a and c both survive
    kept = remove_overlaps([C(0, 30, 60, "a"), C(25, 55, 10, "b"), C(50, 80, 70, "c")])
    assert [c.name for c in kept] == ["c", "a"]


def test_tiny_overlap_within_tolerance_is_allowed():
    kept = remove_overlaps([C(0, 30.3, 80, "a"), C(30, 60, 70, "b")], tolerance=0.5)
    assert len(kept) == 2


def test_duplicate_from_two_chunks_collapses_to_one():
    kept = remove_overlaps([C(100, 140, 85, "chunk1"), C(100.5, 139.8, 83, "chunk2")])
    assert [c.name for c in kept] == ["chunk1"]


def test_empty():
    assert remove_overlaps([]) == []
