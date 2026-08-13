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

## Context

You're the first engineering hire at a seed-stage VC firm. Partners spend ~10 hours/week scanning Product Hunt, YC, Hacker News, Twitter/X, and Crunchbase for promising startups, then writing memos by hand. Most candidates get passed on. Your job is to build the first version of an internal pipeline that automates the triage layer so partners can spend their time on the top 10%.

## Pipeline Insights

### 1. Sourcing

- Sources considered:
    - Primary - Hacker News Algolia Search API
