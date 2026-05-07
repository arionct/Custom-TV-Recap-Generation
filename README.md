# Spoiler-Restricted TV Recap RAG

Project for generating spoiler-restricted cumulative recaps of
`Breaking Bad`. Given a stopping point `(season, episode)`, the system should
summarize only what happens at or before that episode.

The final comparison uses three Gemma-backed methods:

1. no-retrieval baseline,
2. per-episode transcript RAG,
3. per-episode summary RAG.

Retrieval is deterministic: episode rows are filtered to `(season, episode) <= k`
before chunking, so future episode text is never placed in the prompt. The model
can still hallucinate from memory, so the repo includes metrics and saved runs
for qualitative/quantitative inspection.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.local.json
ollama pull gemma3:4b
```

Edit `config.local.json` if your Ollama/OpenAI-compatible endpoint differs.

## Run

```bash
# Transcript RAG
python -m src.rag --show "Breaking Bad" --season 1 --episode 3

# Summary RAG
python -m src.rag --show "Breaking Bad" --season 1 --episode 3 --corpus summary

# No-retrieval baseline
python -m src.rag --show "Breaking Bad" --season 1 --episode 3 --retrieval none
```
