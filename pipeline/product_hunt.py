from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

PRODUCT_HUNT_API_URL = "https://api.producthunt.com/v2/api/graphql"
DEFAULT_PER_QUERY_LIMIT = 20
DEFAULT_TOPICS_PER_QUERY = 3
DEFAULT_OUTPUT_PATH = Path(__file__).with_name("candidates.json")
MAX_RATE_LIMIT_RETRIES = 5
MAX_RATE_LIMIT_WAIT_SECONDS = 900

TOPICS_QUERY = """
query SearchTopics($query: String!, $first: Int!) {
  topics(query: $query, first: $first) {
    edges {
      node {
        id
        name
        slug
      }
    }
  }
}
"""

POSTS_BY_TOPIC_QUERY = """
query PostsByTopic($topic: String!, $first: Int!) {
  posts(topic: $topic, first: $first, order: VOTES) {
    edges {
      node {
        id
        name
        slug
        tagline
        description
        url
        website
        createdAt
        votesCount
        featuredAt
        thumbnail {
          url
        }
        productLinks {
          type
          url
        }
        topics {
          edges {
            node {
              name
              slug
            }
          }
        }
        makers {
          id
          name
          username
          profileImage
        }
      }
    }
  }
}
"""


def get_headers() -> dict[str, str]:
    token = os.environ.get("PRODUCT_HUNT_TOKEN")
    if not token:
        raise RuntimeError("PRODUCT_HUNT_TOKEN is not set")

    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def graphql(query: str, variables: dict[str, object]) -> dict[str, Any]:
    logger.info("GraphQL request variables=%s", variables)

    for attempt in range(1, MAX_RATE_LIMIT_RETRIES + 1):
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            response = client.post(
                PRODUCT_HUNT_API_URL,
                json={"query": query, "variables": variables},
                headers=get_headers(),
            )

        remaining = response.headers.get("X-Rate-Limit-Remaining")
        limit = response.headers.get("X-Rate-Limit-Limit")
        if remaining is not None:
            logger.info("Rate limit remaining=%s/%s", remaining, limit)

        if response.status_code == 429:
            reset_seconds = int(response.headers.get("X-Rate-Limit-Reset", "60"))
            wait_seconds = min(reset_seconds, MAX_RATE_LIMIT_WAIT_SECONDS) + 1
            if attempt == MAX_RATE_LIMIT_RETRIES:
                logger.error("Rate limited (429) after %d attempts, giving up", attempt)
                response.raise_for_status()
            logger.warning(
                "Rate limited (429), retrying in %ds (attempt %d/%d)",
                wait_seconds,
                attempt,
                MAX_RATE_LIMIT_RETRIES,
            )
            time.sleep(wait_seconds)
            continue

        response.raise_for_status()
        payload = response.json()
        if "errors" in payload:
            logger.error("Product Hunt GraphQL error for variables=%s: %s", variables, payload["errors"])
            raise RuntimeError(f"Product Hunt GraphQL error: {payload['errors']}")

        return payload["data"]

    raise RuntimeError("Product Hunt API rate limit retries exhausted")


def form_launch_url(product_url: str, launch_slug: str, post_id: str) -> str:
    if not launch_slug or not launch_slug.strip():
        return f"{product_url}#launch-{post_id}"

    parsed = urlparse(product_url)
    path_parts = parsed.path.strip("/").split("/")
    if len(path_parts) >= 2 and path_parts[0] == "products":
        return f"https://www.producthunt.com/products/{path_parts[1]}/launches/{launch_slug}"

    return f"{product_url}#launch-{post_id}"


_topic_search_cache: dict[tuple[str, int], list[dict[str, str]]] = {}


def _search_topics(search_term: str, first: int) -> list[dict[str, str]]:
    cache_key = (search_term.lower(), first)
    if cache_key in _topic_search_cache:
        logger.info("Topic search cache hit for %r", search_term)
        return _topic_search_cache[cache_key]

    data = graphql(TOPICS_QUERY, {"query": search_term, "first": first})
    topic_edges = data.get("topics", {}).get("edges", [])
    topics = [
        {"id": edge["node"]["id"], "name": edge["node"]["name"], "slug": edge["node"]["slug"]}
        for edge in topic_edges
    ]
    _topic_search_cache[cache_key] = topics
    return topics


