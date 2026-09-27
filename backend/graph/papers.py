from records import ChunkRecord, PaperRecord

from graph.driver import Graph
from graph.gaps import concept_diff, gap_diff, link_venue, write_gap
from graph.search import search_papers, similar_papers

UPSERT_PAPER = """
MERGE (p:Paper {id: $id})
SET p.title = $title,
    p.year = $year,
    p.doi = $doi,
    p.abstract = $abstract,
    p.openalex_id = $openalex_id,
    p.arxiv_id = $arxiv_id
WITH p
FOREACH (a IN $authors |
  MERGE (author:Author {id: a.id})
  SET author.name = a.name
  MERGE (author)-[:PUBLISHED]->(p)
)
WITH p
FOREACH (t IN $topics |
  MERGE (topic:Topic {id: t.id})
  SET topic.name = t.name
  MERGE (p)-[:RELATED_TO]->(topic)
)
WITH p
FOREACH (k IN $keywords |
  MERGE (kw:Keyword {id: toLower(k)})
  SET kw.name = k
  MERGE (p)-[:CONTAINS]->(kw)
)
WITH p
FOREACH (_ IN CASE WHEN $venue_id IS NULL THEN [] ELSE [1] END |
  MERGE (v:Venue {id: $venue_id})
  SET v.name = $venue_name, v.kind = $venue_kind
  MERGE (p)-[:PUBLISHED_IN]->(v)
)
"""

MARK_PRIVATE = """
MATCH (p:Paper {id: $id})
SET p:Private, p.owner_user_id = $owner
"""

ABSTRACT_CHUNK = """
MATCH (p:Paper {id: $id})
MERGE (c:Chunk {id: $chunk_id})
SET c.section = 'abstract', c.text = $abstract, c.position = 0
MERGE (c)-[:PART_OF]->(p)
"""

WRITE_CHUNKS = """
UNWIND $chunks AS c
MERGE (ch:Chunk {id: c.id})
SET ch.section = c.section, ch.text = c.text, ch.position = c.position
WITH ch
MATCH (p:Paper {id: $paper_id})
MERGE (ch)-[:PART_OF]->(p)
"""

SET_SUMMARY = """
MATCH (p:Paper {id: $id})
SET p.summary = $summary, p.contributions = $contributions,
    p.paper_type = $paper_type, p.demonstrated = $demonstrated
"""

ADD_CONCEPTS = """
MATCH (p:Paper {id: $id})
FOREACH (c IN $concepts |
  MERGE (concept:Concept {id: c.id})
  SET concept.name = c.name, concept.kind = c.kind
  MERGE (p)-[:DISCUSSES]->(concept)
)
"""

CLEAR_SEED_CONCEPTS = """
MATCH (p:Paper {id: $id})-[r:DISCUSSES]->(:Concept)
DELETE r
"""

CLEAR_GAPS = """
MATCH (p:Paper {id: $id})-[:HAS_GAP]->(g:Gap)
OPTIONAL MATCH (g)-[:SUGGESTS]->(d:Direction)
OPTIONAL MATCH (c:Claim {gap_id: g.id})
DETACH DELETE g, d, c
"""

CITED_IDS = """
MATCH (p:Paper {id: $id})-[:CITES]->(cited:Paper)
RETURN collect(DISTINCT cited.id) AS ids
"""

CITED_ABSTRACTS = """
MATCH (p:Paper {id: $id})-[:CITES]->(cited:Paper)
RETURN cited.id AS id, cited.title AS title, cited.abstract AS abstract
"""

ADD_KEYWORDS = """
MATCH (p:Paper {id: $id})
FOREACH (k IN $keywords |
  MERGE (kw:Keyword {id: toLower(k)})
  SET kw.name = k
  MERGE (p)-[:CONTAINS]->(kw)
)
"""

