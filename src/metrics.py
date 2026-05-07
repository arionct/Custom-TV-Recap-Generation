"""
Lexical overlap metrics between generated text and episode corpora.

Useful for quantitative checks on retrieval leakage vs parametric knowledge:
compare overlap with episodes strictly before k, at k, and strictly after k.
"""

from __future__ import annotations

import re
from typing import Any

from src.episode_order import (
    at_stopping_episode,
    strictly_after,
    strictly_before,
)

_WORD_RE = re.compile(r"[a-z0-9']+", re.IGNORECASE)
_CAP_ENTITY_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\b")
_ENTITY_STOP_PHRASES = {"episode", "pilot", "recap", "season"}

_STOPWORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "also",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "doing",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "itself",
    "just",
    "me",
    "more",
    "most",
    "my",
    "myself",
    "no",
    "nor",
    "not",
    "now",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "ours",
    "out",
    "over",
    "own",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "will",
    "with",
    "would",
    "you",
    "your",
    "yours",
}


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens (alphanumeric + apostrophe)."""
    return [m.group(0).lower() for m in _WORD_RE.finditer(text)]


def content_tokens(text: str) -> list[str]:
    """Tokens used for higher-signal overlap checks: lowercase, non-stopword, len >= 3."""
    return [t for t in tokenize(text) if len(t) >= 3 and t not in _STOPWORDS]


def capitalized_entities(text: str) -> set[str]:
    """Cheap named-entity-ish phrases for spoiler smoke tests."""
    out: set[str] = set()
    for m in _CAP_ENTITY_RE.finditer(text):
        phrase = " ".join(tok.lower() for tok in m.group(0).split())
        toks = phrase.split()
        if not toks or all(t in _STOPWORDS for t in toks):
            continue
        if phrase in _ENTITY_STOP_PHRASES:
            continue
        out.add(phrase)
    return out


def token_coverage(gen_tokens: list[str], ref_tokens: list[str]) -> float:
    """
    Fraction of generated tokens (multiset positions) that appear in reference
    token multiset (bag overlap normalized by len(gen)).
    """
    if not gen_tokens:
        return 0.0
    ref_set = set(ref_tokens)
    hits = sum(1 for t in gen_tokens if t in ref_set)
    return hits / len(gen_tokens)


def build_region_texts(
    rows: list[dict[str, Any]],
    k_season: int,
    k_episode: int,
) -> tuple[str, str, str]:
    """
    Split the show corpus into three disjoint strings for metric comparisons.

    - prior: episodes strictly before stopping (k_season, k_episode)
    - at_k: only the stopping episode body text
    - future: episodes strictly after stopping (potential spoiler sources if the
      model overlaps strongly here while retrieval excludes them)
    """
    ks, ke = k_season, k_episode

    def key(r: dict[str, Any]) -> tuple[int, int]:
        return int(r["season"]), int(r["episode"])

    prior_rows = sorted(
        [
            r
            for r in rows
            if strictly_before(int(r["season"]), int(r["episode"]), ks, ke)
        ],
        key=key,
    )
    at_rows = sorted(
        [
            r
            for r in rows
            if at_stopping_episode(int(r["season"]), int(r["episode"]), ks, ke)
        ],
        key=key,
    )
    fut_rows = sorted(
        [
            r
            for r in rows
            if strictly_after(int(r["season"]), int(r["episode"]), ks, ke)
        ],
        key=key,
    )
    join = lambda rs: "\n\n".join(str(r["text"]) for r in rs)
    return join(prior_rows), join(at_rows), join(fut_rows)


def overlap_report(
    generated: str,
    prior_text: str,
    at_k_text: str,
    future_text: str,
) -> dict[str, float | int | list[str]]:
    """
    Token coverage of generation against three disjoint corpus regions.

    Returns raw counts plus coverage scores in [0, 1].
    """
    gen_toks = tokenize(generated)
    prior_toks = tokenize(prior_text)
    at_k_toks = tokenize(at_k_text)
    fut_toks = tokenize(future_text)
    gen_content = content_tokens(generated)
    prior_content = content_tokens(prior_text)
    at_k_content = content_tokens(at_k_text)
    fut_content = content_tokens(future_text)
    future_only = set(fut_content) - set(prior_content) - set(at_k_content)
    future_only_hits = sorted({t for t in gen_content if t in future_only})
    gen_entities = capitalized_entities(generated)
    prior_entities = capitalized_entities(prior_text)
    at_k_entities = capitalized_entities(at_k_text)
    future_entities = capitalized_entities(future_text)
    future_only_entities = future_entities - prior_entities - at_k_entities
    future_only_entity_hits = sorted(gen_entities & future_only_entities)
    return {
        "gen_tokens": len(gen_toks),
        "gen_content_tokens": len(gen_content),
        "prior_tokens": len(prior_toks),
        "at_k_tokens": len(at_k_toks),
        "future_tokens": len(fut_toks),
        "coverage_prior": token_coverage(gen_toks, prior_toks),
        "coverage_at_k": token_coverage(gen_toks, at_k_toks),
        "coverage_future": token_coverage(gen_toks, fut_toks),
        "content_coverage_prior": token_coverage(gen_content, prior_content),
        "content_coverage_at_k": token_coverage(gen_content, at_k_content),
        "content_coverage_future": token_coverage(gen_content, fut_content),
        "future_only_content_hits": len(future_only_hits),
        "future_only_content_hit_ratio": (
            len(future_only_hits) / len(set(gen_content)) if gen_content else 0.0
        ),
        "future_only_content_terms": future_only_hits[:30],
        "future_only_entity_hits": len(future_only_entity_hits),
        "future_only_entities": future_only_entity_hits[:30],
    }


def _char_bigrams(s: str) -> set[tuple[str, str]]:
    t = re.sub(r"\s+", " ", s.lower())
    if len(t) < 2:
        return set()
    return set(zip(t, t[1:]))


def char_bigram_jaccard(a: str, b: str) -> float:
    """Character bigram overlap in [0, 1]; cheap surface proxy for 'semantic' overlap."""
    A, B = _char_bigrams(a), _char_bigrams(b)
    if not A and not B:
        return 1.0
    if not A or not B:
        return 0.0
    inter = len(A & B)
    union = len(A | B)
    return inter / union if union else 0.0


def liu_naacl2022_style_proxy(generated: str, retrieved_source: str) -> dict[str, float]:
    """
    Lightweight reference-free signals inspired by Liu et al., NAACL 2022
    (semantic correlation + compression ratio — here: token ratio + char bigram Jaccard).

    Full paper uses PLM-based semantic alignment; these scalars are fast stand-ins for tooling.
    See: https://aclanthology.org/2022.naacl-main.153/
    """
    if not retrieved_source.strip():
        return {
            "compression_token_ratio": 0.0,
            "char_bigram_jaccard_gen_vs_retrieved": 0.0,
            "sdc_star_proxy_char_jaccard": 0.0,
            "retrieved_content_coverage": 0.0,
            "unsupported_content_token_ratio": 0.0,
        }
    gt = tokenize(generated)
    st = tokenize(retrieved_source)
    comp = len(gt) / max(len(st), 1)
    jac = char_bigram_jaccard(generated, retrieved_source)
    compression_penalty = 1.0 - min(comp, 1.0)
    denom = jac + compression_penalty
    sdc_star_proxy = (
        (2.0 * jac * compression_penalty / denom) if denom > 0 else 0.0
    )
    gen_content = content_tokens(generated)
    src_content = content_tokens(retrieved_source)
    src_set = set(src_content)
    unsupported = sorted({t for t in gen_content if t not in src_set})
    return {
        "compression_token_ratio": round(comp, 4),
        "char_bigram_jaccard_gen_vs_retrieved": round(jac, 4),
        "sdc_star_proxy_char_jaccard": round(sdc_star_proxy, 4),
        "retrieved_content_coverage": round(token_coverage(gen_content, src_content), 4),
        "unsupported_content_token_ratio": round(
            len(unsupported) / len(set(gen_content)) if gen_content else 0.0,
            4,
        ),
    }
