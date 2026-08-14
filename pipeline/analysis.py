from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from llm import call_structured
from logging_config import configure_logging
from run_paths import ANALYSIS_FILENAME, latest_run_dir
from run_paths import shortlist_path as run_shortlist_path

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 8


def analysis_output_path(shortlist_path: Path) -> Path:
    """Derive a sibling analysis path from the shortlist path, e.g. runs/<run>/analysis.json."""
    return shortlist_path.with_name(ANALYSIS_FILENAME)

LABEL_SCORES: dict[str, int] = {
    "very_weak": 10,
    "weak": 30,
    "moderate": 50,
    "strong": 75,
    "very_strong": 95,
}

WEIGHTS: dict[str, float] = {
    "traction": 0.25,
    "product_specificity": 0.35,
    "differentiation": 0.25,
    "market_fit": 0.15,
}

SHORTLIST_LABELS = tuple(LABEL_SCORES)

SYSTEM_PROMPT = (
    "You are scoring early-stage startups based ONLY on their own self-description. "
    "Do not infer, assume, or add any information not present in the text provided.\n\n"
    "For each startup, score three dimensions. Each score must be one of exactly five labels: "
    "very_weak, weak, moderate, strong, very_strong. Do not return a raw number — return the label, "
    "and cite the specific phrase that drove it.\n\n"
    "For each of the three dimensions, also provide \"would_change_mind\": the most specific, concrete thing that "
    "— if true or stated in the copy — would change this score. Follow these rules strictly:\n\n"
    "- Ground it in what's ACTUALLY MISSING or WRONG about THIS SPECIFIC company's text, not a generic template answer. "
    "Do not default to a boilerplate phrase like \"if it mentioned SMBs\" unless you also say WHAT KIND of SMB signal is "
    "missing given what the company already described (for example, if the product already implies a vertical — dental, "
    "legal, hospitality, retail — name that vertical explicitly instead of saying \"SMBs\" generically).\n"
    "- Bad example (too generic, do not write like this): \"If it explicitly stated that it is designed for SMBs.\"\n"
    "- Good example (specific to the company's own text): \"If it named a business size or vertical — e.g. solo practices or "
    "small clinics — instead of describing generic 'engineering teams' with no size signal.\"\n"
    "- If the label is already very_strong, state what specific new fact would be needed to DISQUALIFY it (for example, a "
    "named enterprise-only client list, a stated enterprise price point) — not a vague \"if it got worse\".\n"
    "- The disqualifying condition must be a NEW fact not already true of the company as described — not a restatement of "
    "something already stated in the text (for example, if the company already says it's for solo founders, do not write "
    "\"if it stated it's only for solo founders\" as the disqualifier — that fact is already present, so it cannot disqualify anything).\n"
    "- Do not repeat the same would_change_mind phrasing across different companies in this batch. If you notice you're about "
    "to write something you already wrote for another company, find the detail specific to THIS company's text instead.\n\n"
    "---\n\n"
    "## 1. Problem & Product Specificity\n\n"
    "Using the tagline AND description together, does the startup name a SPECIFIC problem, a SPECIFIC user/persona, and a SPECIFIC mechanism (how it actually works)? Consider both fields as one combined input — the tagline often carries the core positioning, the description carries the supporting detail.\n\n"
    "- very_strong: names a specific problem AND a specific user AND explains the mechanism concretely.\n"
    "- strong: names a specific problem and mechanism, but user/persona is implied rather than stated.\n"
    "- moderate: names a general problem area with some concrete detail, but missing either a clear user or clear mechanism.\n"
    "- weak: mostly generic language with only vague gestures at specifics.\n"
    "- very_weak: no specific problem, user, or mechanism at all — pure marketing language.\n\n"
    "## 2. Differentiation Claim Strength\n\n"
    "Using the tagline AND description together, does the text state a REAL reason this is different from alternatives — a specific approach, price point, technical choice, or positioning — or is it just category buzzwords with no comparative claim?\n\n"
    "- very_strong: explicit, specific comparison to alternatives or a named category, with a concrete point of difference.\n"
    "- strong: implies a clear differentiator without directly naming competitors.\n"
    "- moderate: a differentiation claim is present but vague or unverifiable.\n"
    "- weak: only category placement, no comparative claim.\n"
    "- very_weak: no differentiation language at all.\n\n"
    "## 3. Market Fit to Thesis\n\n"
    "Thesis (target niche): {THESIS_DESCRIPTION}\n\n"
    "Using the tagline, description, AND category tags together, how well does this startup fit this specific thesis niche — not 'is this a good startup' in general, only fit to the stated niche. Sharing the same broad category (for example, 'AI agents') is NOT sufficient for a strong score. The actual customer must match the thesis. A product explicitly built for enterprise customers (naming Fortune 500s, major chains, enterprise-only positioning) should score very_weak or weak against an SMB-focused thesis even if the tech category matches.\n\n"
    "market_fit of 'strong' or 'very_strong' REQUIRES the text to name an explicit business-size or scale signal — e.g. "
    "solo founder, small team, a specific small-business vertical (dental, legal, local retail), or a price point/scale "
    "detail that implies small business (e.g. '$49/mo,' 'built in our own dental office'). Sharing a product category "
    "alone (SaaS, productivity, developer tools, AI agents) is explicitly INSUFFICIENT for strong/very_strong, even with "
    "hedged language like 'could appeal to,' 'perfect for,' or 'fits within' — these phrases are not evidence, do not let "
    "them justify a high score.\n\n"
    "- very_strong: explicitly targets the thesis niche's customer (names SMBs/small businesses/a specific small-business vertical) as its central/primary customer.\n"
    "- strong: names an explicit business-size or scale signal (solo founder, small team, a specific vertical, a small-business price point) but it is secondary/one of several ICPs rather than the clear primary focus.\n"
    "- moderate: shares tags/theme or uses category-adjacency language (\"could appeal to,\" \"perfect for\"), but names no explicit business-size or scale signal — ICP not explicitly named.\n"
    "- weak: only loose/tangential connection.\n"
    "- very_weak: unrelated, OR explicitly targets a different customer segment than the thesis.\n\n"
    "Startups to score (each scored using ONLY its tagline and description below; topics is provided additionally for the market_fit judgment only):\n"
    "{CANDIDATES_JSON}\n\n"
    "Return a JSON object with a single key named 'results' containing an array, one entry per startup, "
    "in exactly the same order as the input. Each criterion object must have the shape "
    "{\"label\": \"...\", \"basis\": \"...\", \"would_change_mind\": \"...\"}. "
    "Copy each startup's 'name' field verbatim — do not shorten, rephrase, or translate it. "
    "Return ONLY the JSON object. No other text."
)

