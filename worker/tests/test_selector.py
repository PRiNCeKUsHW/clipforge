"""End-to-end highlight selection with a fake LLM standing in for Gemini."""

import json

import pytest

from clipforge_worker.errors import PipelineError
from clipforge_worker.highlights.selector import HighlightOptions, request_highlights, select_highlights
from clipforge_worker.transcript import Segment, Transcript
from tests.factories import sentence_transcript


def clip(start, end, score, title="Title"):
    return {
        "start": start,
        "end": end,
        "hook_title": title,
        "virality_score": score,
        "score_breakdown": {"hook": score, "payoff": score, "emotion": score, "standalone": score},
        "reason": "because",
    }


class FakeLLM:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts: list[str] = []
        self.images = []

    def generate_json(self, prompt, *, images=None):
        self.prompts.append(prompt)
        self.images.append(images)
        r = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        return r(prompt) if callable(r) else r


def test_retries_once_on_invalid_output_then_succeeds():
    llm = FakeLLM("garbage", json.dumps({"clips": [clip(0, 30, 80)]}))
    result = request_highlights(llm, "PROMPT")
    assert len(result) == 1
    assert len(llm.prompts) == 2
    assert "previous answer was rejected" in llm.prompts[1]


def test_two_invalid_outputs_raise_readable_error():
    llm = FakeLLM("garbage", "still garbage")
    with pytest.raises(PipelineError, match="invalid highlight data twice"):
        request_highlights(llm, "PROMPT")
    assert len(llm.prompts) == 2


def test_select_snaps_dedupes_and_sorts():
    t = sentence_transcript(40)  # 200s, 5s sentences
    llm = FakeLLM(json.dumps({"clips": [
        clip(11.0, 41.0, 70, "B"),
        clip(12.0, 44.0, 90, "A overlaps B and wins"),
        clip(101.3, 131.0, 60, "C"),
    ]}))  # fmt: skip
    result = select_highlights(t, llm, HighlightOptions())
    assert [c.hook_title for c in result] == ["A overlaps B and wins", "C"]
    a = result[0]
    # snapped to a sentence start (multiples of 5s) minus padding; end at a sentence end plus padding
    assert a.start == pytest.approx(9.9, abs=0.01)  # 10.0 - 0.15 pad clamped to previous word end 9.9
    assert a.end == pytest.approx(44.9 + 0.1, abs=0.01)  # 44.9 + 0.3 pad clamped to next word start 45.0
    assert 20 <= a.end - a.start <= 90


def test_instruction_and_speakers_reach_the_prompt():
    t = sentence_transcript(20)
    t.segments[0].speaker = "SPEAKER_00"
    llm = FakeLLM(json.dumps([clip(0, 30, 80)]))
    select_highlights(t, llm, HighlightOptions(), instruction="only funny moments")
    prompt = llm.prompts[0]
    assert "only funny moments" in prompt
    assert "SPEAKER_00:" in prompt
    assert "[0.0-4.9]" in prompt


def test_long_transcripts_are_chunked_and_merged():
    t = sentence_transcript(1000)  # 5000s
    seen_windows = []

    def respond(prompt):
        # propose a clip at the start of each window
        import re

        m = re.search(r"covering (\d+)s to (\d+)s", prompt)
        assert m, "multi-chunk prompts must state their window"
        start = float(m.group(1))
        seen_windows.append(start)
        return json.dumps([clip(start + 30, start + 60, 50 + len(seen_windows))])

    llm = FakeLLM(respond)
    result = select_highlights(t, llm, HighlightOptions(chunk_threshold=3600, chunk_seconds=1500, chunk_overlap=120))
    assert len(seen_windows) == 4  # 0, 1380, 2760, 4140
    assert len(result) == 4
    assert [c.virality_score for c in result] == sorted([c.virality_score for c in result], reverse=True)


def test_one_failing_chunk_does_not_sink_the_rest():
    t = sentence_transcript(1000)
    calls = {"n": 0}

    def respond(prompt):
        calls["n"] += 1
        if "covering 0s" in prompt:
            return "garbage"
        return json.dumps([clip(1500, 1530, 70)])

    result = select_highlights(t, FakeLLM(respond), HighlightOptions())
    assert len(result) == 1


def test_no_usable_clips_raises():
    t = Transcript(duration=100, segments=[Segment(start=0, end=2, text="Hi.", words=[])])
    # every proposed clip is far shorter than the hard minimum once snapped (no words -> raw times)
    llm = FakeLLM(json.dumps([clip(0, 5, 80)]))
    with pytest.raises(PipelineError, match="didn't find any clip-worthy"):
        select_highlights(t, llm, HighlightOptions())


def test_caps_number_of_clips():
    t = sentence_transcript(400)  # 2000s
    proposals = [clip(i * 100 + 0.1, i * 100 + 30, 50 + i) for i in range(15)]
    result = select_highlights(t, FakeLLM(json.dumps(proposals)), HighlightOptions(max_clips=10))
    assert len(result) == 10
    assert result[0].virality_score == 64
