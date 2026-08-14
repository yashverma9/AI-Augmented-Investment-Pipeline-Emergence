from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from llm import call_structured
from logging_config import configure_logging
from models import TopicQueries
from product_hunt import (
    DEFAULT_PER_QUERY_LIMIT,
    DEFAULT_TOPICS_PER_QUERY,
    fetch_posts_for_queries,
    save_posts_to_json,
)
from run_paths import new_run_dir, shortlist_path, sourcing_path

NUM_QUERIES = 5
NUM_SHORTLIST = 25
SHORTLIST_LLM_BATCH_SIZE = 15

# Cheap pre-filter: known large/established companies whose PH posts are product releases,
# not independent startups (e.g. a new Gemini model), regardless of thesis fit.
LARGE_COMPANY_NAMES = {
    "google",
    "gemini",
    "meta",
    "microsoft",
    "openai",
    "chatgpt",
    "gpt",
    "anthropic",
    "claude",
    "amazon",
    "aws",
    "apple",
    "nvidia",
    "salesforce",
    "adobe",
    "ibm",
    "x",
    "xai",
    "grok",
}

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You convert an investment thesis topic into search terms for Product Hunt's "
    f"topic directory. Return exactly {NUM_QUERIES} queries, each 1-3 words, phrased "
    "like existing PH topic names (e.g. 'Developer Tools', 'Sales Automation', "
    "'No-Code'), not full sentences or questions. Each query should target a "
    "distinct, plausible PH topic so together they surface a broad but still "
    "relevant set of topics. No duplicates, no numbering, no explanations."
)

SHORTLIST_SYSTEM_PROMPT = (
    "You are a strict relevance filter for Product Hunt startups. "
    "For each startup, answer whether it genuinely matches the thesis niche. "
    "Be conservative: return 'yes' only if the startup is clearly in scope. "
    "Also reject (return 'no' regardless of thesis fit) any post that is a feature, model, or "
    "product release from an already-large, established company (e.g. Google, Meta, Microsoft, "
    "OpenAI, Anthropic, Amazon) rather than an independent early-stage startup — "
    "e.g. a new Gemini/GPT model release, a Google/Meta product launch. "
    "Return structured decisions only."
)

SHORTLIST_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "can",
    "could",
    "for",
    "from",
    "has",
    "have",
    "how",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "may",
    "more",
    "most",
    "new",
    "no",
    "not",
    "of",
    "on",
    "or",
    "our",
    "out",
    "over",
    "per",
    "so",
    "than",
    "that",
    "the",
    "their",
    "then",
    "there",
    "this",
    "to",
    "up",
    "use",
    "used",
    "using",
    "via",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "with",
    "would",
    "you",
    "your",
}


class ShortlistDecision(BaseModel):
    id: str
    keep: bool


class ShortlistDecisions(BaseModel):
    decisions: list[ShortlistDecision] = Field(min_length=1)


def expand_topic_to_queries(topic: str) -> list[str]:
    """LLM call: investment topic -> fixed set of short PH topics(query:) search terms."""
    result = call_structured(TopicQueries, SYSTEM_PROMPT, f"Investment topic: {topic}")
    return result.queries


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in SHORTLIST_STOPWORDS and len(token) > 1
    }


def _topic_match_keywords(post: dict[str, Any], thesis_keywords: set[str]) -> bool:
    if not thesis_keywords:
        return False

    post_topics = _tokenize(str(post.get("topics") or ""))
    return bool(post_topics & thesis_keywords)


def _text_match_keywords(post: dict[str, Any], thesis_keywords: set[str]) -> bool:
    if not thesis_keywords:
        return False

    searchable_text = " ".join(
        str(post.get(field) or "") for field in ("name", "tagline", "description")
    )
    return bool(_tokenize(searchable_text) & thesis_keywords)


def _is_large_company_release(post: dict[str, Any]) -> bool:
    name_tokens = _tokenize(str(post.get("name") or ""))
    return bool(name_tokens & LARGE_COMPANY_NAMES)


def _rule_based_shortlist(posts: list[dict[str, Any]], thesis: str) -> list[dict[str, Any]]:
    thesis_keywords = _tokenize(thesis)
    shortlisted = [
        post
        for post in posts
        if post.get("votes_count", 0) >= 20
        and not _is_large_company_release(post)
        and (_topic_match_keywords(post, thesis_keywords) or _text_match_keywords(post, thesis_keywords))
    ]
    shortlisted.sort(
        key=lambda post: (
            _topic_match_keywords(post, thesis_keywords),
            post.get("votes_count", 0),
        ),
        reverse=True,
    )
    logger.info(
        "Rule-based shortlist kept %d/%d post(s) for thesis=%r",
        len(shortlisted),
        len(posts),
        thesis,
    )
    return shortlisted


