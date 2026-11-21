import json

import pytest

from clipforge_worker.highlights.parse import HighlightParseError, parse_highlight_response


def clip(**overrides):
    base = {
        "start": 10.0,
        "end": 45.0,
        "hook_title": "The one trick nobody tells you",
        "virality_score": 88,
        "score_breakdown": {"hook": 90, "payoff": 85, "emotion": 70, "standalone": 92},
        "reason": "Strong opening question with a clear answer.",
    }
    base.update(overrides)
    return base


def test_parses_valid_object():
    result = parse_highlight_response(json.dumps({"clips": [clip(), clip(start=60, end=100)]}))
    assert len(result) == 2
    assert result[0].virality_score == 88
    assert result[0].score_breakdown.standalone == 92


def test_accepts_bare_list_and_code_fence():
    raw = "```json\n" + json.dumps([clip()]) + "\n```"
    assert len(parse_highlight_response(raw)) == 1


def test_rounds_float_and_string_scores():
    result = parse_highlight_response(json.dumps({"clips": [clip(virality_score=87.6, score_breakdown={"hook": "90", "payoff": 80.2, "emotion": 1, "standalone": 0})]}))
    assert result[0].virality_score == 88
    assert result[0].score_breakdown.hook == 90


def test_strips_whitespace_in_titles():
    assert parse_highlight_response(json.dumps([clip(hook_title="  Hi  ")]))[0].hook_title == "Hi"


@pytest.mark.parametrize("raw", ["", "   ", "not json", "{\"clips\": ", "42", "{\"items\": []}", "{\"clips\": {}}"])
def test_rejects_unusable_payloads(raw):
    with pytest.raises(HighlightParseError):
        parse_highlight_response(raw)


def test_rejects_empty_clip_list():
    with pytest.raises(HighlightParseError, match="empty"):
        parse_highlight_response(json.dumps({"clips": []}))


def test_drops_invalid_items_but_keeps_valid_ones():
    raw = json.dumps(
        {
            "clips": [
                clip(),
                clip(end=5.0),  # end before start
                clip(virality_score=150),  # out of range
                clip(hook_title=""),  # empty title
                {"start": 1},  # missing fields
                clip(score_breakdown={"hook": 1}),  # incomplete breakdown
            ]
        }
    )
    result = parse_highlight_response(raw)
    assert len(result) == 1
    assert result[0].start == 10.0


def test_all_invalid_raises_with_details():
    with pytest.raises(HighlightParseError, match="end"):
        parse_highlight_response(json.dumps({"clips": [clip(start=50, end=40)]}))


def test_clamps_to_video_duration_and_drops_clips_past_the_end():
    raw = json.dumps({"clips": [clip(start=100, end=140), clip(start=200, end=230)]})
    result = parse_highlight_response(raw, video_duration=120)
    assert len(result) == 1
    assert result[0].end == 120


def test_post_copy_is_optional_and_hashtags_are_normalised():
    with_copy = clip(description="  Watch till the end  ", hashtags=["#Python", "python", "coding tips", "#shorts", 5])
    result = parse_highlight_response(json.dumps([with_copy, clip(start=60, end=100)]))
    assert result[0].description == "Watch till the end"
    assert result[0].hashtags == ["Python", "codingtips", "shorts"]
    assert result[1].description == "" and result[1].hashtags == []
