from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

DEFAULT_MODEL = "gpt-4o-mini"


def get_client(model: str | None = None, temperature: float = 0) -> ChatOpenAI:
    """Thin ChatOpenAI factory - no LangChain chains/agents/orchestration on top of this.

    Reads OPENAI_API_KEY from the environment (via ChatOpenAI's own default lookup).
    """
    return ChatOpenAI(
        model=model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL),
        temperature=temperature,
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def call_structured[SchemaT: BaseModel](
    schema: type[SchemaT],
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
) -> SchemaT:
    """Single schema-constrained call; retries only on transient API errors."""
    client = get_client(model=model).with_structured_output(schema)
    result = client.invoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    return result  # type: ignore[return-value]
