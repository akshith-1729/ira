"""Readiness for a venue: topic fit, venue tier, and upstream quality signals."""

from __future__ import annotations

TIER_DEMAND = {
    "top": 0.75,
    "strong": 0.55,
    "specialist": 0.30,
}

NOTHING_SHOWN = frozenset(
    {
        "",
        "nothing",
        "nothing was",
        "nothing was shown",
        "none",
        "not shown",
        "n/a",
    }
)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def quality_signal(paper: dict) -> tuple[float, list[str]]:
    """Use signals the pipeline already stores. Do not invent a new quality model."""
    reasons: list[str] = []
    score = 0.25
    paper_type = str(paper.get("paper_type") or "").strip().lower()
    demonstrated = str(paper.get("demonstrated") or "").strip()
    contributions = paper.get("contributions") or []

    if paper_type == "empirical":
        score += 0.25
        reasons.append("paper_type=empirical")
    elif paper_type == "survey":
        score += 0.15
        reasons.append("paper_type=survey")
    elif paper_type in {"proposal", "position"}:
        score += 0.05
        reasons.append(f"paper_type={paper_type}")
    elif paper_type:
        reasons.append(f"paper_type={paper_type}")
    else:
        reasons.append("paper_type missing")

    if demonstrated and demonstrated.lower() not in NOTHING_SHOWN:
        score += 0.25
        reasons.append("demonstrated result recorded")
    else:
        reasons.append("no demonstrated result")

    demonstrated_bits = 0
    specified_bits = 0
    for item in contributions:
        if isinstance(item, dict):
            status = str(item.get("status") or "").lower()
            if status == "demonstrated":
                demonstrated_bits += 1
            elif status == "specified":
                specified_bits += 1
        elif str(item).strip():
            specified_bits += 1
    if demonstrated_bits:
        score += 0.15
        reasons.append("a contribution is marked demonstrated")
    elif specified_bits:
        score += 0.05
        reasons.append("contributions are specified only")

    evidence = [
        gap
        for gap in paper.get("gaps") or []
        if isinstance(gap, dict) and gap.get("source") == "evidence"
    ]
    if evidence:
        score -= 0.15
        reasons.append("upstream evidence gap")

    return round(_clamp(score), 3), reasons


def venue_readiness(topic_fit: float, tier: str, quality: float) -> float:
    demand = TIER_DEMAND.get(tier, 0.55)
    clearance = _clamp(quality / demand)
    return round(0.5 * _clamp(topic_fit) + 0.5 * clearance, 3)


def score_feasibility(paper: dict, venues: list[dict]) -> dict:
    quality, quality_reasons = quality_signal(paper)
    enriched = []
    for venue in venues:
        fit = (venue.get("fit") or {}).get("score")
        topic_fit = float(fit) if fit is not None else 0.0
        readiness = venue_readiness(topic_fit, venue.get("tier") or "strong", quality)
        row = dict(venue)
        row["readiness"] = readiness
        enriched.append(row)

    ranked = sorted(
        enriched,
        key=lambda row: (
            -((row.get("fit") or {}).get("score") or 0),
            -row["readiness"],
            row["name"],
        ),
    )
    best = next((row for row in ranked if (row.get("fit") or {}).get("score")), ranked[0] if ranked else None)
    if best is None:
        return {
            "summary": None,
            "venues": enriched,
            "quality": quality,
            "quality_reasons": quality_reasons,
        }
    topic_fit = float((best.get("fit") or {}).get("score") or 0)
    summary = {
        "score": best["readiness"],
        "method": "topic_tier_quality",
        "venue_id": best["id"],
        "signals": {
            "topic_fit": topic_fit,
            "tier": best.get("tier"),
            "quality": quality,
        },
        "reasons": [
            f"best topic fit is {best['name']}",
            f"venue tier {best.get('tier')}",
            *quality_reasons,
        ],
    }
    return {"summary": summary, "venues": ranked, "quality": quality, "quality_reasons": quality_reasons}
