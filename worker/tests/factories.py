from clipforge_worker.transcript import Segment, Transcript, Word


def make_words(text: str, start: float = 0.0, word_dur: float = 0.4, gap: float = 0.1) -> list[Word]:
    """Evenly timed words from text; punctuation stays attached (so '.' marks sentence ends)."""
    words, t = [], start
    for token in text.split():
        words.append(Word(word=token, start=round(t, 3), end=round(t + word_dur, 3)))
        t += word_dur + gap
    return words


def sentence_transcript(n_sentences: int, words_per_sentence: int = 10, word_dur: float = 0.4, gap: float = 0.1) -> Transcript:
    """Transcript of n identical-length sentences, one segment each. With defaults each sentence
    lasts 10 * 0.5 = 5s (minus the trailing gap)."""
    segments, t = [], 0.0
    for i in range(n_sentences):
        body = " ".join(f"w{i}_{j}" for j in range(words_per_sentence - 1)) + f" end{i}."
        words = make_words(body, start=t, word_dur=word_dur, gap=gap)
        segments.append(Segment(start=words[0].start, end=words[-1].end, text=body, words=words))
        t = words[-1].end + gap
    return Transcript(language="en", duration=round(t, 3), segments=segments)
