"""Parser for WordPress episode summary pages (no network)."""

from scrape_breaking_bad_summaries import decode_episode_code, parse_summaries_from_html


def test_decode_episode_code() -> None:
    assert decode_episode_code("101") == (1, 1)
    assert decode_episode_code("213") == (2, 13)
    assert decode_episode_code("516") == (5, 16)


def test_parse_minimal_page() -> None:
    html = """
    <html><body><div class="entry-content">
    <p><strong>Episode 101: Pilot</strong></p>
    <p><strong>Teaser / Chapter 1 [0:00-1:00]</strong></p>
    <p>First line of story.</p>
    <p>Second line.</p>
    <p><strong>Episode 102: Next</strong></p>
    <p>Body for two.</p>
    </div></body></html>
    """
    rows = parse_summaries_from_html(html, "http://test")
    assert len(rows) == 2
    assert rows[0]["season"] == 1 and rows[0]["episode"] == 1
    assert "Teaser / Chapter 1" in rows[0]["text"]
    assert "First line of story" in rows[0]["text"]
    assert rows[1]["episode_id"] == "breaking_bad_s01e02"
    assert "Body for two" in rows[1]["text"]
