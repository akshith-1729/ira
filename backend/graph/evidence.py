"""Deterministic holes in the paper's own sections. No LLM."""

from __future__ import annotations

import re

EVAL_HEAD = re.compile(
    r"\b(result|evaluation|experiment|performance measure|empirical)\b",
    re.IGNORECASE,
)
PROPOSAL_HEAD = re.compile(r"\b(expected|proposed|future work|plan)\b", re.IGNORECASE)
# Real scores look like 28.4 or 91.4%, not Precision@K or section numbers.
SCORE = re.compile(r"\b\d+\.\d+\b")
UNTESTED = re.compile(
    r"not yet (?:been )?(?:implemented|tested|evaluated)|no experimental results|"
    r"numerical (?:performance )?results are left|evaluation plan rather than",
    re.IGNORECASE,
)


def evidence_gaps(paper_id: str, chunks: list[dict]) -> list[dict]:
    """Gaps that follow from what the sections contain, not from a neighbor's field tag."""
    eval_chunks = [chunk for chunk in chunks if EVAL_HEAD.search(chunk.get("section") or "")]
    body = " ".join(chunk.get("text") or "" for chunk in chunks)
    eval_body = " ".join(chunk.get("text") or "" for chunk in eval_chunks)
    support = eval_chunks[0]["id"] if eval_chunks else f"{paper_id}:abstract"
    gaps: list[dict] = []

    if UNTESTED.search(body) or (eval_chunks and not SCORE.search(eval_body)):
        gaps.append(
            {
                "id": f"{paper_id}:gap:evidence:results",
                "topic_id": "evidence:results",
                "topic_name": "Missing empirical results",
                "source": "evidence",
                "statement": (
                    "The paper specifies an evaluation plan but does not report measured "
                    "scores, so the method is specified rather than demonstrated."
                ),
                "direction": (
                    "Run the planned retrieval and summarization tests and report "
                    "Precision@K, nDCG, or ROUGE against a named baseline."
                ),
                "direction_id": f"{paper_id}:direction:evidence:results",
                "claims": [
                    {
                        "id": f"{paper_id}:gap:evidence:results:0",
                        "text": "Evaluation sections name metrics and do not report scores.",
                        "chunks": [
                            {
                                "id": support,
                                "paper_id": paper_id,
                                "section": eval_chunks[0].get("section") if eval_chunks else "abstract",
                                "text": None,
                            }
                        ],
                    }
                ],
            }
        )

    if any(PROPOSAL_HEAD.search(chunk.get("section") or "") for chunk in chunks) and not SCORE.search(eval_body):
        # Already covered by the results gap; do not add a second slogan.
        if not gaps:
            gaps.append(
                {
                    "id": f"{paper_id}:gap:evidence:proposal",
                    "topic_id": "evidence:proposal",
                    "topic_name": "Design without a test",
                    "source": "evidence",
                    "statement": (
                        "Core sections are written as a proposed workflow. Nothing in the "
                        "text reports a completed experiment."
                    ),
                    "direction": "Implement the pipeline on a fixed corpus and publish the measurements.",
                    "direction_id": f"{paper_id}:direction:evidence:proposal",
                    "claims": [
                        {
                            "id": f"{paper_id}:gap:evidence:proposal:0",
                            "text": "Proposal language appears in the section heads.",
                            "chunks": [{"id": support, "paper_id": paper_id, "section": None, "text": None}],
                        }
                    ],
                }
            )
    return gaps
