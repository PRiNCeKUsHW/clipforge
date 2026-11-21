import pytest

from clipforge_worker.highlights.postprocess import SnapConfig, sentence_boundaries, snap_clip
from clipforge_worker.transcript import Word
from tests.factories import make_words, sentence_transcript

NO_PAD = SnapConfig(min_duration=20, max_duration=90, pad_start=0, pad_end=0)


def test_sentence_boundaries_from_punctuation_and_pauses():
    words = make_words("Hello there. How are you? Fine")
    # add a long pause before the last word so it starts a new sentence too
    words[-1] = Word(word="Fine", start=words[-2].end + 1.5, end=words[-2].end + 1.9)
    words.append(Word(word="thanks", start=words[-1].end + 0.1, end=words[-1].end + 0.5))
    starts, ends = sentence_boundaries(words, pause_gap=0.8)
    assert [words[i].word for i in starts] == ["Hello", "How", "Fine"]
    assert [words[i].word for i in ends] == ["there.", "you?", "thanks"]


def test_handles_quotes_after_terminal_punctuation():
    words = make_words('He said "stop." Then left')
    _, ends = sentence_boundaries(words)
    assert words[ends[0]].word == '"stop."'


def test_snaps_start_and_end_to_sentence_boundaries():
    t = sentence_transcript(30)  # 5s sentences: starts at 0, 5, 10...; ends at 4.9, 9.9, ...
    words = t.all_words()
    s, e = snap_clip(11.2, 38.3, words, NO_PAD)
    assert s == pytest.approx(10.0)  # nearest sentence start to 11.2
    assert e == pytest.approx(39.9)  # nearest sentence end to 38.3 (34.9 or 39.9 -> 39.9 is closer)


def test_enforces_minimum_duration():
    words = sentence_transcript(30).all_words()
    s, e = snap_clip(10.0, 18.0, words, NO_PAD)  # proposed 8s, below the 20s minimum
    assert e - s >= 20


def test_enforces_maximum_duration():
    words = sentence_transcript(60).all_words()
    s, e = snap_clip(0.0, 200.0, words, NO_PAD)
    assert e - s <= 90
    assert e == pytest.approx(89.9)  # the latest sentence end that still fits


def test_far_away_start_falls_back_to_nearest_word():
    # one very long "sentence" with no punctuation: no sentence start near 30s
    words = make_words(" ".join(f"w{i}" for i in range(200)))
    s, _ = snap_clip(30.2, 60, words, NO_PAD)
    assert s == pytest.approx(30.0)  # word starts every 0.5s


def test_padding_never_overlaps_neighbouring_words():
    words = sentence_transcript(30).all_words()
    cfg = SnapConfig(min_duration=20, max_duration=90, pad_start=5.0, pad_end=5.0)
    s, e = snap_clip(10.0, 39.9, words, cfg)
    # previous word ends at 9.9, next word starts at 40.0
    assert s == pytest.approx(9.9)
    assert e == pytest.approx(40.0)


def test_padding_is_clamped_to_media_bounds():
    words = sentence_transcript(10).all_words()  # ~49.9s total
    s, e = snap_clip(0.0, 49.9, words, SnapConfig(pad_start=1, pad_end=1), media_duration=50.0)
    assert s == 0.0
    assert e == pytest.approx(50.0)


def test_returns_none_when_no_reasonable_clip_exists():
    words = make_words("Too short.")
    assert snap_clip(0.0, 30.0, words, NO_PAD) is None


def test_without_words_keeps_times_but_clamps():
    assert snap_clip(-1.0, 40.0, [], NO_PAD, media_duration=30) == (0.0, 30)
    assert snap_clip(0.0, 5.0, [], NO_PAD) is None


def test_hindi_danda_ends_a_sentence():
    words = make_words("नमस्ते दोस्तों। आज बात करेंगे")
    _, ends = sentence_boundaries(words)
    assert words[ends[0]].word == "दोस्तों।"


def test_padding_never_pushes_a_clip_past_the_cap():
    words = sentence_transcript(40).all_words()  # sentence ends at x4.9 / x9.9
    cfg = SnapConfig(min_duration=20, max_duration=59, pad_start=0, pad_end=5.0)
    s, e = snap_clip(0.0, 59.0, words, cfg)
    assert e - s <= 59.0
