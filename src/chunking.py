"""
Chunking for transcripts (fixed word windows) and for scraped summaries
(one chunk per Teaser/Act/Credits chapter).
"""

from __future__ import annotations

import re

# Target band ~300–500 words; default center of the range
DEFAULT_CHUNK_WORDS = 400

# Lines that start a new summary section (Studying Breaking Bad site format).
# Examples: "Teaser / Chapter 1 [0:00-4:06]", "Act One / Chapter 2 / 4:12-13:27",
# "Act Four/ Chapters 4 (cont.) & 5 [39:49-57:11]", "Credits / Chapter 6 [...]"
SUMMARY_CHAPTER_HEADER_RE = re.compile(
    r"(?m)^(Teaser|Prologue|Credits|Act\s+(?:One|Two|Three|Four|Five))[^\n]*Chapter[^\n]*\s*$",
    re.IGNORECASE,
)


def chunk_by_words(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_WORDS,
) -> list[str]:
    """
    Split text into chunks of at most `chunk_size` words (whitespace-separated).
    No overlap. Empty or whitespace-only input yields [].
    """
    words = text.split()
    if not words:
        return []
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    out: list[str] = []
    for i in range(0, len(words), chunk_size):
        out.append(" ".join(words[i : i + chunk_size]))
    return out


def chunk_episode_texts(
    episode_id: str,
    text: str,
    chunk_size: int = DEFAULT_CHUNK_WORDS,
) -> list[dict[str, str]]:
    """
    Return one dict per chunk with stable labels for prompt assembly.
    """
    parts = chunk_by_words(text, chunk_size=chunk_size)
    return [
        {
            "episode_id": episode_id,
            "chunk_index": j,
            "text": t,
        }
        for j, t in enumerate(parts)
    ]


def chunk_episode_summaries_by_chapters(
    episode_id: str,
    text: str,
    *,
    fallback_word_size: int = DEFAULT_CHUNK_WORDS,
) -> list[dict[str, str]]:
    """
    Split scraped episode summary text into one chunk per chapter block.

    Preamble text before the first chapter header (usually the
    ``Episode NNN: Title`` line) is prepended to the first chapter chunk.
    If no chapter headers are found, falls back to fixed word chunking.
    """
    matches = list(SUMMARY_CHAPTER_HEADER_RE.finditer(text))
    if not matches:
        return chunk_episode_texts(episode_id, text, chunk_size=fallback_word_size)

    segments: list[str] = []
    preamble = text[: matches[0].start()].strip()
    for i, m in enumerate(matches):
        seg_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segment = text[m.start() : seg_end].strip()
        if i == 0 and preamble:
            segment = f"{preamble}\n\n{segment}".strip()
        segments.append(segment)

    return [
        {"episode_id": episode_id, "chunk_index": j, "text": t}
        for j, t in enumerate(segments)
    ]
