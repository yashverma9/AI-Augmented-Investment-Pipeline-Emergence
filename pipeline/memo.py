from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from logging_config import configure_logging

logger = logging.getLogger(__name__)

DEFAULT_ANALYSIS_PATH = Path(__file__).with_name("analysis.json")
DEFAULT_CANDIDATES_DIR = Path(__file__).with_name("candidates")
DEFAULT_MEMOS_DIR = Path(__file__).with_name("memos")
TEMPLATE_DIR = Path(__file__).with_name("templates")
TEMPLATE_NAME = "memo.md.jinja"

# Deterministic call thresholds over overall_score, per docs/PLAN.md Stage 3.
MEETING_THRESHOLD = 70
WATCH_THRESHOLD = 50

WOULD_CHANGE_MIND_CRITERIA = ("product_specificity", "differentiation", "market_fit")


def slugify(text: str, max_length: int | None = None) -> str:
    """Filesystem-safe slug, e.g. 'AI agents for SMBs' -> 'ai-agents-for-smbs'."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if max_length is not None and len(slug) > max_length:
        slug = slug[:max_length].rsplit("-", 1)[0]
    return slug


def topic_abbreviation(topic: str, max_length: int = 24) -> str:
    """Short filesystem-safe slug for a topic, e.g. 'AI agents for SMBs' -> 'ai-agents-for-smbs'."""
    return slugify(topic, max_length=max_length) or "topic"


def memo_run_dir(topic: str, base_dir: Path = DEFAULT_MEMOS_DIR) -> Path:
    """A fresh timestamped folder per pipeline run: memos/memos-<topic-abbrev>-<timestamp>/."""
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return base_dir / f"memos-{topic_abbreviation(topic)}-{timestamp}"


def _latest_analysis_path() -> Path:
    if DEFAULT_ANALYSIS_PATH.exists():
        return DEFAULT_ANALYSIS_PATH

    analysis_paths = sorted(DEFAULT_CANDIDATES_DIR.glob("*_analysis.json"))
    if analysis_paths:
        return analysis_paths[-1]

    raise FileNotFoundError(
        f"No analysis file found. Expected {DEFAULT_ANALYSIS_PATH} or a timestamped file under {DEFAULT_CANDIDATES_DIR}."
    )


def _load_analysis(analysis_path: Path) -> list[dict[str, Any]]:
    data = json.loads(analysis_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise TypeError(f"Expected a JSON array in {analysis_path}")
    return data


def get_call(overall_score: float) -> str:
    if overall_score >= MEETING_THRESHOLD:
        return "Take a meeting"
    if overall_score >= WATCH_THRESHOLD:
        return "Watch"
    return "Pass"


def what_would_change_mind(scores: dict[str, float], scores_detail: dict[str, Any], n: int = 2) -> list[str]:
    """Surface the would_change_mind note for the n weakest LLM-judged criteria (traction has no such note)."""
    judged = [c for c in WOULD_CHANGE_MIND_CRITERIA if c in scores_detail]
    weakest = sorted(judged, key=lambda c: scores.get(c, 0.0))[:n]
    return [scores_detail[c]["would_change_mind"] for c in weakest]


def launch_date(created_at: str) -> str:
    """Just the date portion of an ISO timestamp, e.g. '2026-07-29T07:01:00Z' -> '2026-07-29'."""
    return created_at.split("T")[0] if created_at else "n/a"


def founders(makers: str) -> str:
    """Comma-separated makers with any redacted PH usernames dropped."""
    names = [name.strip() for name in makers.split(",") if name.strip() and name.strip() != "[REDACTED]"]
    return ", ".join(names) if names else "Not mentioned"


def other_links(product_links: list[dict[str, Any]]) -> list[dict[str, str]]:
    """product_links minus the website entry, which is already shown separately."""
    return [link for link in product_links if link.get("type") != "Website"]


def generate_memos(
    analysis_path: Path,
    topic: str,
    *,
    output_dir: Path | None = None,
    template_dir: Path = TEMPLATE_DIR,
) -> Path:
    candidates = _load_analysis(analysis_path)

    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template(TEMPLATE_NAME)

    out_dir = output_dir or memo_run_dir(topic)
    out_dir.mkdir(parents=True, exist_ok=True)

    for candidate in candidates:
        scores = candidate["scores"]
        scores_detail = candidate.get("scores_detail", {})
        call = get_call(candidate["overall_score"])
        wwcm = what_would_change_mind(scores, scores_detail)

        rendered = template.render(
            name=candidate["name"],
            tagline=candidate["tagline"],
            description=candidate["description"],
            call=call,
            overall_score=candidate["overall_score"],
            scores=scores,
            scores_detail=scores_detail,
            would_change_mind=wwcm,
            website=candidate["website"],
            ph_launch_url=candidate["ph_launch_url"],
            makers=founders(str(candidate.get("makers") or "")),
            votes_count=candidate.get("votes_count", 0),
            launch_date=launch_date(str(candidate.get("created_at") or "")),
            other_links=other_links(candidate.get("product_links") or []),
            status=candidate.get("status", "complete"),
            error=candidate.get("error"),
        )

        filename = f"{slugify(candidate['name'])}.md"
        (out_dir / filename).write_text(rendered, encoding="utf-8")
        logger.info("wrote %s — %s (%.1f)", filename, call, candidate["overall_score"])

    logger.info("Wrote %d memo(s) to %s", len(candidates), out_dir)
    return out_dir


def main() -> None:
    configure_logging("memo")
    parser = argparse.ArgumentParser(description="Render investment memos from analysis.json")
    parser.add_argument("--topic", required=True, help="Investment theme (used to name the output folder)")
    parser.add_argument("--input", type=Path, default=None, help="Analysis JSON to render memos from")
    args = parser.parse_args()

    analysis_path = args.input or _latest_analysis_path()
    out_dir = generate_memos(analysis_path, args.topic)
    print(f"analysis_input={analysis_path}")
    print(f"memos_output={out_dir}")


if __name__ == "__main__":
    main()
