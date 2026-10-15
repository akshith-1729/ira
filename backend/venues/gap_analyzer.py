"""Independent venue-gap pass. Does not read or write the citation-graph gap tables."""

from __future__ import annotations

import re

from ai.prompts import VENUE_GAP_TASK, build_prefix

SCORE = re.compile(r"\b\d+\.\d+\b")
UNTESTED = re.compile(
    r"not yet (?:been )?(?:implemented|tested|evaluated)|no experimental results|"
    r"numerical (?:performance )?results are left|evaluation plan rather than|"
    r"left to future work",
    re.IGNORECASE,
)
EXPLICIT_NO_BASELINE = re.compile(
    r"no baseline|without a baseline|not compared|without comparison",
    re.IGNORECASE,
)
KINDS = frozenset({"results", "baseline", "dataset", "scope"})


def _blob(paper: dict) -> str:
    parts = [
        paper.get("title") or "",
        paper.get("abstract") or "",
        paper.get("demonstrated") or "",
        paper.get("paper_type") or "",
    ]
    return " ".join(part for part in parts if part)


def _gap(paper_id: str, kind: str, statement: str, evidence: str, source: str) -> dict:
    return {
        "id": f"{paper_id}:venue-gap:{kind}",
        "kind": kind,
        "statement": statement,
        "evidence": evidence,
        "source": source,
    }


def deterministic_gaps(paper: dict) -> list[dict]:
    paper_id = str(paper.get("id") or "paper")
    text = _blob(paper)
    paper_type = str(paper.get("paper_type") or "").lower()
    found: list[dict] = []

    if UNTESTED.search(text) or (paper_type == "proposal" and not SCORE.search(text)):
        cue = UNTESTED.search(text)
        found.append(
            _gap(
                paper_id,
                "results",
                "The method is specified but the text does not report a measured result.",
                cue.group(0) if cue else "proposal without a reported score",
                "deterministic",
            )
        )

    if EXPLICIT_NO_BASELINE.search(text):
        cue = EXPLICIT_NO_BASELINE.search(text)
        found.append(
            _gap(
                paper_id,
                "baseline",
                "A score is discussed without a named baseline comparison.",
                cue.group(0),
                "deterministic",
            )
        )
    return found


def parse_llm_gaps(paper: dict, payload: dict) -> list[dict]:
    paper_id = str(paper.get("id") or "paper")
    rows = []
    for item in payload.get("gaps") or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        statement = str(item.get("statement") or "").strip()
        evidence = str(item.get("evidence") or "").strip()
        if kind not in KINDS or not statement:
            continue
        rows.append(_gap(paper_id, kind, statement, evidence, "llm"))
    return rows


def merge_gaps(*groups: list[dict]) -> list[dict]:
    by_kind: dict[str, dict] = {}
    for group in groups:
        for gap in group:
            kind = gap["kind"]
            current = by_kind.get(kind)
            if current is None or (current.get("source") != "llm" and gap.get("source") == "llm"):
                by_kind[kind] = gap
    return list(by_kind.values())


def analyze_gaps(paper: dict, llm=None) -> list[dict]:
    found = deterministic_gaps(paper)
    if llm is None:
        return found
    prefix = build_prefix(paper.get("title") or "", paper.get("abstract") or "")
    try:
        payload = llm.complete(prefix, VENUE_GAP_TASK, fast=True)
    except Exception:
        return found
    if not isinstance(payload, dict):
        return found
    return merge_gaps(found, parse_llm_gaps(paper, payload))