LLM_SYSTEM_PROMPT = (
    "You are a strict JSON generator. Return only valid JSON that matches the requested schema. "
    "Do not add commentary, markdown, or code fences."
)


class ScoreAssessment(BaseModel):
    label: Literal["very_weak", "weak", "moderate", "strong", "very_strong"]
    basis: str
    would_change_mind: str


class ScoreDetail(ScoreAssessment):
    score: float


class StartupScores(BaseModel):
    name: str
    product_specificity: ScoreAssessment
    differentiation: ScoreAssessment
    market_fit: ScoreAssessment


class StartupScoresBatch(BaseModel):
    results: list[StartupScores] = Field(min_length=1)


class AnalysisResult(BaseModel):
    name: str
    tagline: str
    description: str
    website: str
    ph_launch_url: str
    created_at: str
    votes_count: int
    topics: str
    makers: str
    product_links: list[dict[str, Any]]
    scores: dict[str, float]
    scores_detail: dict[str, ScoreDetail]
    overall_score: float
    status: Literal["complete", "incomplete"] = "complete"
    error: str | None = None


def traction_score(votes: int, all_votes: list[int]) -> float:
    if not all_votes:
        return 50.0

    lo, hi = min(all_votes), max(all_votes)
    if hi == lo:
        return 50.0
    return ((votes - lo) / (hi - lo)) * 100


def overall_score(scores: dict[str, float]) -> float:
    return sum(scores[key] * WEIGHTS[key] for key in WEIGHTS)


def _label_to_score(label: str) -> int:
    return LABEL_SCORES[label]


