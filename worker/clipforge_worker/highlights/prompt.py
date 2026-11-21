from __future__ import annotations

from collections.abc import Sequence

from clipforge_worker.transcript import Segment


def format_transcript(segments: Sequence[Segment], with_speakers: bool) -> str:
    """One line per segment: `[12.3-17.9] SPEAKER_00: text`. Timestamps are absolute seconds."""
    lines = []
    for s in segments:
        who = f"{s.speaker}: " if with_speakers and s.speaker else ""
        lines.append(f"[{s.start:.1f}-{s.end:.1f}] {who}{s.text.strip()}")
    return "\n".join(lines)


def build_prompt(
    transcript_text: str,
    *,
    min_seconds: float,
    max_seconds: float,
    min_clips: int,
    max_clips: int,
    instruction: str | None = None,
    window: tuple[float, float] | None = None,
    has_speakers: bool = False,
    has_frames: bool = False,
) -> str:
    how_many = f"the {max_clips} best" if min_clips == max_clips else f"{min_clips}-{max_clips}"
    parts = [
        "You are an expert short-form video editor who finds the moments in long videos that perform "
        "best as YouTube Shorts / Instagram Reels / TikToks.",
        "",
        f"From the timestamped transcript below, pick {how_many} self-contained clips, "
        f"each {min_seconds:.0f}-{max_seconds:.0f} seconds long. Fewer is fine if the content is thin; "
        "never invent moments that aren't in the transcript.",
        "",
        "Scoring criteria (each 0-100):",
        "- hook: the first 3 seconds grab attention (a bold claim, question, surprise or conflict).",
        "- payoff: the clip completes a thought and delivers a satisfying payoff or punchline.",
        "- emotion: humor, surprise, inspiration, controversy or strong emotion.",
        "- standalone: understandable without having watched the rest of the video.",
        "virality_score is your overall 0-100 estimate of how well the clip would perform (not just an average).",
        "",
        "Rules:",
        "- start/end are absolute seconds taken from the transcript timestamps.",
        "- Start at the beginning of a sentence; end at the end of a sentence.",
        "- Clips must not overlap.",
        "- hook_title: a catchy title for the short (max ~70 characters), in the transcript's language.",
        "- reason: one or two sentences on why this clip works.",
        "- description: a short, engaging social post caption for the clip (1-2 sentences, no hashtags).",
        "- hashtags: 3-6 relevant hashtags without the # sign (topic, niche, plus 'shorts').",
    ]
    if has_speakers:
        parts.append("- Lines are labelled with speaker ids; exchanges between speakers can make great clips.")
    if has_frames:
        parts.append(
            "- Sampled video frames with their timestamps are attached. Use them to judge visual moments "
            "(action, reactions, demonstrations), especially where there is little speech."
        )
    if window is not None:
        parts += [
            "",
            f"Note: this is one part of a longer video, covering {window[0]:.0f}s to {window[1]:.0f}s. "
            "Only choose clips inside this range.",
        ]
    if instruction:
        parts += [
            "",
            "The creator gave this preference. Follow it as long as it fits the rules above:",
            f'"""{instruction.strip()}"""',
        ]
    parts += ["", "Respond only with JSON matching the provided schema.", "", "TRANSCRIPT:", transcript_text]
    return "\n".join(parts)
