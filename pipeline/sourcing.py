from __future__ import annotations

import argparse

from llm import call_structured
from models import TopicQueries

NUM_QUERIES = 5

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Expand a topic into PH topic search queries")
    parser.add_argument("--topic", required=True)
    args = parser.parse_args()

    for query in expand_topic_to_queries(args.topic):
        print(query)


if __name__ == "__main__":
    main()
