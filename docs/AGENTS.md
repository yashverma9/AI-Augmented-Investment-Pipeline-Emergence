# Project Instructions

## Stack

- Python, managed with `uv` (pyproject.toml + uv.lock)
- `langchain_openai.ChatOpenAI` as a thin structured-output LLM client only — no LangGraph, chains, or agents
- pydantic for schemas, tenacity for retries, httpx for async HTTP, jinja2 for memo templates

## Architecture

- CLI entrypoint: `run.py` (`--topic`, `--stage source|analyze|memo|all`)
- Three decoupled, file-based stages — each reads a file and writes a file, never calls another stage's functions directly:
  - `sourcing.py` -> `candidates.json`
  - `analysis.py` -> `analysis.json` (reads `candidates.json`)
  - `memo.py` -> `memos/*.md` (reads `analysis.json`)
- Shared modules: `models.py` (pydantic schemas), `thesis.py` (criteria/weights/thresholds), `llm.py` (LLM client + retry wrapper), `product_hunt.py` (sourcing API client)
- Raw API responses are cached to disk under `cache/` (gitignored) before parsing
- Outputs (`candidates.json`, `analysis.json`, `memos/*.md`) are committed to the repo — not gitignored

## Rules

- Prefer existing modules and utilities.
- Do not introduce new dependencies unless necessary.
- Do not modify unrelated files.
- Do not rewrite working code without a reason.
- Keep implementations simple and production-ready.
- Do not change the pydantic schemas (`models.py`) unless explicitly asked.
- Structured LLM output must be validated against a pydantic model — never parse freeform text with regex.
- Never guess-fill missing data; mark it `null` with a `basis`/explanation instead.
- Deterministic logic (scores, thresholds, Pass/Watch/Meeting calls) stays in code, not another LLM call.

## Before finishing a task

- Run the relevant tests.
- Run lint/typecheck when applicable.
- Fix errors caused by your changes.
- Summarize what changed and what was tested.