def _llm_relevance_shortlist(posts: list[dict[str, Any]], thesis: str, batch_size: int = SHORTLIST_LLM_BATCH_SIZE) -> list[dict[str, Any]]:
    shortlisted: list[dict[str, Any]] = []

    for batch_start in range(0, len(posts), batch_size):
        batch = posts[batch_start : batch_start + batch_size]
        if not batch:
            continue

        candidates_text = "\n".join(
            f"{index + 1}. id={post['id']} | name={post.get('name') or ''} | tagline={post.get('tagline') or ''}"
            for index, post in enumerate(batch)
        )
        prompt = (
            f"Thesis niche: {thesis}\n\n"
            "Decide whether each startup genuinely matches the thesis niche. "
            "Use only the startup's name and tagline. Be conservative. "
            "Reject any post that is a release from an already-large, established company "
            "(a new model, feature, or product from a company like Google, Meta, Microsoft, "
            "OpenAI, Anthropic, Amazon, etc.) rather than an independent startup, even if it "
            "otherwise fits the thesis.\n\n"
            f"Startups:\n{candidates_text}"
        )

        try:
            result = call_structured(ShortlistDecisions, SHORTLIST_SYSTEM_PROMPT, prompt)
        except Exception as exc:  # pragma: no cover - defensive fallback for cheap gate failures
            logger.warning("Shortlist LLM gate failed for thesis=%r batch=%d-%d: %s", thesis, batch_start, batch_start + len(batch), exc)
            shortlisted.extend(batch)
            continue

        keep_ids = {decision.id for decision in result.decisions if decision.keep}
        batch_shortlist = [post for post in batch if post["id"] in keep_ids]
        logger.info(
            "LLM shortlist kept %d/%d post(s) for thesis=%r batch=%d-%d",
            len(batch_shortlist),
            len(batch),
            thesis,
            batch_start,
            batch_start + len(batch),
        )
        shortlisted.extend(batch_shortlist)

    return shortlisted


def shortlist_candidates(posts: list[dict[str, Any]], thesis: str, limit: int = NUM_SHORTLIST) -> list[dict[str, Any]]:
    """Two-pass shortlist: cheap topic/votes filter first, then a batched yes/no LLM gate."""
    shortlisted = _rule_based_shortlist(posts, thesis)
    shortlisted = _llm_relevance_shortlist(shortlisted, thesis)
    return shortlisted[:limit]


def source_topic(
    topic: str,
    *,
    per_query: int = DEFAULT_PER_QUERY_LIMIT,
    topics_per_query: int = DEFAULT_TOPICS_PER_QUERY,
    run_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], Path]:
    """Fetch posts and write sourcing.json + shortlisted.json into a per-run directory."""
    run_dir = run_dir or new_run_dir(topic)
    queries = expand_topic_to_queries(topic)
    posts = fetch_posts_for_queries(queries, per_query=per_query, topics_per_query=topics_per_query)
    save_posts_to_json(posts, sourcing_path(run_dir))
    save_posts_to_json(shortlist_candidates(posts, thesis=topic), shortlist_path(run_dir))
    return posts, run_dir


def main() -> None:
    configure_logging("source")
    parser = argparse.ArgumentParser(description="Fetch Product Hunt candidates for an investment topic")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--per-query", type=int, default=DEFAULT_PER_QUERY_LIMIT)
    parser.add_argument("--topics-per-query", type=int, default=DEFAULT_TOPICS_PER_QUERY)
    parser.add_argument("--run-dir", type=Path, default=None, help="Defaults to a new folder under runs/")
    args = parser.parse_args()

    posts, run_dir = source_topic(
        args.topic,
        per_query=args.per_query,
        topics_per_query=args.topics_per_query,
        run_dir=args.run_dir,
    )
    print(f"queries={NUM_QUERIES}")
    print(f"per_query={args.per_query}")
    print(f"topics_per_query={args.topics_per_query}")
    print(f"posts={len(posts)}")
    print(f"run_dir={run_dir}")
    print(f"sourcing_output={sourcing_path(run_dir)}")
    print(f"shortlist_output={shortlist_path(run_dir)}")


if __name__ == "__main__":
    main()
