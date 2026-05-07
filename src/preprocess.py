"""
Build structured episode dataset from raw transcript files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Filename stem: <show_slug>_s<season>e<episode>  (e.g. breaking_bad_s02e05)
_EPISODE_STEM = re.compile(r"^(.+)_s(\d{2})e(\d{2})$")

# Known slugs -> canonical show title (extend when adding new shows)
SLUG_TO_SHOW_TITLE: dict[str, str] = {
    "breaking_bad": "Breaking Bad",
}

_SUBTITLE_CREDIT_PATTERNS = [
    re.compile(r"^subs collected, corrected\b.*", re.IGNORECASE),
    re.compile(r"^\"?breaking bad season .*?(bdrip|dvdrip|hdtv|tsv).*\"?$", re.IGNORECASE),
    re.compile(r"^sync, corrected by\b.*", re.IGNORECASE),
    re.compile(r"^www\.\s*addic7ed\.\s*com$", re.IGNORECASE),
    re.compile(r"^subtitles?:\s*$", re.IGNORECASE),
]


def slug_to_show_title(slug: str) -> str:
    if slug in SLUG_TO_SHOW_TITLE:
        return SLUG_TO_SHOW_TITLE[slug]
    return slug.replace("_", " ").title()


def parse_transcript_stem(stem: str) -> tuple[str, int, int, str]:
    """
    Parse a filename stem (no .txt) into (show_slug, season, episode, episode_id).

    Example: "breaking_bad_s02e05" -> ("breaking_bad", 2, 5, "breaking_bad_s02e05")
    """
    m = _EPISODE_STEM.match(stem)
    if not m:
        raise ValueError(f"Cannot parse episode stem: {stem!r}")
    slug = m.group(1)
    season = int(m.group(2))
    episode = int(m.group(3))
    episode_id = f"{slug}_s{season:02d}e{episode:02d}"
    return slug, season, episode, episode_id


def clean_transcript_text(text: str) -> str:
    """
    Remove subtitle-release artifacts that are not story content.

    The raw source occasionally includes release credits, site watermarks, and inline
    positioning tags. These can confuse retrieval-grounded recaps and overlap metrics.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\{pos\([^}]+\)\}", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\{\*([^}]*)\}", r"\1", text)

    kept: list[str] = []
    previous_blank = False
    for raw_line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if any(p.match(line) for p in _SUBTITLE_CREDIT_PATTERNS):
            continue
        is_blank = not line
        if is_blank and previous_blank:
            continue
        kept.append(line)
        previous_blank = is_blank

    return "\n".join(kept).strip() + "\n"


def parse_transcript_path(path: Path) -> tuple[str, int, int, str, str]:
    """
    From a .txt file path, return (show title, season, episode, episode_id, full text).
    """
    stem = path.stem
    slug, season, episode, eid = parse_transcript_stem(stem)
    show = slug_to_show_title(slug)
    text = clean_transcript_text(path.read_text(encoding="utf-8", errors="replace"))
    return show, season, episode, eid, text


def build_episodes(
    transcript_dir: Path,
) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    for p in sorted(transcript_dir.glob("*.txt")):
        if p.name.startswith("."):
            continue
        show, season, episode, eid, text = parse_transcript_path(p)
        rows.append(
            {
                "show": show,
                "season": season,
                "episode": episode,
                "episode_id": eid,
                "text": text,
            }
        )
    # Deterministic: earlier seasons/episodes first (helps debugging and RAG order)
    rows.sort(key=lambda r: (r["show"], r["season"], r["episode"]))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Build episodes.json from raw transcripts")
    ap.add_argument(
        "--transcript-dir",
        type=Path,
        default=None,
        help="Directory with breaking_bad_sXXeYY.txt (default: data/raw/episode_transcripts under project root)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSON path (default: data/processed/episodes.json under project root)",
    )
    args = ap.parse_args()
    project_root = Path(__file__).resolve().parent.parent
    transcript_dir = args.transcript_dir or (project_root / "data" / "raw" / "episode_transcripts")
    out_path = args.out or (project_root / "data" / "processed" / "episodes.json")
    if not transcript_dir.is_dir():
        print(f"Transcript directory not found: {transcript_dir}", file=sys.stderr)
        return 1
    episodes = build_episodes(transcript_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(episodes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(episodes)} episodes to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
