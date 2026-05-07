"""
Scrape per-act Breaking Bad episode summaries from the Studying Breaking Bad
WordPress site and write `data/processed/episode_summaries.json` for RAG.

Page structure (typical):
  - Container: div.entry-content
  - Episode: <p><strong>Episode NNN: Title</strong></p>  (NNN = 1ss eee, e.g. 201 = S2E1)
  - Chapters: <p><strong>Teaser / Chapter 1 [timecodes]</strong></p>, etc.
  - Body: following <p> nodes until the next episode header.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Optional Cloudflare-friendly session (same idea as scrape_breaking_bad.py)
try:
    import cloudscraper
except ImportError:
    cloudscraper = None

BASE = "https://studyingbreakingbadcourse.wordpress.com/episoderesources/episode-summaries/"

# One URL per "page" of summaries. Season 3+ use historical "coming-soon" slugs but are complete.
SEASON_SUMMARY_PAGES: list[str] = [
    "season-1/",
    "season-2/",
    "summaries-from-season-3-coming-soon/",
    "summaries-from-season-4-coming-soon/",
    "summaries-from-season-5-part-1-coming-soon/",
    "summaries-from-season-5-part-2-coming-soon/",
]

# For validation (total 62)
SEASON_EPISODE_COUNTS: dict[int, int] = {
    1: 7,
    2: 13,
    3: 13,
    4: 13,
    5: 16,
}

REQUEST_TIMEOUT = 45
SLEEP_BETWEEN_REQUESTS = (1.0, 2.0)

EPISODE_HEADER_RE = re.compile(
    r"^Episode\s+(\d{3})\s*:\s*(.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)


def project_root() -> Path:
    return Path(__file__).resolve().parent


def make_session() -> requests.Session:
    if cloudscraper is not None:
        session = cloudscraper.create_scraper()
    else:
        session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session


def decode_episode_code(code_str: str) -> tuple[int, int]:
    """
    Site uses a 3-digit code ABC: A = season (1–5), BC = episode within season.
    Examples: 101 -> S1E1, 213 -> S2E13, 516 -> S5E16.
    """
    code_str = code_str.strip()
    if len(code_str) != 3 or not code_str.isdigit():
        raise ValueError(f"Unexpected episode code: {code_str!r}")
    season = int(code_str[0])
    episode = int(code_str[1:3])
    return season, episode


def normalize_text(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\xa0", " ")
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def paragraph_plain_text(p: Any) -> str:
    for br in p.find_all("br"):
        br.replace_with("\n")
    return normalize_text(p.get_text(separator="\n"))


def parse_summaries_from_html(html: str, source_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    entry = soup.select_one("div.entry-content")
    if entry is None:
        raise ValueError(f"No div.entry-content in {source_url}")

    segments: list[tuple[tuple[int, int], str, str, str]] = []
    current_key: tuple[int, int] | None = None
    current_code: str | None = None
    current_title: str | None = None
    lines: list[str] = []

    def flush() -> None:
        nonlocal current_key, current_code, current_title, lines
        if current_key is None:
            return
        assert current_code is not None and current_title is not None
        body = normalize_text("\n\n".join(lines))
        segments.append((current_key, current_code, current_title, body))
        lines = []
        current_key = None
        current_code = None
        current_title = None

    for p in entry.find_all("p"):
        text = paragraph_plain_text(p)
        if not text:
            continue

        m = EPISODE_HEADER_RE.match(text)
        if m:
            flush()
            code_str, title = m.group(1), m.group(2).strip()
            season, ep_num = decode_episode_code(code_str)
            current_key = (season, ep_num)
            current_code = code_str
            current_title = title
            lines.append(f"Episode {code_str}: {title}")
            continue

        if current_key is None:
            low = text.lower()
            if "share this:" in low or "loading" in low[:20]:
                continue
            continue

        lines.append(text)

    flush()

    rows: list[dict[str, Any]] = []
    for (season, ep_num), code_str, title, body in segments:
        slug_season = f"{season:02d}"
        slug_ep = f"{ep_num:02d}"
        eid = f"breaking_bad_s{slug_season}e{slug_ep}"
        rows.append(
            {
                "show": "Breaking Bad",
                "season": season,
                "episode": ep_num,
                "episode_id": eid,
                "title": title,
                "source_code": code_str,
                "source_url": source_url,
                "text": body,
            }
        )
    return rows


def validate_coverage(rows: list[dict[str, Any]]) -> None:
    by_season: dict[int, list[int]] = {}
    for r in rows:
        s, e = int(r["season"]), int(r["episode"])
        by_season.setdefault(s, []).append(e)

    for s, expected in SEASON_EPISODE_COUNTS.items():
        got = sorted(by_season.get(s, []))
        if len(got) != expected:
            raise ValueError(
                f"Season {s}: expected {expected} episodes, got {len(got)}: {got}"
            )
        if got != list(range(1, expected + 1)):
            raise ValueError(f"Season {s}: missing or duplicate episode indices: {got}")

    if len(rows) != sum(SEASON_EPISODE_COUNTS.values()):
        raise ValueError(f"Expected 62 episodes total, got {len(rows)}")


def strip_metadata_for_rag(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Schema expected by src/rag.py: show, season, episode, episode_id, text."""
    return [
        {
            "show": r["show"],
            "season": r["season"],
            "episode": r["episode"],
            "episode_id": r["episode_id"],
            "text": r["text"],
        }
        for r in rows
    ]


def fetch_page(session: requests.Session, path: str) -> str:
    url = urljoin(BASE, path)
    r = session.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.text


def main() -> int:
    ap = argparse.ArgumentParser(description="Scrape BB episode summaries into episode_summaries.json")
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSON (default: data/processed/episode_summaries.json)",
    )
    ap.add_argument(
        "--keep-meta",
        action="store_true",
        help="Keep title, source_code, source_url in each row (default: RAG-only fields)",
    )
    args = ap.parse_args()

    root = project_root()
    out_path = args.out or (root / "data" / "processed" / "episode_summaries.json")

    session = make_session()
    all_rows: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()

    for path in SEASON_SUMMARY_PAGES:
        url = urljoin(BASE, path)
        print(f"Fetching {url} ...")
        try:
            html = fetch_page(session, path)
        except requests.RequestException as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        try:
            page_rows = parse_summaries_from_html(html, url)
        except Exception as e:
            print(f"Parse failed for {url}: {e}", file=sys.stderr)
            return 1

        for r in page_rows:
            key = (int(r["season"]), int(r["episode"]))
            if key in seen:
                print(f"WARNING: duplicate {key} from {url}", file=sys.stderr)
                continue
            seen.add(key)
            all_rows.append(r)

        time.sleep(random.uniform(*SLEEP_BETWEEN_REQUESTS))

    all_rows.sort(key=lambda r: (int(r["season"]), int(r["episode"])))

    try:
        validate_coverage(all_rows)
    except ValueError as e:
        print(f"Validation failed: {e}", file=sys.stderr)
        print(f"Collected {len(all_rows)} episodes; keys: {sorted(seen)[:20]} ...", file=sys.stderr)
        return 1

    if not args.keep_meta:
        all_rows = strip_metadata_for_rag(all_rows)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(all_rows)} episodes to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
