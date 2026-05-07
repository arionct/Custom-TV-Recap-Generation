"""
Phase-1 RAG: deterministic episode-based retrieval and local (Ollama-compatible) generation.

Retrieval is **not** a learned dense/sparse ranker (no BM25/DPR). For a stopping
episode k=(season, episode), we deterministically include chunks built only from
rows with (s,e) <= k in series order. Transcripts are split into fixed word
windows; **summary** JSON is split by **chapter** (Teaser / Act / Credits
headers) when present, with word-based chunking as a fallback. Optional
``--max-chunks`` can keep an episode-balanced subset (default) or the chronological
tail of that stream. Either way, it never introduces episodes after k.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Literal

from src.chunking import (
    DEFAULT_CHUNK_WORDS,
    chunk_episode_summaries_by_chapters,
    chunk_episode_texts,
)
from src.preprocess import parse_transcript_stem

# Default system message: reduces Gemma/Ollama leaking reserved tokens like "<unused1234>".
DEFAULT_RECAP_SYSTEM_PROMPT = (
    "You write television recaps using ONLY the excerpt passages the user provides. "
    "Prefer concrete scenes, conflicts, and actions from that text; do not pad with broad "
    "series summaries or facts from later seasons from memory. "
    "If the excerpts are from a single episode, do not invent section headings for other "
    "episode numbers or continue into later episodes. "
    "Reply in plain English paragraphs or concise bullets. "
    "Do not output placeholder tags, token IDs, or angle-bracket markers such as 'unused'."
)

# --- Episode ordering (HARD: never include data from episodes after the stopping point) ---


def sanitize_model_output(text: str) -> str:
    """
    Strip Gemma vocabulary artifacts that sometimes surface in Ollama chat output.
    """
    if not text:
        return ""
    t = str(text)
    t = re.sub(r"<unused\d+\s*>?", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^…\s*", "", t)
    t = re.sub(r"^</\s*br\s*>\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^(?:[^\x00-\x7F]*\s*)+\n*", "", t)
    chatter = re.compile(
        r"^\s*(?:okay,\s*)?(?:here(?:'|’)s|here is)\s+"
        r"(?:a\s+)?(?:concise\s+|cumulative\s+)?recap[^\n]*\n+",
        flags=re.IGNORECASE,
    )
    while True:
        new_t = chatter.sub("", t, count=1)
        new_t = re.sub(r"^\s*SHALL WE BEGIN\?\s*\n+", "", new_t, flags=re.IGNORECASE)
        new_t = re.sub(r"^\s*(?:feuilleton|recap)\s*:\s*\n+", "", new_t, flags=re.IGNORECASE)
        if new_t == t:
            break
        t = new_t
    return t.strip()


# Headings like "**Episode 2:**" after a single-episode prompt are almost always hallucinations.
_SINGLE_EP_FAKE_HEADING = re.compile(
    r"(?m)^\s*(?:#{1,3}\s+)?(?:\*\*)?Episode\s+(\d+)\s*:\s*(?:\*\*)?\s*$",
    re.IGNORECASE,
)


def clamp_single_episode_headings(text: str, source_episode_id: str) -> str:
    """
    If retrieval included exactly one episode, drop trailing text starting at the first
    markdown-style heading for a *different* episode number (models often fabricate
    Episode 2 / Episode 3 sections despite one-episode excerpts).
    """
    if not text or not source_episode_id:
        return text
    try:
        _slug, _s0, e0, _eid = parse_transcript_stem(source_episode_id)
    except ValueError:
        return text
    cut: int | None = None
    for m in _SINGLE_EP_FAKE_HEADING.finditer(text):
        try:
            en = int(m.group(1))
        except (TypeError, ValueError):
            continue
        if en != e0:
            cut = m.start() if cut is None else min(cut, m.start())
    if cut is None or cut <= 0:
        return text
    return text[:cut].rstrip()


def _retrieval_task_instructions(
    *,
    single_excerpt_episode: bool,
    source_episode_id: str | None,
    k_season: int,
    k_episode: int,
    omitted_episode_ids: list[str] | None = None,
) -> str:
    has_omissions = bool(omitted_episode_ids)
    length_target = (
        "Target 250-350 words. Do not exceed 400 words unless the stopping point is late in the show "
        "and essential context would otherwise be lost; for late-show requests, compress aggressively "
        "and stay under about 650 words."
    )
    if single_excerpt_episode:
        eid_note = f" ({source_episode_id})" if source_episode_id else ""
        return (
            f"Task: Write ONE recap for **only** Season {k_season} Episode {k_episode}{eid_note}, using "
            "ONLY what is supported by the excerpt blocks below.\n"
            "- Use a few concise paragraphs grounded in the excerpts. Do **not** add sections, headings, "
            "or labels for any other episode number (no 'Episode 2', 'Part 2', 'Next episode', etc.).\n"
            f"- {length_target}\n"
            "- Stay specific: scenes, dialogue beats, and actions that appear in the excerpts.\n"
            "- Do not mention characters, deaths, relationships, or plot beats that do not appear anywhere "
            "in the excerpts—even if they are famous moments from the show.\n"
            "- Episode titles in your recap must match titles given in the excerpts; never substitute from memory.\n"
            "- Do not spoiler anything after the stopping point.\n"
            "- If a detail is not explicitly supported by the excerpts, omit it—do not fill gaps from memory."
        )
    if has_omissions:
        lead = (
            "Task: Write ONE cohesive recap of the provided episodes, using ONLY what is "
            "supported by the excerpt blocks below. The context budget omitted some earlier episodes, "
            "so do not claim this is a complete pilot-through-stopping-point recap.\n"
        )
    else:
        lead = (
            "Task: Write ONE cohesive cumulative recap from the pilot through the stopping episode (inclusive), "
            "using ONLY what is supported by the excerpt blocks below.\n"
        )
    return (
        lead
        +
        "- Write a flowing viewer-facing recap, not an episode-by-episode index. Do not make one heading, "
        "paragraph, or bullet list item for every episode.\n"
        "- Compress older/background events aggressively and spend more space on the most important plot "
        "threads, conflicts, character motivations, and unresolved setup needed to continue watching.\n"
        f"- {length_target}\n"
        "- Stay specific: describe actual scenes, problems, and turning points that appear in the excerpts. "
        "Avoid sweeping series-wide narration (e.g. avoid phrases like 'as the series progresses', "
        "'the series concludes', full-series character arcs, or nicknames like 'Heisenberg' unless those "
        "exact words appear in the excerpts).\n"
        "- Do not mention characters, deaths, relationships, or plot beats that do not appear anywhere "
        "in the excerpts above—even if they are famous moments from the show.\n"
        "- Preserve broad chronology, but merge related events across episodes into coherent story arcs.\n"
        "- Do not use episode headings unless the user specifically asks for an episode-by-episode breakdown.\n"
        "- Prefer close paraphrases of retrieved wording over broad generalization; when uncertain, keep "
        "the source wording rather than filling in a familiar plot point from memory.\n"
        "- If law enforcement finds a scene but the excerpts do not identify suspects, do not name the "
        "protagonists as suspects or say investigators uncovered their involvement.\n"
        "- Episode titles in your recap must match titles given in the excerpts; never substitute a title "
        "from memory.\n"
        "- Do not spoiler anything after the stopping point.\n"
        "- Start directly with recap content; do not preface with 'Here is', 'Okay', or a disclaimer.\n"
        "- If a detail is not explicitly supported by the excerpts, omit it—do not fill gaps from memory."
    )


def normalize_show(s: str) -> str:
    return s.strip().casefold()


def episode_lte(
    season: int,
    episode: int,
    k_season: int,
    k_episode: int,
) -> bool:
    if season < k_season:
        return True
    if season > k_season:
        return False
    return episode <= k_episode


def select_episodes_until(
    rows: list[dict[str, Any]],
    show: str,
    k_season: int,
    k_episode: int,
) -> list[dict[str, Any]]:
    want = normalize_show(show)
    chosen: list[dict[str, Any]] = []
    for r in rows:
        if normalize_show(str(r["show"])) != want:
            continue
        s, e = int(r["season"]), int(r["episode"])
        if not episode_lte(s, e, k_season, k_episode):
            continue
        chosen.append(r)
    chosen.sort(key=lambda r: (int(r["season"]), int(r["episode"])))
    return chosen


def select_episodes_for_show(
    rows: list[dict[str, Any]],
    show: str,
) -> list[dict[str, Any]]:
    """All episodes for one show (ordered), including those after stopping—for offline metrics."""
    want = normalize_show(show)
    chosen = [r for r in rows if normalize_show(str(r["show"])) == want]
    chosen.sort(key=lambda r: (int(r["season"]), int(r["episode"])))
    return chosen


def build_chunk_list(
    episodes: list[dict[str, Any]],
    chunk_size: int = DEFAULT_CHUNK_WORDS,
    *,
    corpus: Literal["transcript", "summary"] = "transcript",
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ep in episodes:
        eid = str(ep["episode_id"])
        text = str(ep["text"])
        if corpus == "summary":
            chunker = chunk_episode_summaries_by_chapters(
                eid, text, fallback_word_size=chunk_size
            )
        else:
            chunker = chunk_episode_texts(eid, text, chunk_size=chunk_size)
        for c in chunker:
            out.append(c)
    return out


def take_tail_max_chunks(
    flat: list[dict[str, Any]],
    max_total: int | None,
) -> list[dict[str, Any]]:
    """
    If a cap is set and we have too many chunks, keep the last max_total
    in chronological order (dropping the oldest content first).
    """
    if max_total is None or len(flat) <= max_total:
        return flat
    return flat[-max_total:]


def _chunks_by_episode(flat: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for c in flat:
        eid = str(c["episode_id"])
        if eid not in grouped:
            grouped[eid] = []
            order.append(eid)
        grouped[eid].append(c)
    return [(eid, grouped[eid]) for eid in order]


def _evenly_spaced_chunks(chunks: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    if n <= 0:
        return []
    if n >= len(chunks):
        return chunks
    if n == 1:
        return [chunks[len(chunks) // 2]]
    idxs = {round(i * (len(chunks) - 1) / (n - 1)) for i in range(n)}
    return [chunks[i] for i in sorted(idxs)]


def take_episode_balanced_max_chunks(
    flat: list[dict[str, Any]],
    max_total: int | None,
) -> list[dict[str, Any]]:
    """
    Keep a deterministic, episode-balanced subset under a chunk budget.

    This avoids a common recap failure mode where a chronological tail budget drops
    the pilot/early episodes but the prompt still asks for a cumulative recap.
    """
    if max_total is None or len(flat) <= max_total:
        return flat
    if max_total < 1:
        return []

    grouped = _chunks_by_episode(flat)
    if max_total < len(grouped):
        grouped = grouped[-max_total:]

    allocations = {eid: 1 for eid, _chunks in grouped}
    remaining = max_total - len(grouped)
    while remaining > 0:
        progressed = False
        for eid, chunks in reversed(grouped):
            if remaining <= 0:
                break
            if allocations[eid] < len(chunks):
                allocations[eid] += 1
                remaining -= 1
                progressed = True
        if not progressed:
            break

    selected: list[dict[str, Any]] = []
    for eid, chunks in grouped:
        selected.extend(_evenly_spaced_chunks(chunks, allocations[eid]))
    selected.sort(key=lambda c: (str(c["episode_id"]), int(c["chunk_index"])))
    return selected


def select_chunks_for_budget(
    flat: list[dict[str, Any]],
    max_total: int | None,
    *,
    strategy: Literal["episode_balanced", "tail"] = "episode_balanced",
) -> list[dict[str, Any]]:
    if strategy == "tail":
        return take_tail_max_chunks(flat, max_total)
    if strategy == "episode_balanced":
        return take_episode_balanced_max_chunks(flat, max_total)
    raise ValueError(f"Unknown chunk selection strategy: {strategy}")


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_episodes_path(
    corpus: Literal["transcript", "summary"] = "transcript",
    override: Path | None = None,
) -> Path:
    if override is not None:
        return override
    root = _project_root()
    if corpus == "summary":
        return root / "data" / "processed" / "episode_summaries.json"
    return root / "data" / "processed" / "episodes.json"


def load_config(path: Path | None = None) -> dict[str, Any]:
    p = path or (_project_root() / "config.local.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    if "base_url" not in data or "model_name" not in data:
        raise ValueError("config must include base_url and model_name")
    return data


def load_episodes_json(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or (_project_root() / "data" / "processed" / "episodes.json")
    if not p.is_file():
        raise FileNotFoundError(f"Episodes file not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _excerpt_noun(excerpt_kind: str) -> str:
    if excerpt_kind == "summary":
        return "episode summary excerpts"
    return "transcript excerpts"


def _grounding_line(excerpt_kind: str) -> str:
    if excerpt_kind == "summary":
        return (
            "Only include events that are explicitly present in the provided summaries. "
            "Do not infer or add events not directly described there."
        )
    return (
        "Only include events that are explicitly present in the provided transcript. "
        "Do not infer or add events not directly described. "
        "If something is not supported by the excerpts, omit it or say it is not shown."
    )


_EPISODE_TITLE_RE = re.compile(r"(?m)^\s*(Episode\s+\d{3}\s*:\s*[^\n]+)\s*$")


def _episode_scope_lines(chunks: list[dict[str, str]]) -> list[str]:
    by_eid: dict[str, str] = {}
    for c in chunks:
        eid = str(c["episode_id"])
        if eid in by_eid:
            continue
        m = _EPISODE_TITLE_RE.search(str(c.get("text", "")))
        by_eid[eid] = m.group(1).strip() if m else eid
    return [f"- {eid}: {label}" for eid, label in by_eid.items()]


def build_user_prompt(
    show: str,
    k_season: int,
    k_episode: int,
    chunks: list[dict[str, str]],
    *,
    retrieval_mode: str = "full",
    excerpt_kind: str = "transcript",
    omitted_episode_ids: list[str] | None = None,
) -> str:
    if retrieval_mode == "none":
        return (
            f"You are helping write a TV recap for the show {show!r}.\n"
            f"Stopping point: Season {k_season} Episode {k_episode} (inclusive).\n\n"
            "No transcript or summary text is included in this prompt (no-retrieval baseline). "
            "Write a concise, cohesive cumulative recap of the story and main characters from the beginning "
            "of the series through that stopping episode for a viewer who has watched through it. "
            "Do not produce an episode-by-episode breakdown; compress older/background events and focus on "
            "the main plot threads needed to continue watching. Target 250-350 words; do not exceed "
            "400 words unless the stopping point is late in the show and essential context would otherwise be lost.\n"
            "Do not reveal plot points that occur only in later episodes. "
            "If you are uncertain about a detail, omit it rather than speculate.\n\n"
            "Task: Provide the recap now."
        )

    label = _excerpt_noun(excerpt_kind)
    grounding = _grounding_line(excerpt_kind)
    included = sorted({str(c["episode_id"]) for c in chunks})
    scope_lines = (
        f"Included episode_id labels in the excerpts (do not add plot from outside this set): "
        f"{', '.join(included)}.\n"
    )
    if omitted_episode_ids:
        scope_lines += (
            "Episode ids at or before the stopping point that were omitted by the context budget: "
            f"{', '.join(omitted_episode_ids)}. Do not summarize events from omitted episodes unless "
            "they are explicitly restated in the included excerpts.\n"
        )
    scope = _episode_scope_lines(chunks)
    if scope:
        scope_lines += "Episode scope labels for grounding only (do not structure the recap around this list):\n"
        scope_lines += "\n".join(scope) + "\n"
    if len(included) == 1:
        scope_lines += (
            "Only that single episode appears in the excerpts—do not invent a second episode, "
            "a 'Part 2', or events labeled as a later episode.\n"
            "FORBIDDEN: a section or heading named Episode 2, S01E02, 102, or any episode_id not listed above.\n"
        )
    single_excerpt_episode = len(included) == 1
    sole_episode_id: str | None = included[0] if single_excerpt_episode else None
    scope_preamble = (
        "These excerpts cover **one episode only**; write that episode's recap.\n\n"
        if single_excerpt_episode
        else ""
    )
    header = (
        f"You are helping write a TV recap for the show {show!r}.\n"
        f"Stopping point: Season {k_season} Episode {k_episode} (inclusive). "
        f"The {label} below are ONLY from episodes at or before that point. "
        "Do not invent events from later episodes, and do not use knowledge of the show beyond these excerpts. "
        f"{grounding}\n\n"
        f"{scope_preamble}"
        f"{scope_lines}\n"
        f"Excerpts (in chronological order, labeled by episode and chunk index):\n\n"
    )
    blocks: list[str] = [header]
    for c in chunks:
        label_line = f"[{c['episode_id']} part {c['chunk_index']}]"
        blocks.append(f"{label_line}\n{c['text']}\n\n")
    blocks.append(
        _retrieval_task_instructions(
            single_excerpt_episode=single_excerpt_episode,
            source_episode_id=sole_episode_id,
            k_season=k_season,
            k_episode=k_episode,
            omitted_episode_ids=omitted_episode_ids,
        )
    )
    return "".join(blocks)


def _chat_completions_url(base_url: str) -> str:
    u = base_url.rstrip("/")
    if u.endswith("/v1"):
        return f"{u}/chat/completions"
    if u.endswith("/v1/"):
        return f"{u.rstrip('/')}/chat/completions"
    return f"{u}/v1/chat/completions"


def call_local_model(
    config: dict[str, Any],
    user_prompt: str,
    system_prompt: str | None = None,
) -> str:
    url = _chat_completions_url(str(config["base_url"]))
    model = str(config["model_name"])
    temperature = float(config.get("temperature", 0.2))
    max_tokens = int(config.get("max_tokens", 4096))

    if system_prompt is not None:
        sys_content: str | None = system_prompt
    elif "system_prompt" in config:
        sp = config["system_prompt"]
        sys_content = None if sp is None else str(sp)
    else:
        sys_content = DEFAULT_RECAP_SYSTEM_PROMPT

    messages: list[dict[str, str]] = []
    if sys_content:
        messages.append({"role": "system", "content": sys_content})
    messages.append({"role": "user", "content": user_prompt})
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM HTTP {e.code}: {err}") from e
    try:
        msg = raw["choices"][0]["message"]
        content = msg.get("content")
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Unexpected LLM response: {raw!r}") from e

    if content is None:
        raise RuntimeError(f"LLM returned empty message content: {raw!r}")

    cleaned = sanitize_model_output(str(content))
    if not cleaned:
        raise RuntimeError(
            "Model output became empty after removing reserved tokens (e.g. <unused####>). "
            "Try: increase max_tokens in config, reduce prompt size (--max-chunks), "
            "raise Ollama context (num_ctx), or update Gemma/Ollama."
        )
    return cleaned


def prepare_recap_user_prompt(
    show: str,
    k_season: int,
    k_episode: int,
    *,
    chunk_size: int = DEFAULT_CHUNK_WORDS,
    max_total_chunks: int | None = None,
    episodes_path: Path | None = None,
    corpus: Literal["transcript", "summary"] = "transcript",
    retrieval_mode: Literal["full", "none"] = "full",
    chunk_selection: Literal["episode_balanced", "tail"] = "episode_balanced",
) -> tuple[str, dict[str, Any]]:
    """
    Build the recap user prompt and lightweight stats for logging / evaluation.

    ``stats`` includes ``retrieved_concat`` (empty for no-retrieval) used for
    reference-free grounding proxies (e.g. Liu et al., NAACL 2022-style compression).
    """
    path = resolve_episodes_path(corpus, episodes_path)
    data = load_episodes_json(path)
    eps = select_episodes_until(data, show, k_season, k_episode)
    if not eps:
        raise ValueError(
            f"No episodes found for show {show!r} up to S{k_season:02d}E{k_episode:02d}."
        )
    excerpt_kind: str = "summary" if corpus == "summary" else "transcript"
    stats: dict[str, Any] = {
        "corpus": corpus,
        "retrieval_mode": retrieval_mode,
        "chunk_selection": chunk_selection,
        "episodes_in_window": len(eps),
        "chunks_in_prompt": 0,
        "retrieved_chars": 0,
        "retrieved_concat": "",
        "available_episode_ids": [str(ep["episode_id"]) for ep in eps],
        "omitted_episode_ids": [],
    }

    if retrieval_mode == "none":
        user_prompt = build_user_prompt(
            show,
            k_season,
            k_episode,
            [],
            retrieval_mode="none",
            excerpt_kind=excerpt_kind,
        )
        stats["prompt_total_chars"] = len(user_prompt)
        stats["included_episode_ids"] = []
        return user_prompt, stats

    flat = build_chunk_list(eps, chunk_size=chunk_size, corpus=corpus)
    use_chunks = select_chunks_for_budget(
        flat,
        max_total_chunks,
        strategy=chunk_selection,
    )
    included_episode_ids = sorted({str(c["episode_id"]) for c in use_chunks})
    available_episode_ids = [str(ep["episode_id"]) for ep in eps]
    omitted_episode_ids = [
        eid for eid in available_episode_ids if eid not in set(included_episode_ids)
    ]
    prompt_chunks: list[dict[str, str]] = [
        {
            "episode_id": str(c["episode_id"]),
            "chunk_index": str(c["chunk_index"]),
            "text": str(c["text"]),
        }
        for c in use_chunks
    ]
    stats["included_episode_ids"] = included_episode_ids
    stats["omitted_episode_ids"] = omitted_episode_ids
    user_prompt = build_user_prompt(
        show,
        k_season,
        k_episode,
        prompt_chunks,
        retrieval_mode="full",
        excerpt_kind=excerpt_kind,
        omitted_episode_ids=omitted_episode_ids,
    )
    concat = "\n\n".join(str(c["text"]) for c in use_chunks)
    stats["chunks_in_prompt"] = len(use_chunks)
    stats["retrieved_chars"] = len(concat)
    stats["retrieved_concat"] = concat
    stats["prompt_total_chars"] = len(user_prompt)
    return user_prompt, stats


def run_recap(
    show: str,
    k_season: int,
    k_episode: int,
    *,
    chunk_size: int = DEFAULT_CHUNK_WORDS,
    max_total_chunks: int | None = None,
    config_path: Path | None = None,
    episodes_path: Path | None = None,
    corpus: Literal["transcript", "summary"] = "transcript",
    retrieval_mode: Literal["full", "none"] = "full",
    chunk_selection: Literal["episode_balanced", "tail"] = "episode_balanced",
    return_debug: bool = False,
) -> str | tuple[str, dict[str, Any]]:
    """
    Generate a recap. With ``return_debug=True``, returns ``(text, stats)`` where
    ``stats`` includes ``elapsed_seconds`` and prompt/retrieval diagnostics.
    """
    t0 = time.perf_counter()
    user_prompt, stats = prepare_recap_user_prompt(
        show,
        k_season,
        k_episode,
        chunk_size=chunk_size,
        max_total_chunks=max_total_chunks,
        episodes_path=episodes_path,
        corpus=corpus,
        retrieval_mode=retrieval_mode,
        chunk_selection=chunk_selection,
    )
    cfg = load_config(config_path)
    text = call_local_model(cfg, user_prompt)
    inc_ids = stats.get("included_episode_ids")
    if (
        retrieval_mode == "full"
        and isinstance(inc_ids, list)
        and len(inc_ids) == 1
        and isinstance(inc_ids[0], str)
    ):
        text = clamp_single_episode_headings(text, inc_ids[0])
    stats["elapsed_seconds"] = round(time.perf_counter() - t0, 3)
    if return_debug:
        return text, stats
    return text


def main() -> int:
    ap = argparse.ArgumentParser(
        description="TV recap with deterministic episode-limited retrieval or a no-retrieval baseline."
    )
    ap.add_argument("--show", type=str, required=True, help='Show name, e.g. "Breaking Bad"')
    ap.add_argument("--season", type=int, required=True, help="Stopping season k")
    ap.add_argument("--episode", type=int, required=True, help="Stopping episode k (inclusive)")
    ap.add_argument(
        "--corpus",
        choices=("transcript", "summary"),
        default="transcript",
        help="Processed JSON to load (default: transcripts).",
    )
    ap.add_argument(
        "--retrieval",
        choices=("full", "none"),
        default="full",
        help="full: include chunks up to k; none: baseline without excerpts.",
    )
    ap.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="Optional cap on chunks sent (never crosses episode k).",
    )
    ap.add_argument(
        "--chunk-selection",
        choices=("episode_balanced", "tail"),
        default="episode_balanced",
        help=(
            "How to apply --max-chunks: episode_balanced spreads chunks across episodes; "
            "tail keeps the newest chronological chunks."
        ),
    )
    ap.add_argument(
        "--chunk-words",
        type=int,
        default=DEFAULT_CHUNK_WORDS,
        help=(
            f"Transcripts: words per chunk (default: {DEFAULT_CHUNK_WORDS}). "
            "Summaries: only used if chapter headers are missing (fallback split)."
        ),
    )
    ap.add_argument("--config", type=Path, default=None, help="Path to config.local.json")
    ap.add_argument(
        "--episodes",
        type=Path,
        default=None,
        help="Override path to processed episode JSON (same schema as transcripts).",
    )
    ap.add_argument(
        "--timing",
        action="store_true",
        help="Print JSON timing/chunk stats to stderr after generation.",
    )
    args = ap.parse_args()
    if args.chunk_words < 1:
        print("--chunk-words must be >= 1", file=sys.stderr)
        return 2
    if args.max_chunks is not None and args.max_chunks < 1:
        print("--max-chunks must be >= 1 when provided", file=sys.stderr)
        return 2
    if args.season < 1 or args.episode < 1:
        print("--season and --episode must be >= 1", file=sys.stderr)
        return 2
    try:
        if args.timing:
            text, dbg = run_recap(
                args.show,
                args.season,
                args.episode,
                chunk_size=args.chunk_words,
                max_total_chunks=args.max_chunks,
                config_path=args.config,
                episodes_path=args.episodes,
                corpus=args.corpus,
                retrieval_mode=args.retrieval,
                chunk_selection=args.chunk_selection,
                return_debug=True,
            )
            print(
                json.dumps(
                    {
                        "elapsed_seconds": dbg.get("elapsed_seconds"),
                        "chunks_in_prompt": dbg.get("chunks_in_prompt"),
                        "retrieved_chars": dbg.get("retrieved_chars"),
                        "prompt_total_chars": dbg.get("prompt_total_chars"),
                        "chunk_selection": dbg.get("chunk_selection"),
                        "included_episode_ids": dbg.get("included_episode_ids"),
                        "omitted_episode_ids": dbg.get("omitted_episode_ids"),
                    }
                ),
                file=sys.stderr,
            )
        else:
            text = run_recap(
                args.show,
                args.season,
                args.episode,
                chunk_size=args.chunk_words,
                max_total_chunks=args.max_chunks,
                config_path=args.config,
                episodes_path=args.episodes,
                corpus=args.corpus,
                retrieval_mode=args.retrieval,
                chunk_selection=args.chunk_selection,
            )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
