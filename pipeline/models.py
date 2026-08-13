from __future__ import annotations

from pydantic import BaseModel, Field


class TopicQueries(BaseModel):
    """Fixed set of short, PH-topic-name-style search terms derived from an investment topic."""

    queries: list[str] = Field(min_length=5, max_length=5)