VENUES_FOR_TOPICS = """
MATCH (p:Paper)-[:RELATED_TO]->(t:Topic)
WHERE t.id IN $topics OR t.name IN $topics
MATCH (p)-[:PUBLISHED_IN]->(v:Venue)
WITH v, count(DISTINCT p) AS papers, collect(DISTINCT p.id) AS source_papers
RETURN v.id AS id, v.name AS name, papers, source_papers[..5] AS source_papers
ORDER BY papers DESC
LIMIT 8
"""

PAPER_CORE = """
MATCH (p:Paper {id: $id})
OPTIONAL MATCH (a:Author)-[:PUBLISHED]->(p)
WITH p, collect(DISTINCT {id: a.id, name: a.name}) AS authors
OPTIONAL MATCH (p)-[:RELATED_TO]->(t:Topic)
WITH p, authors, collect(DISTINCT {id: t.id, name: t.name}) AS topics
OPTIONAL MATCH (p)-[:CONTAINS]->(k:Keyword)
RETURN p {.id, .title, .year, .doi, .abstract, .summary, .contributions,
          .paper_type, .demonstrated, .owner_user_id} AS paper,
       authors,
       topics,
       collect(DISTINCT k.name) AS keywords,
       p:Private AS private
"""

# Gaps need a neighbor that carries topics. Report why the diff was empty rather than
# leaving the panel blank.
CITATION_CONTEXT = """
MATCH (p:Paper {id: $id})
OPTIONAL MATCH (p)-[:CITES]->(cited:Paper)
WITH p, count(DISTINCT cited) AS cited
OPTIONAL MATCH (p)-[:CITES]->(resolved:Paper)-[:RELATED_TO]->(:Topic)
RETURN cited, count(DISTINCT resolved) AS cited_with_topics
"""

GAPS_FOR_PAPER = """
MATCH (p:Paper {id: $id})-[:HAS_GAP]->(g:Gap)-[:SUGGESTS]->(d:Direction)
OPTIONAL MATCH (c:Claim {gap_id: g.id})-[:SUPPORTED_BY]->(ch:Chunk)
OPTIONAL MATCH (d)-[:FITS_VENUE]->(v:Venue)
RETURN g.id AS gap_id, g.statement AS statement, g.topic_id AS topic_id, g.topic_name AS topic_name,
       g.source AS source,
       d.id AS direction_id, d.text AS direction,
       collect(DISTINCT {
         id: c.id, text: c.text, chunk_id: ch.id, section: ch.section, excerpt: ch.text
       }) AS claims,
       collect(DISTINCT {id: v.id, name: v.name}) AS venues
"""

CHUNKS_FOR_PAPER = """
MATCH (c:Chunk)-[:PART_OF]->(p:Paper {id: $id})
RETURN c.id AS id, c.section AS section, c.text AS text, c.position AS position
ORDER BY c.position
"""

NEIGHBOR_CHUNKS = """
MATCH (p:Paper {id: $id})-[:CITES]->(n:Paper)<-[:PART_OF]-(c:Chunk)
RETURN c.id AS id, c.section AS section, c.text AS text, c.position AS position, n.id AS paper_id
ORDER BY n.id, c.position
LIMIT 40
"""

SUBGRAPH_SEED = """
MATCH (p:Paper {id: $id})
RETURN p.id AS id, p.title AS title
"""

SUBGRAPH_AUTHORS = """
MATCH (a:Author)-[:PUBLISHED]->(p:Paper {id: $id})
RETURN a.id AS id, a.name AS name
LIMIT 12
"""

SUBGRAPH_TOPICS = """
MATCH (p:Paper {id: $id})-[:RELATED_TO]->(t:Topic)
RETURN t.id AS id, t.name AS name
"""

SUBGRAPH_CITED = """
MATCH (p:Paper {id: $id})-[:CITES]->(cited:Paper)
RETURN cited.id AS id, cited.title AS title
LIMIT 40
"""