def _detail_from_assessment(assessment: ScoreAssessment) -> ScoreDetail:
    return ScoreDetail(
        label=assessment.label,
        score=float(_label_to_score(assessment.label)),
        basis=assessment.basis,
        would_change_mind=assessment.would_change_mind,
    )


def _latest_shortlist_path() -> Path:
    return run_shortlist_path(latest_run_dir())


def _load_shortlist(input_path: Path) -> list[dict[str, Any]]:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {input_path}")
    return data


def _chunked(items: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def _build_llm_prompt(thesis: str, batch: list[dict[str, Any]]) -> str:
    candidates_payload = [
        {
            "name": candidate.get("name") or "",
            "tagline": candidate.get("tagline") or "",
            "description": candidate.get("description") or "",
            "topics": candidate.get("topics") or "",
        }
        for candidate in batch
    ]
    return SYSTEM_PROMPT.replace("{THESIS_DESCRIPTION}", thesis).replace(
        "{CANDIDATES_JSON}", json.dumps(candidates_payload, indent=2, ensure_ascii=False)
    )


def _score_batch(batch: list[dict[str, Any]], thesis: str) -> list[StartupScores]:
    base_prompt = _build_llm_prompt(thesis, batch)
    # Second attempt adds an explicit reminder about verbatim names and order.
    retry_suffix = (
        "\n\nCRITICAL: copy each startup's name field exactly as written in the input. "
        "Do not shorten, rephrase, or reorder entries."
    )

    for attempt, prompt in enumerate((base_prompt, base_prompt + retry_suffix), start=1):
        try:
            result = call_structured(
                StartupScoresBatch,
                LLM_SYSTEM_PROMPT,
                prompt,
                model=None,
                method="function_calling",
            )
            if len(result.results) != len(batch):
                raise ValueError(
                    f"LLM returned {len(result.results)} result(s) for {len(batch)} input(s)"
                )

            # Match by name (case/whitespace-tolerant), fall back to position.
            by_name: dict[str, StartupScores] = {
                item.name.strip().lower(): item for item in result.results
            }
            ordered: list[StartupScores] = []
            for i, candidate in enumerate(batch):
                key = (candidate.get("name") or "").strip().lower()
                if key in by_name:
                    ordered.append(by_name[key])
                else:
                    logger.warning(
                        "Name mismatch at position %d: expected %r — using positional fallback",
                        i,
                        candidate.get("name"),
                    )
                    ordered.append(result.results[i])

            return ordered
        except Exception as exc:
            logger.warning(
                "Analysis batch failed on attempt %d/2 for thesis=%r batch_size=%d: %s",
                attempt,
                thesis,
                len(batch),
                exc,
            )

    raise RuntimeError("Analysis batch failed after retry")


def _analysis_result_from_candidate(
    candidate: dict[str, Any],
    thesis: str,
    traction: float,
    llm_scores: StartupScores | None,
    error: str | None = None,
) -> AnalysisResult:
    scores: dict[str, float] = {"traction": traction}
    scores_detail: dict[str, ScoreDetail] = {}

    if llm_scores is None:
        fallback_basis = error or "LLM scoring unavailable"
        scores.update(
            {
                "product_specificity": 50.0,
                "differentiation": 50.0,
                "market_fit": 50.0,
            }
        )
        scores_detail.update(
            {
                "product_specificity": ScoreDetail(
                    label="moderate",
                    score=50.0,
                    basis=fallback_basis,
                    would_change_mind=fallback_basis,
                ),
                "differentiation": ScoreDetail(
                    label="moderate",
                    score=50.0,
                    basis=fallback_basis,
                    would_change_mind=fallback_basis,
                ),
                "market_fit": ScoreDetail(
                    label="moderate",
                    score=50.0,
                    basis=fallback_basis,
                    would_change_mind=fallback_basis,
                ),
            }
        )
        return AnalysisResult(
            name=str(candidate.get("name") or ""),
            tagline=str(candidate.get("tagline") or ""),
            description=str(candidate.get("description") or ""),
            website=str(candidate.get("website") or ""),
            ph_launch_url=str(candidate.get("ph_launch_url") or ""),
            created_at=str(candidate.get("created_at") or ""),
            votes_count=int(candidate.get("votes_count") or 0),
            topics=str(candidate.get("topics") or ""),
            makers=str(candidate.get("makers") or ""),
            product_links=list(candidate.get("product_links") or []),
            scores=scores,
            scores_detail=scores_detail,
            overall_score=round(overall_score(scores), 2),
            status="incomplete",
            error=error,
        )

    scores_detail.update(
        {
            "product_specificity": _detail_from_assessment(llm_scores.product_specificity),
            "differentiation": _detail_from_assessment(llm_scores.differentiation),
            "market_fit": _detail_from_assessment(llm_scores.market_fit),
        }
    )
    scores.update(
        {
            criterion: detail.score for criterion, detail in scores_detail.items()
        }
    )
    return AnalysisResult(
        name=str(candidate.get("name") or ""),
        tagline=str(candidate.get("tagline") or ""),
        description=str(candidate.get("description") or ""),
        website=str(candidate.get("website") or ""),
        ph_launch_url=str(candidate.get("ph_launch_url") or ""),
        created_at=str(candidate.get("created_at") or ""),
        votes_count=int(candidate.get("votes_count") or 0),
        topics=str(candidate.get("topics") or ""),
        makers=str(candidate.get("makers") or ""),
        product_links=list(candidate.get("product_links") or []),
        scores=scores,
        scores_detail=scores_detail,
        overall_score=round(overall_score(scores), 2),
    )


def analyze_shortlist(
    thesis: str,
    *,
    input_path: Path | None = None,
    output_path: Path | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[AnalysisResult]:
    shortlist_path = input_path or _latest_shortlist_path()
    output_path = output_path or analysis_output_path(shortlist_path)
    shortlist = _load_shortlist(shortlist_path)

    if not shortlist:
        logger.warning("Shortlist input %s is empty; writing an empty analysis file", shortlist_path)
        output_path.write_text("[]", encoding="utf-8")
        return []

    all_votes = [int(candidate.get("votes_count") or 0) for candidate in shortlist]
    logger.info(
        "Loaded %d shortlisted candidate(s) from %s; votes range=%s..%s",
        len(shortlist),
        shortlist_path,
        min(all_votes),
        max(all_votes),
    )

    results: list[AnalysisResult] = []
    batches = _chunked(shortlist, batch_size)
    for batch_index, batch in enumerate(batches, start=1):
        batch_tractions = [traction_score(int(candidate.get("votes_count") or 0), all_votes) for candidate in batch]
        try:
            llm_results = _score_batch(batch, thesis)
            for candidate, traction, llm_score in zip(batch, batch_tractions, llm_results, strict=True):
                results.append(_analysis_result_from_candidate(candidate, thesis, traction, llm_score))
        except Exception as exc:
            logger.warning(
                "Marking batch %d/%d incomplete for thesis=%r because scoring failed: %s",
                batch_index,
                len(batches),
                thesis,
                exc,
            )
            for candidate, traction in zip(batch, batch_tractions, strict=True):
                results.append(_analysis_result_from_candidate(candidate, thesis, traction, None, error=str(exc)))

    output_path.write_text(json.dumps([result.model_dump() for result in results], indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote analysis for %d candidate(s) to %s", len(results), output_path)
    return results


def main() -> None:
    configure_logging("analyze")
    parser = argparse.ArgumentParser(description="Score Product Hunt shortlist candidates")
    parser.add_argument("--topic", required=True, help="Investment theme to analyze")
    parser.add_argument("--input", type=Path, default=None, help="Shortlist JSON to analyze")
    parser.add_argument("--output", type=Path, default=None, help="Defaults to a sibling analysis.json next to --input")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    input_path = args.input or _latest_shortlist_path()
    output_path = args.output or analysis_output_path(input_path)
    results = analyze_shortlist(
        args.topic,
        input_path=input_path,
        output_path=output_path,
        batch_size=args.batch_size,
    )
    print(f"topic={args.topic}")
    print(f"input={input_path}")
    print(f"output={output_path}")
    print(f"batch_size={args.batch_size}")
    print(f"results={len(results)}")


if __name__ == "__main__":
    main()