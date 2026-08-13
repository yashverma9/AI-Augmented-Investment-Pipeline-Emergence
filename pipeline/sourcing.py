from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from llm import call_structured
from logging_config import configure_logging
from models import TopicQueries
from product_hunt import (
    DEFAULT_PER_QUERY_LIMIT,
    DEFAULT_TOPICS_PER_QUERY,
    fetch_posts_for_queries,
    save_posts_to_json,
)

NUM_QUERIES = 5
DEFAULT_OUTPUT_PATH = Path(__file__).with_name("candidates.json")

SYSTEM_PROMPT = (
    "You convert an investment thesis topic into search terms for Product Hunt's "
    f"topic directory. Return exactly {NUM_QUERIES} queries, each 1-3 words, phrased "
    "like existing PH topic names (e.g. 'Developer Tools', 'Sales Automation', "
    "'No-Code'), not full sentences or questions. Each query should target a "
    "distinct, plausible PH topic so together they surface a broad but still "
    "relevant set of topics. No duplicates, no numbering, no explanations."
)


def expand_topic_to_queries(topic: str) -> list[str]:
    """LLM call: investment topic -> fixed set of short PH topics(query:) search terms."""
    result = call_structured(TopicQueries, SYSTEM_PROMPT, f"Investment topic: {topic}")
    return result.queries


def source_topic(
    topic: str,
    *,
    per_query: int = DEFAULT_PER_QUERY_LIMIT,
    topics_per_query: int = DEFAULT_TOPICS_PER_QUERY,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> list[dict[str, Any]]:
    queries = expand_topic_to_queries(topic)
    posts = fetch_posts_for_queries(queries, per_query=per_query, topics_per_query=topics_per_query)
    save_posts_to_json(posts, output_path)
    return posts


def main() -> None:
    configure_logging("source")
    parser = argparse.ArgumentParser(description="Fetch Product Hunt candidates for an investment topic")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--per-query", type=int, default=DEFAULT_PER_QUERY_LIMIT)
    parser.add_argument("--topics-per-query", type=int, default=DEFAULT_TOPICS_PER_QUERY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    posts = source_topic(
        args.topic,
        per_query=args.per_query,
        topics_per_query=args.topics_per_query,
        output_path=args.output,
    )
    print(f"queries={NUM_QUERIES}")
    print(f"per_query={args.per_query}")
    print(f"topics_per_query={args.topics_per_query}")
    print(f"posts={len(posts)}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
