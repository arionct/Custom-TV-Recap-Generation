"""
Run recap generation and lexical overlap metrics (prior / at k / future).

Use for comparing baseline (no retrieval) vs transcript RAG vs summary RAG.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.metrics import build_region_texts, liu_naacl2022_style_proxy, overlap_report
from src.rag import (
    load_episodes_json,
    resolve_episodes_path,
    run_recap,
    select_episodes_for_show,
)


def evaluate_one(
    show: str,
    k_season: int,
    k_episode: int,
    *,
    corpus: str = "transcript",
    retrieval_mode: str = "full",
    chunk_size: int | None = None,
    max_total_chunks: int | None = None,
    chunk_selection: str = "episode_balanced",
    config_path: Path | None = None,
    episodes_path: Path | None = None,
) -> dict[str, Any]:
    from src.chunking import DEFAULT_CHUNK_WORDS

    cs = chunk_size if chunk_size is not None else DEFAULT_CHUNK_WORDS
    corpus_path = resolve_episodes_path(corpus, episodes_path)
    data = load_episodes_json(corpus_path)
    show_rows = select_episodes_for_show(data, show)
    if not show_rows:
        raise ValueError(f"No rows for show {show!r} in corpus.")
    prior_t, at_k_t, fut_t = build_region_texts(show_rows, k_season, k_episode)
    text, dbg = run_recap(
        show,
        k_season,
        k_episode,
        chunk_size=cs,
        max_total_chunks=max_total_chunks,
        config_path=config_path,
        episodes_path=corpus_path,
        corpus=corpus,
        retrieval_mode=retrieval_mode,
        chunk_selection=chunk_selection,  # type: ignore[arg-type]
        return_debug=True,
    )
    metrics = overlap_report(text, prior_t, at_k_t, fut_t)
    rcat = str(dbg.get("retrieved_concat") or "")
    metrics["liu_naacl2022_proxy"] = liu_naacl2022_style_proxy(text, rcat)
    metrics["elapsed_seconds"] = dbg.get("elapsed_seconds")
    metrics["chunks_in_prompt"] = dbg.get("chunks_in_prompt")
    metrics["chunk_selection"] = dbg.get("chunk_selection")
    metrics["included_episode_ids"] = dbg.get("included_episode_ids")
    metrics["omitted_episode_ids"] = dbg.get("omitted_episode_ids")
    return {
        "show": show,
        "stopping_season": k_season,
        "stopping_episode": k_episode,
        "corpus": corpus,
        "retrieval_mode": retrieval_mode,
        "generated": text,
        "metrics": metrics,
    }


def main() -> int:
    from src.chunking import DEFAULT_CHUNK_WORDS

    ap = argparse.ArgumentParser(
        description="Generate a recap and report token coverage vs prior / at-k / future corpus text."
    )
    ap.add_argument("--show", type=str, required=True)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--episode", type=int, required=True)
    ap.add_argument(
        "--corpus",
        choices=("transcript", "summary"),
        default="transcript",
        help="Which processed JSON to use (default: transcripts).",
    )
    ap.add_argument(
        "--retrieval",
        choices=("full", "none"),
        default="full",
        help="full: episode-filtered chunks in the prompt; none: no-retrieval baseline.",
    )
    ap.add_argument("--chunk-words", type=int, default=DEFAULT_CHUNK_WORDS)
    ap.add_argument("--max-chunks", type=int, default=None)
    ap.add_argument(
        "--chunk-selection",
        choices=("episode_balanced", "tail"),
        default="episode_balanced",
        help="How to apply --max-chunks when retrieval is full.",
    )
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument(
        "--episodes",
        type=Path,
        default=None,
        help="Override path to processed JSON (must match --corpus schema).",
    )
    ap.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write full result dict (including generated text) as JSON.",
    )
    ap.add_argument(
        "--metrics-only",
        action="store_true",
        help="Print only the metrics JSON line (smaller than full output).",
    )
    args = ap.parse_args()

    try:
        result = evaluate_one(
            args.show,
            args.season,
            args.episode,
            corpus=args.corpus,
            retrieval_mode=args.retrieval,
            chunk_size=args.chunk_words,
            max_total_chunks=args.max_chunks,
            chunk_selection=args.chunk_selection,
            config_path=args.config,
            episodes_path=args.episodes,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.metrics_only:
        print(json.dumps(result["metrics"], indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
