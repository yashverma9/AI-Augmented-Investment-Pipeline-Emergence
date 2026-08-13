# AI Augmented Investment Pipeline: Emergence Assignment

## Goal

A CLI pipeline that takes a topic query (e.g. "AI agents for SMBs"), sources 10-20
candidate startups, analyzes each against a defined investment thesis, and outputs
partner-ready one-page memos ending in Pass / Watch / Take a meeting.

Run mode: `python run.py --topic "AI agents for SMBs"` — this is the primary,
most-tested path. No UI, no server, no database. Outputs are files, committed
to the repo.

## Architecture — three decoupled, file-based stages

```
run.py                    orchestrator, supports --stage source|analyze|memo|all
sourcing.py   -> candidates.json
analysis.py   -> analysis.json   (reads candidates.json)
memo.py       -> memos/*.md      (reads analysis.json)
```

Each stage reads a file and writes a file — never calls another stage's functions
directly. This makes every stage independently re-runnable (e.g. re-run just
`memo.py` after fixing formatting, without re-spending API calls on sourcing/analysis).

No LangChain/LangGraph — this is a linear pipeline with no branching or
agent decision-making, so direct SDK calls + pydantic + tenacity cover
everything needed with less abstraction to debug.

## Stage 1: Sourcing

- Primary discovery source:
    1. Product Hunt APIs
    2. Hacker News Algolia Search API
       (`hn.algolia.com/api/v1/search`) — LATER
- Secondary/enrichment source: GitHub search API (technical signal) and/or
  each candidate's own website (team page, product copy) — NOT a new
  "source" in the anti-pattern sense, just reading data the candidate
  already surfaced.
- Do NOT use Crunchbase or X/Twitter APIs — both lost their free tiers.
- Flow (funnel, not flat):
    1. LLM call expands the topic into 3-5 good search queries.
    2. Hit both primary API with those queries -> ~100+ raw results. (start with Product Hunt for now)
    3. Cheap rule-based filtering: dedupe by domain, drop dead links
       (`httpx.head()` check) -> ~30-40 candidates.
    4. Cheap LLM relevance gate (name + one-liner only, yes/no vs thesis)
       -> ~15-25 candidates.
    5. For the shortlist only: fetch each company's own website (BeautifulSoup
       parse) and GitHub profile if linked, as enrichment.
    6. Rank by traction signal (HN points/comments, recency), cut to final 10-20.
- Candidate schema (pydantic): name, website, description, founders[],
  signal (type/detail/url), source_urls[].
- Cache raw API responses to disk before parsing (crash resilience,
  avoids re-fetching on rerun).
- Concurrency: asyncio + httpx.AsyncClient with a semaphore (~5 concurrent),
  not sequential loops — matters mainly for the LLM calls, which are the
  slow part.

## Stage 2: Analysis

- Thesis is specific and user-defined (not "good companies") — broken into
  3-5 named sub-criteria, not one blob (e.g. problem specificity, why-now,
  team-market fit, differentiation, traction strength).
- Use structured LLM output (tool-calling / schema-constrained), not
  freeform text parsed with regex. Validate every response against a
  pydantic model.
- Each sub-criterion score must cite the specific input fact it's based on
  — only claim what's in the provided source text, never inferred.
- Missing data handling: if a criterion has no supporting data (e.g. no
  founder info found anywhere), set it to `null` with a `basis` field
  explaining why — do NOT guess-fill a "reasonable middle" number.
  Overall score = average of only the non-null criteria. Track and expose
  `data_completeness` (e.g. "3/5 criteria") alongside the score.
- Overall score = fixed, disclosed weighted average — deterministic math,
  not another LLM call asking for "one final number."
- On schema validation failure: retry once with a stricter prompt, then
  mark the candidate incomplete rather than crashing the batch.
- Calibrate before full runs: test on 2-3 known companies (one obviously
  strong, one weak, one ambiguous) to confirm scores actually spread out
  rather than clustering (a known LLM scoring failure mode).

```python
class Analysis(BaseModel):
    team: str
    product: str
    market: str
    risks: list[str]
    scores: dict[str, int | None]      # per sub-criterion, null if no data
    scores_basis: dict[str, str]       # per sub-criterion, cites source fact
    data_completeness: str             # e.g. "3/5 criteria"
    overall_score: int
    rationale: str
```

## Stage 3: Memo

- Use templating (jinja2), NOT another freeform LLM generation pass — every
  line in the memo must trace back to a specific field in analysis.json.
  This is what keeps claims traceable to source, per the rubric.
- Call (Pass/Watch/Meeting) is a deterministic threshold rule over
  overall_score, NOT an LLM judgment call.
    - Example: score >= 70 and no critical risk flag -> Meeting;
      50-69 -> Watch; <50 -> Pass.
    - A critical risk flag OR low data_completeness caps the call at Watch
      regardless of score.
- Format: partner should understand the call in ~60 seconds. Keep it to:
  the call, 3-line rationale, 2-3 things that would change the mind
  (these should surface missing/unverified data directly, e.g. "confirm
  founder backgrounds," "verify differentiation claim").
- Missing data is not hidden — it's surfaced explicitly in the risks /
  open questions section.

## Non-goals (explicitly out of scope)

No React frontend, no job queue, no vector DB, no persistent server/endpoint,
no Crunchbase/Twitter integration (paywalled), no scoring all fields when
data isn't available (mark unknown instead of guessing).

## Testing (pytest, scoped not exhaustive)

- Pipeline doesn't crash on a candidate with missing founder data.
- Malformed/invalid LLM JSON response is caught and flagged, not silently
  accepted.
- Memo renders correctly from a minimal/incomplete analysis object.

## Process documentation (separate from code, but required)

- `BUILD_LOG.md`: short, dated entries written AS the work happens —
  what was tried, what broke, what changed and why. Not written
  retroactively at the end.
- `README.md` "Process & AI Usage" section, written in first person by
  the developer (not AI-generated): thesis rationale, what AI wrote vs.
  what was hand-written/edited, key moments where approach changed,
  what would be done with more time.
- Commit history should be incremental and descriptive (~15-25 commits for
  the full build), matching the build log's timeline — not one giant
  commit or a fabricated-looking sequence.
