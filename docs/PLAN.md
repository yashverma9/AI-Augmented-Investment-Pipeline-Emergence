# Plan: AI-Augmented Investment Pipeline (Emergence Assignment)

## Context

Greenfield repo — only AGENTS.md, BUILD_LOG.md (empty), README.md (stub), project_brief.md exist. No code yet.
Note: AGENTS.md contains generic Next.js/TS boilerplate rules (App Router, src/app/api, src/lib/db) that do NOT apply — project_brief.md (the actual spec) mandates a Python CLI. Following project_brief.md.

## Decisions (confirmed with user)

- LLM: `langchain_openai.ChatOpenAI` used ONLY as a thin model client (with `.with_structured_output()` for schema-constrained calls). No LangGraph, no LangChain chains/agents/orchestration — matches brief's "no LangChain framework overhead" intent while satisfying user's SDK preference.
- Env/deps: `uv` (pyproject.toml + uv.lock).
- API keys: user already has OpenAI key + Product Hunt developer token; will populate `.env` (add `.env.example` with placeholders).
- Thesis: default 5 sub-criteria (problem specificity, why-now, team-market fit, differentiation, traction strength), equal weights (0.2 each), defined in a config module — swappable later.
- Scope v1: Product Hunt sourcing only. HN Algolia stubbed/deferred (function signature present, not implemented / marked TODO per brief's "LATER").
- Schema extension (flag to user, not yet re-confirmed): add `critical_risk: bool` + `critical_risk_basis: str | None` to the `Analysis` pydantic model (brief's example schema only has freeform `risks: list[str]`, but memo.py's deterministic call rule needs a boolean signal, not text parsing). This is an additive extension, not a rewrite.
- Sub-criteria and overall_score are 0-100 scale. overall_score = weighted average over non-null criteria only, weights renormalized to sum to 1 across available criteria.
- Outputs (candidates.json, analysis.json, memos/\*.md) are committed to repo — NOT gitignored. Only `cache/` (raw API responses) and `.env` are gitignored.

## Architecture (flat, per brief)

```
run.py          # CLI orchestrator: --topic, --stage source|analyze|memo|all
sourcing.py     # -> candidates.json
analysis.py     # -> analysis.json (reads candidates.json)
memo.py         # -> memos/*.md (reads analysis.json)
models.py       # pydantic schemas: Candidate, Signal, Analysis
thesis.py       # default thesis sub-criteria, weights, Pass/Watch/Meeting thresholds
llm.py          # ChatOpenAI wrapper + tenacity retry + structured output helpers
product_hunt.py # PH GraphQL client (async httpx, cached raw responses)
templates/memo.md.jinja
cache/          # gitignored — raw API responses per stage
tests/
```

## Phases

### Phase 0 — Scaffolding

- `uv init`, `pyproject.toml` deps: httpx, pydantic, tenacity, langchain-openai, python-dotenv, jinja2, beautifulsoup4, python-slugify; dev deps: pytest, pytest-asyncio, respx (mock httpx in tests), ruff, pyright.
- `.env.example` (OPENAI_API_KEY, PRODUCT_HUNT_TOKEN), update `.gitignore` (.env, cache/).
- Create `cache/`, `templates/`, `tests/` dirs, `memos/` (empty, committed).

### Phase 1 — Shared foundations (_parallel-safe once Phase 0 done_)

- `models.py`: `Signal`, `Candidate` (name, website, description, founders[], signal, source_urls[]), `Analysis` (team, product, market, risks, scores, scores_basis, data_completeness, overall_score, rationale, critical_risk, critical_risk_basis).
- `thesis.py`: `CRITERIA` (name -> weight, prompt description), `PASS_THRESHOLD=50`, `MEETING_THRESHOLD=70`, `MIN_DATA_COMPLETENESS` cap rule.
- `llm.py`: `get_client()` (ChatOpenAI), `call_structured(prompt, schema, max_retries=1)` wrapping tenacity for transient errors + one stricter-prompt retry on pydantic ValidationError, returning `(result | None, error)`.

### Phase 2 — Sourcing (`sourcing.py`, `product_hunt.py`) — _depends on Phase 1_

1. `expand_topic_to_queries(topic)` — LLM call -> 3-5 queries.
2. `product_hunt.py`: async GraphQL client, semaphore(5), cache raw JSON per query under `cache/product_hunt/`.
    - Risk: PH GraphQL v2 has no free-text search over all posts (only topic-filtered/sorted queries). Plan: map expanded queries -> matching topics via `topics(query:)`, then pull posts per topic; verify against live API early (spike) before building full funnel — flagged in Further Considerations.
3. Dedupe by domain, drop dead links (`httpx.head()`, concurrent) -> ~30-40.
4. `llm_relevance_gate(candidates, thesis)` — cheap LLM yes/no per candidate (name + one-liner), concurrent w/ semaphore(5) -> ~15-25.
5. Enrichment: fetch each shortlisted site (BeautifulSoup: title/meta/team page heuristics) + GitHub profile if linked.
6. Rank by traction signal (PH votes/comments + recency), cut to final 10-20 (default N=15, configurable).
7. Write `candidates.json`.

### Phase 3 — Analysis (`analysis.py`) — _depends on Phase 1, can start once Candidate schema is stable (doesn't need Phase 2 to finish, only candidates.json shape)_

- Load `candidates.json`; for each candidate (concurrent, semaphore 5): build prompt with all known facts, call `llm.call_structured(..., Analysis)`.
- On validation failure: retry once w/ stricter prompt; if still failing, mark candidate `status="incomplete"` with error note — never crash the batch.
- Compute `overall_score` (weighted avg, renormalized over non-null criteria) and `data_completeness` deterministically in code (not LLM).
- Write `analysis.json` (list of {candidate, analysis, status}).

### Phase 4 — Memo (`memo.py`, `templates/memo.md.jinja`) — _depends on Phase 3's Analysis shape, not Phase 3 completion_

- `decide_call(overall_score, critical_risk, data_completeness)` — deterministic: >=70 & no critical risk -> Meeting; 50-69 -> Watch; <50 -> Pass; critical_risk or low data_completeness caps at Watch.
- Jinja2 template: call, 3-line rationale, 2-3 "things that would change the mind" (derived from null-criteria bases + risks), open questions/missing-data section.
- Render one `memos/{slug}.md` per candidate; optional `memos/_index.md` summary table sorted by score (nice-to-have, partner scanning aid).

### Phase 5 — Orchestrator (`run.py`) — _depends on Phases 2-4 module interfaces_

- argparse: `--topic`, `--stage {source,analyze,memo,all}`; loads `.env`; calls each stage's `main()`; never imports across stage internals beyond file I/O contract.

### Phase 6 — Tests (`tests/`) — _parallel with Phase 5, depends on Phase 1-4 code existing_

- `test_analysis_missing_founder_data` — pipeline doesn't crash on candidate missing founder info; null criteria handled.
- `test_analysis_malformed_llm_response` — invalid JSON/schema mismatch from mocked LLM is caught, retried once, then flagged not silently accepted.
- `test_memo_renders_minimal_analysis` — memo renders correctly from incomplete Analysis object.
- Mock LLM calls (monkeypatch `llm.call_structured`) and HTTP calls (respx) — no real network/API spend in tests.

### Phase 7 — Docs (ongoing during build, not a single end-step)

- `BUILD_LOG.md`: dated entries added as work happens during implementation.
- `README.md`: expand with setup/usage instructions (uv sync, .env setup, run.py commands); "Process & AI Usage" section left as a structured placeholder for the user to fill in first-person (cannot be authored by AI per brief).

### Phase 8 — Verification

1. `uv run pytest` — all pass.
2. `uv run ruff check .` and `uv run pyright` — no errors.
3. End-to-end smoke run: `uv run python run.py --topic "AI agents for SMBs" --stage all` (real API calls, costs tokens — confirm with user before running).
4. Re-run individual stages (`--stage memo`) to confirm file-based decoupling works without re-invoking sourcing/analysis.

## Relevant files (to be created)

- `pyproject.toml`, `.env.example`, `.gitignore` (update)
- `run.py`, `sourcing.py`, `product_hunt.py`, `analysis.py`, `memo.py`, `models.py`, `thesis.py`, `llm.py`
- `templates/memo.md.jinja`
- `tests/test_analysis.py`, `tests/test_memo.py`, `tests/conftest.py`
- `README.md`, `BUILD_LOG.md` (edits)

## Further Considerations

1. Product Hunt GraphQL search capability is uncertain (no confirmed free-text search over all posts) — recommend a quick live-schema spike as the very first implementation task before building the full sourcing funnel, to confirm topic-based query mapping works or find an alternative query strategy.
2. `critical_risk` boolean field addition to `Analysis` schema (vs. brief's literal example) — flagged as additive change, revisit if user objects.
3. Default candidate count N for final shortlist (10-20 range) — proposing 15 as default, configurable via CLI flag or thesis.py constant.
