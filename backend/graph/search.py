"""Search walks topics, keywords, and concepts. Similar-paper lookup is a graph walk."""

import re

from graph.concepts import generic_names

_STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "based",
        "for",
        "from",
        "in",
        "into",
        "of",
        "on",
        "or",
        "paper",
        "project",
        "regarding",
        "study",
        "system",
        "the",
        "to",
        "using",
        "with",
    }
)

# Problem words the user typed. They are not a research field.
# Topics that describe this app's own ingested paper, not the user's field.
_SELF = frozenset(
    {
        "arxiv",
        "information retrieval",
        "knowledge graph",
        "knowledge graphs",
        "literature review",
        "openalex",
        "recommendation system",
        "research assistant",
        "systematic literature review",
        "systematic review",
    }
)

_ASPECT = frozenset(
    {
        "challenge",
        "challenges",
        "flaw",
        "flaws",
        "issue",
        "issues",
        "problem",
        "problems",
        "vulnerability",
        "vulnerabilities",
        "weakness",
        "weaknesses",
    }
)

# These match almost every paper if we CONTAINS-search topics ("... Technologies").
_WEAK = frozenset(
    {
        "analysis",
        "application",
        "applications",
        "approach",
        "computing",
        "data",
        "detection",
        "flaws",
        "learning",
        "method",
        "methods",
        "model",
        "models",
        "modern",
        "monitoring",
        "network",
        "new",
        "quality",
        "research",
        "review",
        "systems",
        "technologies",
        "technology",
    }
)

SEARCH_CYPHER = """
MATCH (paper:Paper)
WHERE (NOT paper:Private OR paper.owner_user_id = $owner)
  AND (
    $topic IS NULL OR EXISTS {
      MATCH (paper)-[:RELATED_TO]->(t:Topic)
      WHERE t.id = $topic OR toLower(t.name) = toLower($topic)
    }
  )
OPTIONAL MATCH (paper)-[:RELATED_TO]->(topic:Topic)
WHERE any(term IN $terms WHERE toLower(topic.name) CONTAINS term)
OPTIONAL MATCH (paper)-[:CONTAINS]->(kw:Keyword)
WHERE any(term IN $terms WHERE toLower(kw.name) CONTAINS term)
OPTIONAL MATCH (paper)-[:DISCUSSES]->(concept:Concept)
WHERE any(term IN $terms WHERE toLower(concept.name) CONTAINS term)
WITH paper,
     [name IN collect(DISTINCT topic.name) WHERE name IS NOT NULL] AS topics,
     [name IN collect(DISTINCT kw.name) WHERE name IS NOT NULL] AS keywords,
     [name IN collect(DISTINCT concept.name) WHERE name IS NOT NULL] AS concepts
WHERE size(topics) + size(keywords) + size(concepts) > 0
   OR any(term IN $terms WHERE toLower(coalesce(paper.title, '')) CONTAINS term)
RETURN paper.id AS id, paper.title AS title, paper.year AS year,
       paper.summary AS summary, topics, keywords, concepts,
       (size(topics) * 3 + size(keywords) * 2 + size(concepts) * 2
        + CASE WHEN any(term IN $terms WHERE toLower(coalesce(paper.title, '')) CONTAINS term)
          THEN 2 ELSE 0 END) AS score
ORDER BY score DESC, paper.year DESC
LIMIT $limit
"""


def query_terms(text: str) -> list[str]:
    raw = (text or "").lower()
    phrases: list[str] = []
    if re.search(r"web\s*3(?:\.0)?", raw) or "web3" in raw:
        phrases.extend(["web3", "web 3"])
    words = re.findall(r"[a-z0-9]+", raw)
    terms = [word for word in words if word not in _STOP and word not in _WEAK and len(word) >= 4]
    extra: list[str] = []
    for term in list(phrases) + terms:
        if term == "cybersecurity":
            extra.extend(["cyber", "security", "intrusion"])
    return list(dict.fromkeys(phrases + terms + extra))