def resolve_topics(query: str, max_results: int = DEFAULT_TOPICS_PER_QUERY) -> list[dict[str, str]]:
    """Look up Product Hunt topics matching a query.

    `topics(query:)` matches literal substrings of existing topic names/descriptions rather
    than doing semantic search, so multi-word LLM-generated phrases (e.g. "Voice Assistants")
    often return zero results even when the underlying single words (e.g. "Voice") would match.
    If the full query returns nothing, fall back to searching each significant word individually
    and union the results.
    """
    topics = _search_topics(query, first=max(max_results, 10))

    if topics:
        logger.info(
            "Query=%r matched %d topic(s) directly: %s",
            query,
            len(topics),
            [topic["slug"] for topic in topics],
        )
        return topics[:max_results]

    words = [word for word in query.split() if len(word) > 2]
    combined: dict[str, dict[str, str]] = {}
    for word in words:
        for topic in _search_topics(word, first=max(max_results, 10)):
            combined.setdefault(topic["slug"], topic)

    if combined:
        logger.info(
            "Query=%r had no direct match; word-level fallback via %s matched %d topic(s): %s",
            query,
            words,
            len(combined),
            list(combined.keys()),
        )
    else:
        logger.warning("No Product Hunt topics matched query=%r (direct or word-level fallback)", query)

    return list(combined.values())[:max_results]


def normalize_post(node: dict[str, Any], source_query: str, topic: dict[str, str]) -> dict[str, Any]:
    product_url = str(node.get("url") or "")
    launch_slug = str(node.get("slug") or "")
    launch_url = form_launch_url(product_url, launch_slug, str(node["id"]))

    topic_edges = (node.get("topics") or {}).get("edges") or []
    topics = [
        edge["node"]["name"]
        for edge in topic_edges
        if edge.get("node") and edge["node"].get("name")
    ]
    makers = [
        maker["username"]
        for maker in (node.get("makers") or [])
        if maker.get("username")
    ]

    product_links = []
    for link in node.get("productLinks") or []:
        url = link.get("url")
        if not url:
            continue
        product_links.append(
            {
                "url": url,
                "type": link.get("type") or "Website",
            }
        )

    thumbnail = node.get("thumbnail") or {}

    return {
        "id": node["id"],
        "name": node.get("name"),
        "tagline": node.get("tagline") or "",
        "description": node.get("description") or "",
        "website": node.get("website") or launch_url,
        "ph_launch_url": launch_url,
        "ph_product_url": product_url,
        "created_at": node.get("createdAt"),
        "votes_count": node.get("votesCount"),
        "featured_at": node.get("featuredAt"),
        "topics": ", ".join(topics),
        "makers": ", ".join(makers),
        "logo": thumbnail.get("url"),
        "product_links": product_links,
        "source_query": source_query,
        "source_topic": topic["name"],
        "source_topic_slug": topic["slug"],
    }


def fetch_posts_for_topic(
    topic: dict[str, str], source_query: str, per_query: int = DEFAULT_PER_QUERY_LIMIT
) -> list[dict[str, Any]]:
    data = graphql(POSTS_BY_TOPIC_QUERY, {"topic": topic["slug"], "first": per_query})
    post_edges = data.get("posts", {}).get("edges", [])
    logger.info("Topic=%r fetched %d post(s)", topic["slug"], len(post_edges))
    return [normalize_post(edge["node"], source_query=source_query, topic=topic) for edge in post_edges]


def fetch_posts_for_queries(
    queries: list[str],
    per_query: int = DEFAULT_PER_QUERY_LIMIT,
    topics_per_query: int = DEFAULT_TOPICS_PER_QUERY,
) -> list[dict[str, Any]]:
    """For each query, resolve all matching topics and pull posts from each, deduping topics and posts."""
    seen_topic_slugs: set[str] = set()
    seen_post_ids: set[str] = set()
    posts: list[dict[str, Any]] = []

    for query in queries:
        topics = resolve_topics(query, max_results=topics_per_query)
        for topic in topics:
            if topic["slug"] in seen_topic_slugs:
                logger.info("Skipping already-fetched topic=%r for query=%r", topic["slug"], query)
                continue
            seen_topic_slugs.add(topic["slug"])

            for post in fetch_posts_for_topic(topic, source_query=query, per_query=per_query):
                if post["id"] in seen_post_ids:
                    continue
                seen_post_ids.add(post["id"])
                posts.append(post)

    logger.info(
        "Fetched %d unique post(s) across %d unique topic(s) from %d quer(y/ies)",
        len(posts),
        len(seen_topic_slugs),
        len(queries),
    )
    return posts


def save_posts_to_json(posts: list[dict[str, Any]], output_path: Path = DEFAULT_OUTPUT_PATH) -> Path:
    output_path.write_text(json.dumps(posts, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path