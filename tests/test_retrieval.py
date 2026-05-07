"""
Guarantee deterministic retrieval never includes episodes after the stopping point k.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.chunking import chunk_by_words, chunk_episode_texts
from src.preprocess import clean_transcript_text, parse_transcript_stem, slug_to_show_title
from src.rag import (
    build_chunk_list,
    build_user_prompt,
    clamp_single_episode_headings,
    episode_lte,
    load_episodes_json,
    resolve_episodes_path,
    select_chunks_for_budget,
    select_episodes_for_show,
    select_episodes_until,
    take_tail_max_chunks,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EPISODES_JSON = PROJECT_ROOT / "data" / "processed" / "episodes.json"


def test_parse_transcript_stem():
    slug, s, e, eid = parse_transcript_stem("breaking_bad_s02e05")
    assert slug == "breaking_bad"
    assert s == 2
    assert e == 5
    assert eid == "breaking_bad_s02e05"


def test_parse_rejects_invalid_stem():
    with pytest.raises(ValueError, match="parse"):
        parse_transcript_stem("not_a_valid_stem")


def test_slug_to_show_title():
    assert slug_to_show_title("breaking_bad") == "Breaking Bad"


def test_clean_transcript_text_removes_subtitle_artifacts():
    raw = (
        "Subs collected, corrected and if necessary adapted by TRONAR for\n\n"
        '"Breaking Bad Season 1, 2, 3, 4 & 5 + Extras BDRip DVDRip HDTV TSV"\n\n'
        "{pos(192,210)}Real story line.\n"
        "{*kept alternate text}\n"
        "www. addic7ed. com\n"
    )
    cleaned = clean_transcript_text(raw)
    assert "Subs collected" not in cleaned
    assert "BDRip" not in cleaned
    assert "{pos" not in cleaned
    assert "Real story line." in cleaned
    assert "kept alternate text" in cleaned


def test_episode_lte():
    assert episode_lte(1, 1, 2, 5) is True
    assert episode_lte(2, 5, 2, 5) is True
    assert episode_lte(2, 4, 2, 5) is True
    assert episode_lte(2, 6, 2, 5) is False
    assert episode_lte(3, 1, 2, 5) is False


def test_filter_excludes_future_episode_same_season():
    rows = [
        {
            "show": "Breaking Bad",
            "season": 2,
            "episode": 5,
            "episode_id": "breaking_bad_s02e05",
            "text": "ONLY_S02E05_MARK",
        },
        {
            "show": "Breaking Bad",
            "season": 2,
            "episode": 6,
            "episode_id": "breaking_bad_s02e06",
            "text": "S02E06_SHOULD_NEVER_APPEAR",
        },
    ]
    out = select_episodes_until(rows, "breaking bad", 2, 5)
    assert len(out) == 1
    assert out[0]["episode_id"] == "breaking_bad_s02e05"
    assert "S02E06" not in out[0]["text"]


def test_s02e05_never_includes_s02e06_in_chunks():
    """
    Chunks are built only from selected episodes; S02E06 must be absent for k=S02E05.
    """
    rows = [
        {
            "show": "Breaking Bad",
            "season": 2,
            "episode": 5,
            "episode_id": "breaking_bad_s02e05",
            "text": "alpha " * 500,
        },
        {
            "show": "Breaking Bad",
            "season": 2,
            "episode": 6,
            "episode_id": "breaking_bad_s02e06",
            "text": "BANNED_S02E06_TOKEN " * 500,
        },
    ]
    chosen = select_episodes_until(rows, "Breaking Bad", 2, 5)
    flat = build_chunk_list(chosen, chunk_size=100)
    joined = json.dumps(flat)
    assert "BANNED_S02E06_TOKEN" not in joined


def test_filter_excludes_later_seasons():
    rows = [
        {"show": "X", "season": 1, "episode": 1, "episode_id": "a", "text": "a"},
        {"show": "X", "season": 2, "episode": 1, "episode_id": "b", "text": "b"},
    ]
    out = select_episodes_until(rows, "x", 1, 1)
    assert [r["episode_id"] for r in out] == ["a"]


def test_real_episodes_json_if_present():
    if not EPISODES_JSON.is_file():
        pytest.skip("Run: python -m src.preprocess")
    data = load_episodes_json(EPISODES_JSON)
    sel = select_episodes_until(data, "Breaking Bad", 2, 5)
    ids = [r["episode_id"] for r in sel]
    assert "breaking_bad_s02e05" in ids
    assert "breaking_bad_s02e06" not in ids
    for r in sel:
        s, e = int(r["season"]), int(r["episode"])
        assert s < 2 or (s == 2 and e <= 5)


def test_tail_chunk_limit_keeps_chronology_tail():
    flat = [{"a": i} for i in range(10)]
    t = take_tail_max_chunks(flat, 3)
    assert t == [{"a": 7}, {"a": 8}, {"a": 9}]


def test_episode_balanced_chunk_limit_keeps_early_episode_context():
    flat = []
    for eid in ["breaking_bad_s01e01", "breaking_bad_s01e02", "breaking_bad_s01e03"]:
        for idx in range(6):
            flat.append({"episode_id": eid, "chunk_index": idx, "text": f"{eid}-{idx}"})
    selected = select_chunks_for_budget(flat, 12, strategy="episode_balanced")
    by_ep = {}
    for c in selected:
        by_ep.setdefault(c["episode_id"], []).append(c["chunk_index"])
    assert set(by_ep) == {
        "breaking_bad_s01e01",
        "breaking_bad_s01e02",
        "breaking_bad_s01e03",
    }
    assert all(len(v) == 4 for v in by_ep.values())


def test_select_episodes_for_show_includes_all_seasons():
    rows = [
        {"show": "X", "season": 1, "episode": 1, "episode_id": "a", "text": "a"},
        {"show": "X", "season": 9, "episode": 9, "episode_id": "z", "text": "z"},
    ]
    out = select_episodes_for_show(rows, "x")
    assert [r["episode_id"] for r in out] == ["a", "z"]


def test_resolve_episodes_path_summary_suffix():
    p = resolve_episodes_path("summary", None)
    assert p.name == "episode_summaries.json"


def test_baseline_prompt_has_no_excerpt_block():
    text = build_user_prompt("Breaking Bad", 1, 3, [], retrieval_mode="none")
    assert "No transcript or summary text is included" in text
    assert "Excerpts" not in text


def test_retrieval_prompt_lists_chunks():
    chunks = [
        {"episode_id": "breaking_bad_s01e01", "chunk_index": "0", "text": "foo bar"},
    ]
    text = build_user_prompt("Breaking Bad", 1, 1, chunks, retrieval_mode="full")
    assert "[breaking_bad_s01e01 part 0]" in text
    assert "foo bar" in text
    assert "one episode only" in text.lower() or "write one recap" in text.lower()
    assert "Included episode_id labels" in text


def test_retrieval_prompt_multi_episode_uses_cumulative_wording():
    chunks = [
        {"episode_id": "breaking_bad_s01e01", "chunk_index": "0", "text": "a"},
        {"episode_id": "breaking_bad_s01e02", "chunk_index": "0", "text": "b"},
    ]
    text = build_user_prompt("Breaking Bad", 1, 2, chunks, retrieval_mode="full")
    low = text.lower()
    assert "cohesive cumulative recap" in low
    assert "not an episode-by-episode index" in low
    assert "do not use episode headings" in low
    assert "target 250-350 words" in low
    assert "grounding only" in low
    assert "These excerpts cover **one episode only**" not in text


def test_clamp_truncates_hallucinated_episode_headings():
    raw = "**Episode 1:**\nPilot beats.\n\n**Episode 2:**\nFabricated continuation.\n"
    out = clamp_single_episode_headings(raw, "breaking_bad_s01e01")
    assert "Fabricated" not in out
    assert "Pilot beats" in out


def test_clamp_keeps_redundant_same_episode_headings():
    raw = "**Episode 1:**\nA\n\n**Episode 1:**\nB\n"
    out = clamp_single_episode_headings(raw, "breaking_bad_s01e01")
    assert "B" in out


def test_chunking_word_count():
    words = ["w"] * 500
    text = " ".join(words)
    chunks = chunk_by_words(text, chunk_size=200)
    assert len(chunks) == 3
    assert len(chunks[0].split()) == 200
    segs = chunk_episode_texts("eid1", "x " * 350, chunk_size=200)
    assert len(segs) == 2
    assert segs[0]["episode_id"] == "eid1"