def catalog_query(text: str) -> str:
    """OpenAlex bag-of-words search treats 'technology' as a hit on everything."""
    raw = (text or "").strip()
    if re.search(r"web\s*3(?:\.0)?", raw, flags=re.I) or "web3" in raw.lower():
        return "web 3.0"
    terms = query_terms(raw)
    return " ".join(terms[:6]) or raw[:200]


def record_matches_terms(record: dict, terms: list[str]) -> bool:
    blob = " ".join(
        [
            record.get("title") or "",
            record.get("abstract") or "",
            " ".join(item.get("name") or "" for item in (record.get("topics") or []) if isinstance(item, dict)),
        ]
    ).lower()
    compact = re.sub(r"[^a-z0-9]+", "", blob)
    for term in terms:
        needle = re.sub(r"[^a-z0-9]+", "", term.lower())
        if needle and needle in compact:
            return True
        if term.lower() in blob:
            return True
    return False


def _clean_names(values, *, limit: int = 8) -> list[str]:
    names: list[str] = []
    for item in values or []:
        name = " ".join(str(item).split())
        lowered = name.lower()
        if len(name) < 2 or len(name) > 80:
            continue
        if lowered in _STOP or lowered in _WEAK or lowered in _ASPECT:
            continue
        names.append(name)
    return list(dict.fromkeys(names))[:limit]


def fallback_intent(text: str) -> dict:
    terms = query_terms(text)
    return {
        "field": "",
        "intent": (text or "").strip(),
        "topics": terms,
        "methods": [],
        "must_match": terms[:4],
        "catalog_query": catalog_query(text),
    }


def merge_intent(text: str, payload: dict | None) -> dict:
    """LLM topics replace raw tokens. Weak or empty model output keeps the fallback."""
    base = fallback_intent(text)
    if not isinstance(payload, dict):
        return base
    raw = (text or "").lower()
    topics = [
        name
        for name in _clean_names(payload.get("topics"))
        if name.lower() not in _SELF or name.lower() in raw
    ]
    methods = _clean_names(payload.get("methods"))
    must = _clean_names(payload.get("must_match"), limit=6)
    catalog = " ".join(str(payload.get("catalog_query") or "").split())[:200]
    if topics:
        base["topics"] = topics
    if methods:
        base["methods"] = methods
    if must:
        base["must_match"] = list(dict.fromkeys(must + base["must_match"]))[:6]
    if catalog and query_terms(catalog) and len(catalog.split()) <= 6:
        gates = must or topics or base["must_match"]
        compact = re.sub(r"[^a-z0-9]+", "", catalog.lower())
        if any(re.sub(r"[^a-z0-9]+", "", name.lower()) in compact for name in gates):
            base["catalog_query"] = catalog
    field = " ".join(str(payload.get("field") or "").split())[:120]
    question = " ".join(str(payload.get("intent") or "").split())[:400]
    if field and field.lower() not in _WEAK:
        base["field"] = field
    if question:
        base["intent"] = question
    return base


def intent_terms(intent: dict, query: str = "") -> list[str]:
    """Field phrases only. Methods like 'literature review' match the wrong local paper."""
    raw = (query or intent.get("intent") or "").lower()
    phrases: list[str] = []
    for name in (intent.get("topics") or []) + (intent.get("must_match") or []):
        phrase = name.lower().strip()
        if not phrase or phrase in _STOP or phrase in _WEAK or phrase in _ASPECT:
            continue
        if phrase in _SELF and phrase not in raw:
            continue
        phrases.append(phrase)
    return list(dict.fromkeys(phrases)) or query_terms(query or intent.get("intent") or "")


def catalog_queries(intent: dict, text: str) -> list[str]:
    queries: list[str] = []
    for value in (intent.get("catalog_query"), catalog_query(text)):
        cleaned = " ".join(str(value or "").split())
        if cleaned and cleaned not in queries:
            queries.append(cleaned)
    return queries


