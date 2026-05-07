"""Lexical metrics and corpus region splits."""

from src.metrics import (
    build_region_texts,
    capitalized_entities,
    content_tokens,
    overlap_report,
    tokenize,
)


def test_tokenize_strips_case_and_punct():
    assert tokenize("Hello, world!!") == ["hello", "world"]


def test_content_tokens_drop_stopwords():
    assert content_tokens("The quick and bright RV") == ["quick", "bright"]


def test_capitalized_entities_extracts_simple_names():
    assert "tuco salamanca" in capitalized_entities("Walt meets Tuco Salamanca.")


def test_build_region_texts_disjoint():
    rows = [
        {"season": 1, "episode": 1, "text": "aaa"},
        {"season": 2, "episode": 1, "text": "bbb"},
        {"season": 2, "episode": 2, "text": "ccc"},
        {"season": 2, "episode": 3, "text": "ddd"},
    ]
    prior, at_k, fut = build_region_texts(rows, 2, 2)
    assert "aaa" in prior and "bbb" in prior
    assert at_k.strip() == "ccc"
    assert fut.strip() == "ddd"


def test_overlap_report_future_signal():
    gen = "alpha beta gamma unusualfuturetoken"
    prior = "alpha beta"
    at_k = "gamma"
    future = "unusualfuturetoken xyz"
    r = overlap_report(gen, prior, at_k, future)
    assert r["coverage_prior"] > 0
    assert r["coverage_future"] > 0
    assert r["future_only_content_hits"] == 1
    assert r["future_only_content_terms"] == ["unusualfuturetoken"]


def test_overlap_report_future_only_entities():
    r = overlap_report(
        "Walt mentions Tuco Salamanca.",
        "Walt knows Jesse.",
        "Walt sees Krazy Eight.",
        "Tuco Salamanca arrives later.",
    )
    assert r["future_only_entity_hits"] == 1
    assert r["future_only_entities"] == ["tuco salamanca"]


def test_liu_proxy_nonempty_retrieval():
    from src.metrics import liu_naacl2022_style_proxy

    g = "Walter White teaches chemistry in Albuquerque."
    src = "Walter White is a chemistry teacher in Albuquerque New Mexico."
    p = liu_naacl2022_style_proxy(g, src)
    assert "compression_token_ratio" in p
    assert "sdc_star_proxy_char_jaccard" in p
    assert "retrieved_content_coverage" in p
    assert p["char_bigram_jaccard_gen_vs_retrieved"] > 0.1
