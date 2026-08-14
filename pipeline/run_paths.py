from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

RUNS_DIR = Path(__file__).with_name("runs")

SOURCING_FILENAME = "sourcing.json"
SHORTLIST_FILENAME = "shortlisted.json"
ANALYSIS_FILENAME = "analysis.json"
MEMOS_DIRNAME = "memos"


def slugify(text: str, max_length: int | None = None) -> str:
    """Filesystem-safe slug, e.g. 'AI agents for SMBs' -> 'ai-agents-for-smbs'."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if max_length is not None and len(slug) > max_length:
        slug = slug[:max_length].rsplit("-", 1)[0]
    return slug


def topic_abbreviation(topic: str, max_length: int = 24) -> str:
    return slugify(topic, max_length=max_length) or "topic"


def new_run_dir(topic: str, base_dir: Path = RUNS_DIR) -> Path:
    """A fresh folder per pipeline run: runs/Investment-<topic-abbrev>-<timestamp>/."""
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = base_dir / f"Investment-{topic_abbreviation(topic)}-{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def latest_run_dir(base_dir: Path = RUNS_DIR) -> Path:
    """Most recently created run dir under runs/, for standalone stage invocations."""
    run_dirs = [d for d in base_dir.glob("Investment-*") if d.is_dir()]
    if not run_dirs:
        raise FileNotFoundError(f"No run directories found under {base_dir}.")
    return max(run_dirs, key=lambda d: d.stat().st_mtime)


def sourcing_path(run_dir: Path) -> Path:
    return run_dir / SOURCING_FILENAME


def shortlist_path(run_dir: Path) -> Path:
    return run_dir / SHORTLIST_FILENAME


def analysis_path(run_dir: Path) -> Path:
    return run_dir / ANALYSIS_FILENAME


def memos_dir(run_dir: Path) -> Path:
    return run_dir / MEMOS_DIRNAME
