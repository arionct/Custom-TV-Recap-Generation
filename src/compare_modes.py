"""
Compare no-retrieval vs transcript-RAG vs summary-RAG for one stopping point.

Writes a JSON report (metrics + generated text) for offline review.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.chunking import DEFAULT_CHUNK_WORDS
from src.evaluate import evaluate_one


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--show", default="Breaking Bad")
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--episode", type=int, required=True)
    ap.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="Default cap for transcript RAG; summary RAG is uncapped unless --summary-max-chunks is set.",
    )
    ap.add_argument("--transcript-max-chunks", type=int, default=None)
    ap.add_argument("--summary-max-chunks", type=int, default=None)
    ap.add_argument(
        "--chunk-selection",
        choices=("episode_balanced", "tail"),
        default="episode_balanced",
    )
    ap.add_argument("--chunk-words", type=int, default=DEFAULT_CHUNK_WORDS)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    transcript_cap = args.transcript_max_chunks
    if transcript_cap is None:
        transcript_cap = args.max_chunks

    modes: list[tuple[str, str, str, int | None]] = [
        ("baseline_no_retrieval", "transcript", "none", None),
        ("transcript_rag", "transcript", "full", transcript_cap),
        ("summary_rag", "summary", "full", args.summary_max_chunks),
    ]
    results: list[dict[str, Any]] = []
    for label, corpus, retr, max_chunks in modes:
        print(f"--- {label} ---", file=sys.stderr)
        try:
            row = evaluate_one(
                args.show,
                args.season,
                args.episode,
                corpus=corpus,
                retrieval_mode=retr,
                chunk_size=args.chunk_words,
                max_total_chunks=max_chunks,
                chunk_selection=args.chunk_selection,
            )
        except Exception as e:
            results.append({"label": label, "error": str(e)})
            print(f"ERROR {label}: {e}", file=sys.stderr)
            continue
        gen = row["generated"]
        results.append(
            {
                "label": label,
                "corpus": corpus,
                "retrieval_mode": retr,
                "max_chunks": max_chunks,
                "metrics": row["metrics"],
                "generated": gen,
                "generated_preview": gen[:600] + ("…" if len(gen) > 600 else ""),
                "generated_len": len(gen),
            }
        )

    out_path = args.out or Path("runs") / f"compare_s{args.season:02d}e{args.episode:02d}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
