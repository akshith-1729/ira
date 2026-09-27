"""Cypher that finds topics covered by citation neighbors but not by the seed paper."""

from __future__ import annotations

from graph.concepts import generic_names

# A seed with no OpenAlex topics would treat every neighbor field as a gap
# (this paper "misses Sentiment Analysis" because it cited Sentence-BERT).
# Require the seed to be tagged, drop field-level labels, and ask for
# corroboration so one mis-tagged citation cannot invent a research hole.
GAP_DIFF_CYPHER = """
MATCH (seed:Paper {id: $id})-[:RELATED_TO]->(:Topic)
WITH DISTINCT seed
MATCH (seed)-[:CITES]-(neighbor:Paper)-[:RELATED_TO]->(topic:Topic)
WHERE NOT (seed)-[:RELATED_TO]->(topic)
  AND NOT toLower(topic.name) IN $generic
WITH topic, collect(DISTINCT neighbor {.id, .title, .abstract}) AS papers
WHERE size(papers) >= $min_neighbors
RETURN topic.id AS topic_id, topic.name AS topic_name, papers
ORDER BY size(papers) DESC, topic.name
"""

CONCEPT_DIFF_CYPHER = """
MATCH (seed:Paper {id: $id})-[:CITES]->(neighbor:Paper)-[:DISCUSSES]->(concept:Concept)
WHERE NOT (seed)-[:DISCUSSES]->(concept)
  AND concept.kind = 'method'
  AND NOT toLower(concept.name) IN $generic
WITH concept, collect(DISTINCT neighbor {.id, .title, .abstract}) AS papers
WHERE size(papers) >= $min_neighbors
RETURN concept.id AS topic_id, concept.name AS topic_name, concept.kind AS kind, papers
ORDER BY size(papers) DESC, concept.name
"""

WRITE_GAP = """
MATCH (p:Paper {id: $paper_id})
MERGE (g:Gap {id: $gap_id})
SET g.statement = $statement, g.topic_id = $topic_id, g.topic_name = $topic_name,
    g.source = $source
MERGE (p)-[:HAS_GAP]->(g)
MERGE (d:Direction {id: $direction_id})
SET d.text = $direction
MERGE (g)-[:SUGGESTS]->(d)
"""

WRITE_CLAIM = """
MERGE (c:Claim {id: $claim_id})
SET c.text = $text, c.gap_id = $gap_id, c.kind = $kind
WITH c
UNWIND $chunks AS ch
MERGE (chunk:Chunk {id: ch.id})
SET chunk.section = coalesce(ch.section, chunk.section),
    chunk.text = coalesce(ch.text, chunk.text)
WITH c, chunk, ch
MATCH (owner:Paper {id: ch.paper_id})
MERGE (chunk)-[:PART_OF]->(owner)
MERGE (c)-[:SUPPORTED_BY]->(chunk)
"""

LINK_VENUE = """
MATCH (d:Direction {id: $direction_id})
MATCH (v:Venue {id: $venue_id})
MERGE (d)-[:FITS_VENUE]->(v)
"""


def _generic_names() -> list[str]:
    return generic_names()


def _rows_from(records) -> list[dict]:
    rows = []
    for record in records:
        papers = []
        for paper in record["papers"] or []:
            papers.append(
                {
                    "id": paper["id"],
                    "title": paper.get("title") or paper["id"],
                    "abstract": (paper.get("abstract") or "")[:500],
                }
            )
        try:
            kind = record["kind"] or "concept"
        except (KeyError, TypeError):
            kind = "concept"
        rows.append(
            {
                "topic_id": record["topic_id"],
                "topic_name": record["topic_name"],
                "kind": kind,
                "papers": papers,
            }
        )
    return rows


def gap_diff(session, paper_id: str, *, min_neighbors: int = 1) -> list[dict]:
    return _rows_from(
        session.run(
            GAP_DIFF_CYPHER,
            id=paper_id,
            min_neighbors=min_neighbors,
            generic=_generic_names(),
        )
    )


def concept_diff(session, paper_id: str, *, min_neighbors: int = 1) -> list[dict]:
    return _rows_from(
        session.run(
            CONCEPT_DIFF_CYPHER,
            id=paper_id,
            min_neighbors=min_neighbors,
            generic=_generic_names(),
        )
    )


def bind_gaps(diff: list[dict], narrative: dict, paper_id: str) -> list[dict]:
    """Keep only topics the Cypher diff actually returned."""
    by_id = {row["topic_id"]: row for row in diff}
    bound = []
    for gap in narrative.get("gaps") or []:
        topic_id = gap.get("topic_id")
        row = by_id.get(topic_id)
        if row is None:
            continue
        allowed = [paper["id"] for paper in row["papers"]]
        allowed_set = set(allowed)
        claims_in = gap.get("claims") or []
        if not claims_in:
            claims_in = [{"text": gap.get("statement") or "", "paper_ids": allowed}]
        claims = []
        for index, claim in enumerate(claims_in):
            paper_ids = [pid for pid in (claim.get("paper_ids") or []) if pid in allowed_set]
            if not paper_ids:
                paper_ids = allowed
            text = (claim.get("text") or gap.get("statement") or "").strip()
            if not text:
                text = f"Cited work covers {row['topic_name']}, which this paper does not."
            claims.append(
                {
                    "id": f"{paper_id}:gap:{topic_id}:{index}",
                    "text": text,
                    "chunks": [
                        {
                            "id": f"{pid}:abstract",
                            "paper_id": pid,
                            "section": "abstract",
                            "text": None,
                        }
                        for pid in paper_ids
                    ],
                }
            )
        statement = (gap.get("statement") or "").strip()
        titles = "; ".join(paper["title"] for paper in row["papers"][:2])
        if not statement:
            statement = (
                f"Cited work ({titles}) uses {row['topic_name']}, which this paper does not adopt."
            )
        direction = (gap.get("direction") or "").strip()
        if not direction or direction.lower() in {"one measurable experiment", "one concrete next experiment"}:
            direction = (
                f"Compare this paper's method against {row['topic_name']} on its own retrieval or "
                "summarization task and report the metric change."
            )
        bound.append(
            {
                "id": f"{paper_id}:gap:{topic_id}",
                "statement": statement,
                "topic_id": topic_id,
                "topic_name": row["topic_name"],
                "source": row.get("kind") or "concept",
                "direction_id": f"{paper_id}:direction:{topic_id}",
                "direction": direction,
                "claims": claims,
            }
        )
    if bound or not diff:
        return bound
    fallback = {
        "gaps": [
            {
                "topic_id": row["topic_id"],
                "statement": "",
                "direction": "",
                "source": row.get("kind") or "concept",
                "claims": [],
            }
            for row in diff
        ]
    }
    return bind_gaps(diff, fallback, paper_id)


def write_gap(session, paper_id: str, gap: dict) -> None:
    session.run(
        WRITE_GAP,
        paper_id=paper_id,
        gap_id=gap["id"],
        statement=gap["statement"],
        topic_id=gap["topic_id"],
        topic_name=gap["topic_name"],
        source=gap.get("source") or "topic",
        direction_id=gap["direction_id"],
        direction=gap["direction"],
    ).consume()
    for claim in gap["claims"]:
        session.run(
            WRITE_CLAIM,
            claim_id=claim["id"],
            text=claim["text"],
            gap_id=gap["id"],
            kind="gap",
            chunks=claim["chunks"],
        ).consume()


def link_venue(session, direction_id: str, venue_id: str) -> None:
    session.run(LINK_VENUE, direction_id=direction_id, venue_id=venue_id).consume()
