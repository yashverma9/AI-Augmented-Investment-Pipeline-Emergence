# AI Augmented Investment Pipeline: Emergence Assignment

Automates seed-stage startup triage. Give it a topic, get back scored memos with a clear call, so a partner spends time only on the top 10%.

## Setup

This project is managed with `uv` from the `pipeline/` directory.

```bash
cd pipeline
uv sync
```

Common `uv` commands:

```bash
# Run the pipeline CLI inside the managed environment
uv run python run.py --topic "AI agents for SMBs" --stage all

# Add a new package and update pyproject.toml + uv.lock
uv add requests

# Remove a package
uv remove requests

# Refresh the lockfile after dependency changes
uv lock

# Run a one-off command without activating the environment manually
uv run pytest
```

## Running the Pipeline

The pipeline reads its credentials from a `pipeline/.env` file, which is gitignored and not committed. Create your own copy before running anything:

```bash
cd pipeline
touch .env
```

Populate it with your own keys:

- `OPENAI_API_KEY` - from the [OpenAI API keys dashboard](https://platform.openai.com/api-keys); used by `llm.py` for shortlist gating, scoring, and memo generation.
- `PRODUCT_HUNT_TOKEN` - a developer token for the [Product Hunt API](https://api.producthunt.com/v2/docs); used by `product_hunt.py` for sourcing candidates.

Sample `pipeline/.env`:

```bash
OPENAI_API_KEY=sk-proj-abc123examplekeydonotcommit
PRODUCT_HUNT_TOKEN=ph_dev_example1234567890token
```

Run the full pipeline (source → analyze → memo) for a topic:

```bash
cd pipeline
uv run python run.py --topic "AI Agents for SMBs"
```

This creates a new run directory at `pipeline/runs/Investment-<topic-abbrev>-<timestamp>/` containing `sourcing.json`, `shortlisted.json`, `analysis.json`, and a `memos/` folder with one memo per candidate.

You can also run a single stage with `--stage`:

```bash
# Source candidates only (Product Hunt search + shortlist)
uv run python run.py --topic "AI Agents for SMBs" --stage source

# Analyze the most recent shortlist
uv run python run.py --topic "AI Agents for SMBs" --stage analyze

# Generate memos from the most recent analysis
uv run python run.py --topic "AI Agents for SMBs" --stage memo

# Run all stages (default)
uv run python run.py --topic "AI Agents for SMBs" --stage all
```

Logs for each run are written to `pipeline/logs/<stage>_<timestamp>.log`.

## Context

You're the first engineering hire at a seed-stage VC firm. Partners spend ~10 hours/week scanning Product Hunt, YC, Hacker News, Twitter/X, and Crunchbase for promising startups, then writing memos by hand. Most candidates get passed on. Your job is to build the first version of an internal pipeline that automates the triage layer so partners can spend their time on the top 10%.

## How It Works

- **Sourcing**: an LLM turns your topic into short Product Hunt-style search phrases, pulls matching posts, then funnels the raw results down to a shortlist via a traction floor, a keyword pre-filter, and a batched LLM relevance gate (also rejecting big-company launches).
- **Analysis**: each shortlisted candidate is scored on traction (pure math, normalized votes) plus three LLM-judged criteria - product specificity, differentiation, market fit - weighted into one overall score, with a "what would change my mind" rationale per criterion.
- **Memo**: one Jinja2-rendered memo per candidate is generated straight from the analysis data (no extra API calls), ending in a deterministic call - 70+ Take a meeting, 45-69 Watch, below 45 Pass.