SUBGRAPH_GAPS = """
MATCH (p:Paper {id: $id})-[:HAS_GAP]->(g:Gap)-[:SUGGESTS]->(d:Direction)
OPTIONAL MATCH (d)-[:FITS_VENUE]->(v:Venue)
RETURN g.id AS gap_id, g.statement AS statement,
       d.id AS direction_id, d.text AS direction,
       v.id AS venue_id, v.name AS venue_name
"""


def _params(record: PaperRecord) -> dict:
    venue = record.get("venue") or None
    keywords = [name for name in record.get("keywords") or [] if name and name.strip()]
    return {
        "id": record["id"],
        "title": record["title"],
        "year": record.get("year"),
        "doi": record.get("doi"),
        "abstract": record.get("abstract") or "",
        "openalex_id": record.get("openalex_id"),
        "arxiv_id": record.get("arxiv_id"),
        "authors": record.get("authors") or [],
        "topics": record.get("topics") or [],
        "keywords": keywords,
        "venue_id": venue["id"] if venue else None,
        "venue_name": venue["name"] if venue else None,
        "venue_kind": venue["kind"] if venue else None,
    }


class PaperStore:
    def __init__(self, graph: Graph):
        self.graph = graph

    def upsert_paper(self, record: PaperRecord, *, private: bool, owner: str | None) -> None:
        with self.graph.session() as session:
            session.run(UPSERT_PAPER, **_params(record)).consume()
            if private and owner:
                session.run(MARK_PRIVATE, id=record["id"], owner=owner).consume()
            abstract = (record.get("abstract") or "").strip()
            if abstract:
                session.run(
                    ABSTRACT_CHUNK,
                    id=record["id"],
                    chunk_id=f"{record['id']}:abstract",
                    abstract=abstract,
                ).consume()

    def upsert_references(self, seed_id: str, records: list[PaperRecord]) -> None:
        for record in records:
            self.upsert_paper(record, private=False, owner=None)
        if not records:
            return
        query = """
        MATCH (seed:Paper {id: $seed})
        UNWIND $ids AS cited_id
        MATCH (cited:Paper {id: cited_id})
        MERGE (seed)-[:CITES]->(cited)
        """
        with self.graph.session() as session:
            session.run(query, seed=seed_id, ids=[record["id"] for record in records]).consume()

    def write_chunks(self, paper_id: str, chunks: list[ChunkRecord]) -> None:
        if not chunks:
            return
        with self.graph.session() as session:
            session.run(WRITE_CHUNKS, paper_id=paper_id, chunks=chunks).consume()

    def set_summary(
        self,
        paper_id: str,
        summary: str,
        contributions: list[str],
        *,
        paper_type: str = "",
        demonstrated: str = "",
    ) -> None:
        with self.graph.session() as session:
            session.run(
                SET_SUMMARY,
                id=paper_id,
                summary=summary,
                contributions=contributions,
                paper_type=paper_type or None,
                demonstrated=demonstrated or None,
            ).consume()

    def add_concepts(self, paper_id: str, concepts: list[dict]) -> None:
        if not concepts:
            return
        with self.graph.session() as session:
            session.run(ADD_CONCEPTS, id=paper_id, concepts=concepts).consume()

    def replace_concepts(self, paper_id: str, concepts: list[dict]) -> None:
        with self.graph.session() as session:
            session.run(CLEAR_SEED_CONCEPTS, id=paper_id).consume()
        self.add_concepts(paper_id, concepts)

    def clear_gaps(self, paper_id: str) -> None:
        with self.graph.session() as session:
            session.run(CLEAR_GAPS, id=paper_id).consume()

    def cited_ids(self, paper_id: str) -> list[str]:
        with self.graph.session() as session:
            record = session.run(CITED_IDS, id=paper_id).single()
        return list((record["ids"] if record else None) or [])

    def cited_records(self, paper_id: str) -> list[dict]:
        with self.graph.session() as session:
            return [dict(record) for record in session.run(CITED_ABSTRACTS, id=paper_id)]

    def concept_diff(self, paper_id: str, *, min_neighbors: int = 1) -> list[dict]:
        with self.graph.session() as session:
            return concept_diff(session, paper_id, min_neighbors=min_neighbors)

    def add_keywords(self, paper_id: str, keywords: list[str]) -> None:
        cleaned = [name.strip() for name in keywords if name and name.strip()]
        if not cleaned:
            return
        with self.graph.session() as session:
            session.run(ADD_KEYWORDS, id=paper_id, keywords=cleaned).consume()

    def write_claims(self, paper_id: str, claims: list[dict], *, kind: str) -> None:
        if not claims:
            return
        with self.graph.session() as session:
            for claim in claims:
                chunks = []
                for chunk_id in claim["chunk_ids"]:
                    chunks.append(
                        {
                            "id": chunk_id,
                            "paper_id": paper_id,
                            "section": None,
                            "text": None,
                        }
                    )
                session.run(
                    """
                    MERGE (c:Claim {id: $claim_id})
                    SET c.text = $text, c.kind = $kind, c.gap_id = $gap_id
                    WITH c
                    UNWIND $chunks AS ch
                    MATCH (chunk:Chunk {id: ch.id})
                    MERGE (c)-[:SUPPORTED_BY]->(chunk)
                    """,
                    claim_id=claim["id"],
                    text=claim["text"],
                    kind=kind,
                    gap_id=claim.get("gap_id"),
                    chunks=chunks,
                ).consume()

    def gap_diff(self, paper_id: str, *, min_neighbors: int = 1) -> list[dict]:
        with self.graph.session() as session:
            return gap_diff(session, paper_id, min_neighbors=min_neighbors)

    def write_gap(self, paper_id: str, gap: dict) -> None:
        with self.graph.session() as session:
            write_gap(session, paper_id, gap)

    def link_venue(self, direction_id: str, venue_id: str) -> None:
        with self.graph.session() as session:
            link_venue(session, direction_id, venue_id)

    def venues_for_topics(self, topics: list[str]) -> list[dict]:
        cleaned = [topic for topic in topics if topic]
        if not cleaned:
            return []
        with self.graph.session() as session:
            rows = session.run(VENUES_FOR_TOPICS, topics=cleaned)
            return [
                {
                    "id": record["id"],
                    "name": record["name"],
                    "papers": record["papers"],
                    "source_papers": list(record["source_papers"] or []),
                }
                for record in rows
            ]

    def chunks_for(self, paper_id: str, *, include_neighbors: bool) -> list[dict]:
        with self.graph.session() as session:
            chunks = [dict(record) for record in session.run(CHUNKS_FOR_PAPER, id=paper_id)]
            if include_neighbors:
                for record in session.run(NEIGHBOR_CHUNKS, id=paper_id):
                    item = dict(record)
                    item.pop("paper_id", None)
                    chunks.append(item)
        return chunks

    def search(self, *, terms, topic, owner, limit):
        with self.graph.session() as session:
            return search_papers(
                session,
                terms=terms,
                topic=topic,
                owner=owner,
                limit=limit,
            )

    def similar_papers(self, paper_id: str, *, owner: str, limit: int = 8) -> list[dict]:
        with self.graph.session() as session:
            return similar_papers(session, paper_id, owner=owner, limit=limit)

    def get_paper(self, paper_id: str, *, owner: str) -> dict | None:
        with self.graph.session() as session:
            core = session.run(PAPER_CORE, id=paper_id).single()
            if core is None:
                return None
            paper = dict(core["paper"])
            if core["private"] and paper.get("owner_user_id") != owner:
                return None
            authors = [author for author in core["authors"] if author.get("id")]
            topics = [topic for topic in core["topics"] if topic.get("id")]
            keywords = [name for name in core["keywords"] if name]
            gap_rows = list(session.run(GAPS_FOR_PAPER, id=paper_id))
            context = session.run(CITATION_CONTEXT, id=paper_id).single()
        gaps = []
        directions = []
        for row in gap_rows:
            claims = []
            for claim in row["claims"] or []:
                if not claim.get("id"):
                    continue
                excerpt = claim.get("excerpt") or ""
                claims.append(
                    {
                        "id": claim["id"],
                        "text": claim.get("text"),
                        "chunk_id": claim.get("chunk_id"),
                        "section": claim.get("section"),
                        "excerpt": excerpt[:280],
                    }
                )
            venues = [venue for venue in row["venues"] or [] if venue.get("id")]
            gaps.append(
                {
                    "id": row["gap_id"],
                    "statement": row["statement"],
                    "topic_id": row["topic_id"],
                    "topic_name": row["topic_name"],
                    "source": row.get("source") or "topic",
                    "direction": row["direction"],
                    "claims": claims,
                    "venues": venues,
                }
            )
            directions.append({"id": row["direction_id"], "text": row["direction"], "venues": venues})
        topic_keys = []
        for topic in topics:
            topic_keys.extend([topic["id"], topic["name"]])
        return {
            "id": paper["id"],
            "title": paper.get("title"),
            "year": paper.get("year"),
            "doi": paper.get("doi"),
            "abstract": paper.get("abstract"),
            "authors": authors,
            "topics": topics,
            "keywords": keywords,
            "summary": paper.get("summary"),
            "paper_type": paper.get("paper_type"),
            "demonstrated": paper.get("demonstrated"),
            "contributions": paper.get("contributions") or [],
            "gaps": gaps,
            "directions": directions,
            "citation_context": {
                "cited": context["cited"] if context else 0,
                "cited_with_topics": context["cited_with_topics"] if context else 0,
            },
            "private": bool(core["private"]),
            "topic_keys": topic_keys,
        }

    def subgraph(self, paper_id: str) -> dict | None:
        with self.graph.session() as session:
            seed = session.run(SUBGRAPH_SEED, id=paper_id).single()
            if seed is None:
                return None
            authors = list(session.run(SUBGRAPH_AUTHORS, id=paper_id))
            topics = list(session.run(SUBGRAPH_TOPICS, id=paper_id))
            cited = list(session.run(SUBGRAPH_CITED, id=paper_id))
            gap_rows = list(session.run(SUBGRAPH_GAPS, id=paper_id))

        nodes = []
        links = []
        seen: set[str] = set()

        def add_node(kind: str, node_id: str, label: str, **extra) -> str:
            graph_id = node_id if kind == "Paper" else f"{kind}:{node_id}"
            if graph_id not in seen:
                seen.add(graph_id)
                nodes.append({"id": graph_id, "kind": kind, "label": label, "ref": node_id, **extra})
            return graph_id

        seed_id = add_node("Paper", seed["id"], seed["title"] or seed["id"], seed=True)
        for author in authors:
            author_id = add_node("Author", author["id"], author["name"] or author["id"])
            links.append({"source": author_id, "target": seed_id, "type": "PUBLISHED"})
        for topic in topics:
            topic_id = add_node("Topic", topic["id"], topic["name"] or topic["id"])
            links.append({"source": seed_id, "target": topic_id, "type": "RELATED_TO"})
        for paper in cited:
            cited_id = add_node("Paper", paper["id"], paper["title"] or paper["id"])
            links.append({"source": seed_id, "target": cited_id, "type": "CITES"})
        for row in gap_rows:
            gap_id = add_node("Gap", row["gap_id"], row["statement"] or "Gap")
            links.append({"source": seed_id, "target": gap_id, "type": "HAS_GAP"})
            direction_id = add_node("Direction", row["direction_id"], row["direction"] or "Direction")
            links.append({"source": gap_id, "target": direction_id, "type": "SUGGESTS"})
            if row["venue_id"]:
                venue_id = add_node("Venue", row["venue_id"], row["venue_name"] or row["venue_id"])
                links.append({"source": direction_id, "target": venue_id, "type": "FITS_VENUE"})
        return {"nodes": nodes, "links": links}
