from __future__ import annotations

import re
import time
import random
from pathlib import Path
from typing import Dict, List, Tuple

from bs4 import BeautifulSoup

try:
    import cloudscraper  # optional, but helpful if plain requests gets blocked
except ImportError:
    cloudscraper = None

import requests


BASE_URL = "https://subslikescript.com/series/Breaking_Bad-903747"
OUTPUT_DIR = Path("/Users/ariontripathi/cs 505/project/episode_transcripts")

# season -> number of episodes
SEASON_EPISODE_COUNTS: Dict[int, int] = {
    1: 7,
    2: 13,
    3: 13,
    4: 13,
    5: 16,
}

REMOVE_MUSIC_LINES = True
REQUEST_TIMEOUT = 30
SLEEP_BETWEEN_REQUESTS = (1.0, 2.0)  # min/max seconds


def make_session() -> requests.Session:
    """
    Create a session. Prefer cloudscraper if installed.
    """
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
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://subslikescript.com/",
        }
    )
    return session


def episode_url(season: int, episode: int) -> str:
    return f"{BASE_URL}/season-{season}/episode-{episode}"


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\xa0", " ")
    return text


def is_music_line(line: str) -> bool:
    """
    Remove obvious lyric/music lines.
    The simplest rule for this site is to drop lines containing ♪.
    """
    stripped = line.strip()
    if not stripped:
        return False

    if "♪" in stripped:
        return True

    lowered = stripped.lower()
    if lowered in {"[music]", "(music)", "music"}:
        return True

    return False


def clean_transcript_text(raw_text: str, remove_music: bool = True) -> str:
    raw_text = normalize_whitespace(raw_text)

    cleaned_lines: List[str] = []
    for line in raw_text.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()

        if remove_music and is_music_line(line):
            continue

        cleaned_lines.append(line)

    # collapse repeated blank lines to at most one blank line
    result_lines: List[str] = []
    previous_blank = False
    for line in cleaned_lines:
        is_blank = (line == "")
        if is_blank and previous_blank:
            continue
        result_lines.append(line)
        previous_blank = is_blank

    result = "\n".join(result_lines).strip()
    return result + "\n"


def extract_transcript(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # based on the structure you described
    script_div = soup.select_one("article.main-article div.full-script")
    if script_div is None:
        raise ValueError("Could not find article.main-article div.full-script")

    # turn <br> into newline markers before get_text
    for br in script_div.find_all("br"):
        br.replace_with("\n")

    raw_text = script_div.get_text(separator="\n")
    return clean_transcript_text(raw_text, remove_music=REMOVE_MUSIC_LINES)


def scrape_one_episode(session: requests.Session, season: int, episode: int) -> Tuple[bool, str]:
    url = episode_url(season, episode)

    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        return False, f"S{season:02d}E{episode:02d} request failed: {exc}"

    if response.status_code != 200:
        return False, f"S{season:02d}E{episode:02d} returned status {response.status_code}: {url}"

    try:
        transcript = extract_transcript(response.text)
    except Exception as exc:
        return False, f"S{season:02d}E{episode:02d} parse failed: {exc} ({url})"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"breaking_bad_s{season:02d}e{episode:02d}.txt"
    out_path.write_text(transcript, encoding="utf-8")

    return True, f"Saved {out_path.name}"


def main() -> None:
    session = make_session()
    failures: List[str] = []

    total = sum(SEASON_EPISODE_COUNTS.values())
    done = 0

    for season, episode_count in SEASON_EPISODE_COUNTS.items():
        for episode in range(1, episode_count + 1):
            done += 1
            print(f"[{done}/{total}] Scraping S{season:02d}E{episode:02d} ...")

            ok, message = scrape_one_episode(session, season, episode)
            print(message)

            if not ok:
                failures.append(message)

            time.sleep(random.uniform(*SLEEP_BETWEEN_REQUESTS))

    if failures:
        failure_log = OUTPUT_DIR / "failed_episodes.txt"
        failure_log.write_text("\n".join(failures) + "\n", encoding="utf-8")
        print(f"\nDone with some failures. See: {failure_log}")
    else:
        print("\nDone. All episode transcripts were saved successfully.")


if __name__ == "__main__":
    main()