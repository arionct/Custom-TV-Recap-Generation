"""Output sanitization for local LLM responses."""

from src.rag import sanitize_model_output


def test_sanitize_strips_unused_tokens() -> None:
    assert sanitize_model_output("<unused5890>") == ""
    assert sanitize_model_output("Hello <unused123> world.") == "Hello  world."


def test_sanitize_preserves_normal_text() -> None:
    s = "Walt teaches chemistry."
    assert sanitize_model_output(s) == s


def test_sanitize_strips_leading_chatty_preamble() -> None:
    raw = "Okay, here's a recap based on the excerpts:\n\nWalt teaches chemistry."
    assert sanitize_model_output(raw) == "Walt teaches chemistry."
    assert sanitize_model_output("SHALL WE BEGIN?\n\nWalt teaches chemistry.") == "Walt teaches chemistry."


def test_sanitize_strips_leading_non_ascii_artifact() -> None:
    assert sanitize_model_output("ایطی\n\nWalt teaches chemistry.") == "Walt teaches chemistry."


def test_sanitize_strips_known_non_english_preamble() -> None:
    assert sanitize_model_output("feuilleton:\n\nWalt teaches chemistry.") == "Walt teaches chemistry."
