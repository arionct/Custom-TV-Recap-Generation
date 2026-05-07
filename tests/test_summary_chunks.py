"""Chapter-based chunking for scraped episode summaries."""

import json
from pathlib import Path

import pytest

from src.chunking import (
    SUMMARY_CHAPTER_HEADER_RE,
    chunk_episode_summaries_by_chapters,
)

PROJECT = Path(__file__).resolve().parent.parent


def test_chapter_header_regex_variants() -> None:
    samples = [
        "Teaser / Chapter 1 [0:00-4:06]",
        "Prologue / Chapter 1 / 0:00-5:32",
        "Act One / Chapter 2 [5:32-14:18]",
        "Act Four/ Chapters 4 (cont.) & 5 [39:49-57:11]",
        "Act Three / Chapters 4-5 [26:14-35:08]",
        "Act Three / Chapter 4 / 28:07-35:34",
        "Credits / Chapter 6 [47:26-48:06]",
    ]
    for s in samples:
        assert SUMMARY_CHAPTER_HEADER_RE.search(s), repr(s)


@pytest.mark.skipif(
    not (PROJECT / "data/processed/episode_summaries.json").is_file(),
    reason="episode_summaries.json not present",
)
def test_pilot_has_multiple_chapter_chunks() -> None:
    rows = json.loads(
        (PROJECT / "data/processed/episode_summaries.json").read_text(encoding="utf-8")
    )
    pilot = next(r for r in rows if r["episode_id"] == "breaking_bad_s01e01")
    chunks = chunk_episode_summaries_by_chapters(pilot["episode_id"], pilot["text"])
    assert len(chunks) >= 5
    assert "Teaser / Chapter 1" in chunks[0]["text"]
    assert "Episode 101:" in chunks[0]["text"]


def test_fallback_when_no_headers() -> None:
    text = "Just some prose with no act structure. " * 50
    chunks = chunk_episode_summaries_by_chapters(
        "breaking_bad_s01e01", text, fallback_word_size=20
    )
    assert len(chunks) >= 2