def bind_search_brief(rows: list[dict], narrative: dict | None) -> tuple[str, list[dict]]:
    """Attach the brief to retrieved papers. Invented ids die. Retrieval already gated the field."""
    known = {row["paper"]["id"]: row for row in rows if row.get("paper") and row["paper"].get("id")}
    brief = " ".join(str((narrative or {}).get("brief") or "").split())[:1200]
    if not isinstance(narrative, dict) or "hits" not in narrative:
        return brief, rows
    bound = []
    seen: set[str] = set()
    for item in narrative.get("hits") or []:
        if not isinstance(item, dict):
            continue
        paper_id = item.get("id")
        if paper_id not in known or paper_id in seen:
            continue
        row = dict(known[paper_id])
        why = " ".join(str(item.get("why") or "").split())
        if why:
            row["why"] = why[:400]
        bound.append(row)
        seen.add(paper_id)
    for row in rows:
        paper_id = row["paper"]["id"]
        if paper_id not in seen:
            bound.append(row)
            seen.add(paper_id)
    return brief, bound


def search_papers(session, *, terms: list[str], topic: str | None, owner: str, limit: int):
    topic_value = topic.strip() if isinstance(topic, str) and topic.strip() else None
    rows = []
    for record in session.run(
        SEARCH_CYPHER,
        terms=terms,
        topic=topic_value,
        owner=owner,
        limit=limit,
    ):
        reasons = [name for name in (record["topics"] or []) + (record["keywords"] or []) + (record["concepts"] or []) if name]
        rows.append(
            {
                "paper": {
                    "id": record["id"],
                    "title": record["title"],
                    "year": record["year"],
                    "summary": record["summary"],
                },
                "score": float(record["score"]),
                "reasons": reasons,
                "source": "graph",
            }
        )
    return rows


# Embedding neighbors in a tiny local corpus are meaningless (a cybersecurity
# review will rank a research-assistant paper at 0.91). Require a topic,
# concept, or citation path, then rank by how many of those links exist.
SIMILAR_CYPHER = """
MATCH (seed:Paper {id: $id})
MATCH (other:Paper)
WHERE other.id <> $id
  AND (NOT other:Private OR other.owner_user_id = $owner)
OPTIONAL MATCH (seed)-[:RELATED_TO]->(t:Topic)<-[:RELATED_TO]-(other)
WHERE NOT toLower(t.name) IN $generic
WITH seed, other, collect(DISTINCT t.name) AS topics
OPTIONAL MATCH (seed)-[:DISCUSSES]->(c:Concept)<-[:DISCUSSES]-(other)
WHERE NOT toLower(c.name) IN $generic
WITH seed, other, topics, collect(DISTINCT c.name) AS concepts
WITH seed, other, topics, concepts,
     EXISTS { MATCH (seed)-[:CITES]->(other) } AS cited,
     EXISTS { MATCH (seed)-[:CITES*2]-(other) } AS two_hop
WHERE size(topics) > 0 OR size(concepts) > 0 OR two_hop
RETURN other.id AS id, other.title AS title, other.year AS year,
       other.summary AS summary, topics, concepts, cited, two_hop,
       (size(topics) * 3 + size(concepts) * 2
        + CASE WHEN cited THEN 1 ELSE 0 END
        + CASE WHEN two_hop THEN 2 ELSE 0 END) AS score
ORDER BY score DESC, other.year DESC
LIMIT $limit
"""


def similar_papers(session, paper_id: str, *, owner: str, limit: int) -> list[dict]:
    rows = []
    for record in session.run(
        SIMILAR_CYPHER,
        id=paper_id,
        owner=owner,
        limit=limit,
        generic=generic_names(),
    ):
        reasons = []
        for name in record["topics"] or []:
            if name:
                reasons.append(name)
        for name in record["concepts"] or []:
            if name:
                reasons.append(name)
        if record["cited"]:
            reasons.append("cited by this paper")
        elif record["two_hop"]:
            reasons.append("shared citation path")
        rows.append(
            {
                "paper": {
                    "id": record["id"],
                    "title": record["title"],
                    "year": record["year"],
                    "summary": record["summary"],
                },
                "score": float(record["score"]),
                "reasons": reasons,
            }
        )
    return rows
