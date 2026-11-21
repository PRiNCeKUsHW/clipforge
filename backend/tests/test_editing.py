import io
import uuid
import zipfile

import pytest

from app.core.db import SessionLocal
from app.models import Clip, ClipStatus, ProjectStatus, VideoProject
from app.services.editing import apply_word_texts, retime_words, words_in_range
from tests.conftest import register_and_login

TRANSCRIPT = {
    "language": "en",
    "duration": 60.0,
    "segments": [
        {
            "start": 0,
            "end": 60,
            "text": "...",
            "words": [{"word": f"w{i}", "start": float(i), "end": i + 0.8, "speaker": "SPEAKER_00"} for i in range(60)],
        }
    ],
}


# ---------------------------------------------------------------- pure helpers
def test_words_in_range_uses_midpoints():
    words = words_in_range(TRANSCRIPT, 10.0, 12.0)
    assert [w["word"] for w in words] == ["w10", "w11"]  # w12 midpoint 12.4 is outside
    assert words[0]["speaker"] == "SPEAKER_00"


def test_retime_keeps_edits_for_words_still_inside():
    current = words_in_range(TRANSCRIPT, 10.0, 20.0)
    current[0]["word"] = "TEN"  # w10 edited
    current[5]["word"] = "FIFTEEN"  # w15 edited
    new = retime_words(TRANSCRIPT, current, 12.0, 25.0)
    texts = [w["word"] for w in new]
    assert "TEN" not in texts and "w10" not in texts  # trimmed away
    assert "FIFTEEN" in texts  # edit preserved
    assert texts[-1] == "w24"  # extended range picks up original words


def test_apply_word_texts():
    current = words_in_range(TRANSCRIPT, 0, 2.5)
    edited = apply_word_texts(current, ["Hello", "  big   world ", ""])
    assert [w["word"] for w in edited] == ["Hello", "big world", ""]
    assert [w["start"] for w in edited] == [w["start"] for w in current]
    with pytest.raises(ValueError):
        apply_word_texts(current, ["too", "few"])


# ---------------------------------------------------------------- API
async def make_clip(client, auth, s3, status=ClipStatus.ready) -> tuple[uuid.UUID, uuid.UUID]:
    r = await client.post("/api/projects", headers=auth, json={"source_type": "youtube", "source_url": "https://youtu.be/dQw4w9WgXcQ"})
    pid = uuid.UUID(r.json()["id"])
    async with SessionLocal() as s:
        p = await s.get(VideoProject, pid)
        p.status, p.duration, p.transcript, p.storage_key = ProjectStatus.ready, 60.0, TRANSCRIPT, f"sources/{pid}/source.mp4"
        clip = Clip(
            project_id=pid, start=10.0, end=30.0, hook_title="Hook", virality_score=80,
            score_breakdown={}, reason="r", transcript_words=words_in_range(TRANSCRIPT, 10, 30),
            crop_path={"layout": "single", "keyframes": []}, status=status,
            output_key=f"clips/{pid}/c.mp4", hashtags=["a"], description="desc",
        )  # fmt: skip
        s.add(clip)
        await s.commit()
        cid = clip.id
    s3.client.put_object(Bucket=s3.bucket, Key=f"clips/{pid}/c.mp4", Body=b"fake-mp4-bytes")
    return pid, cid


async def test_clip_detail_has_editor_fields(client, auth, s3):
    _, cid = await make_clip(client, auth, s3)
    body = (await client.get(f"/api/clips/{cid}", headers=auth)).json()
    assert body["framing"] == "single" and body["layout"] == "auto"
    assert body["project_duration"] == 60.0
    assert body["source_url"] and len(body["transcript_words"]) == 20
    assert body["hashtags"] == ["a"] and body["description"] == "desc"


async def test_trim_retimes_words_and_resets_crop(client, auth, s3):
    _, cid = await make_clip(client, auth, s3)
    r = await client.patch(f"/api/clips/{cid}", headers=auth, json={"start": 12.0, "end": 40.0})
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["start"], body["end"]) == (12.0, 40.0)
    assert body["transcript_words"][0]["word"] == "w12"
    assert body["framing"] is None  # crop path cleared, recomputed on render


@pytest.mark.parametrize(
    "payload",
    [{"start": 10, "end": 11}, {"end": 999}, {"caption_style": "comic-sans"}, {"word_texts": ["a"]}, {"start": 1, "word_texts": []}],
)
async def test_invalid_edits(client, auth, s3, payload):
    _, cid = await make_clip(client, auth, s3)
    assert (await client.patch(f"/api/clips/{cid}", headers=auth, json=payload)).status_code == 422


async def test_caption_text_style_title_and_copy_edits(client, auth, s3):
    _, cid = await make_clip(client, auth, s3)
    texts = [f"x{i}" for i in range(20)]
    texts[3] = ""
    r = await client.patch(
        f"/api/clips/{cid}",
        headers=auth,
        json={"word_texts": texts, "caption_style": "karaoke", "hook_title": " New ", "hashtags": ["#Py", " ", "AI"], "description": "hi"},
    )
    body = r.json()
    assert body["transcript_words"][0]["word"] == "x0" and body["transcript_words"][3]["word"] == ""
    assert body["transcript_words"][0]["start"] == 10.0
    assert body["caption_style"] == "karaoke" and body["hook_title"] == "New" and body["hashtags"] == ["Py", "AI"]
    assert body["transcript_text"].startswith("x0 x1 x2 x4")


async def test_render_enqueues_and_blocks_edits_while_rendering(client, auth, s3, enqueued_tasks):
    _, cid = await make_clip(client, auth, s3)
    r = await client.post(f"/api/clips/{cid}/render", headers=auth)
    assert r.status_code == 202 and r.json()["status"] == "rendering"
    assert enqueued_tasks["render"] == [cid]
    assert (await client.post(f"/api/clips/{cid}/render", headers=auth)).status_code == 409
    assert (await client.patch(f"/api/clips/{cid}", headers=auth, json={"hook_title": "x"})).status_code == 409


async def test_zip_download_contains_rendered_clips(client, auth, s3):
    pid, _ = await make_clip(client, auth, s3)
    r = await client.get(f"/api/projects/{pid}/download.zip", headers=auth)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert zf.namelist() == ["01-Hook.mp4"]
        assert zf.read("01-Hook.mp4") == b"fake-mp4-bytes"


async def test_editor_endpoints_are_private(client, auth, s3):
    pid, cid = await make_clip(client, auth, s3)
    other = await register_and_login(client, "intruder@example.com")
    assert (await client.patch(f"/api/clips/{cid}", headers=other, json={"hook_title": "x"})).status_code == 404
    assert (await client.post(f"/api/clips/{cid}/render", headers=other)).status_code == 404
    assert (await client.get(f"/api/projects/{pid}/download.zip", headers=other)).status_code == 404


async def test_caption_style_none_is_allowed(client, auth, s3):
    _, cid = await make_clip(client, auth, s3)
    r = await client.patch(f"/api/clips/{cid}", headers=auth, json={"caption_style": "none"})
    assert r.status_code == 200 and r.json()["caption_style"] == "none"


async def test_layout_change_resets_framing(client, auth, s3):
    _, cid = await make_clip(client, auth, s3)
    body = (await client.get(f"/api/clips/{cid}", headers=auth)).json()
    assert body["layout"] == "auto" and body["framing"] == "single"
    r = await client.patch(f"/api/clips/{cid}", headers=auth, json={"layout": "podcast_split"})
    assert r.status_code == 200
    assert r.json()["layout"] == "podcast_split" and r.json()["framing"] is None
    assert (await client.patch(f"/api/clips/{cid}", headers=auth, json={"layout": "diagonal"})).status_code == 422
