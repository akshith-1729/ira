"""Search walks topics, keywords, and concepts. Similar-paper lookup is a graph walk."""

import re
from difflib import SequenceMatcher

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

_KNOWN = frozenset(
    {
        "ai",
        "bert",
        "cnn",
        "gan",
        "gnn",
        "gpt",
        "ids",
        "llm",
        "ml",
        "nlp",
        "ocr",
        "pca",
        "rag",
        "rnn",
        "svm",
        "vae",
    }
)

_TOPIC_QUERY = re.compile(
    r"\?|"
    r"\b(?:how|what|why|when|where|which)\b|"
    r"\b(?:effects?|impacts?|influence|implications?|role)\b",
    flags=re.I,
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
        "need",
        "needed",
        "needs",
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

# Whole tokens only. CONTAINS 'ding' was matching 'embedding' and flooding search.
_TOKEN = (
    "(' ' + toLower(replace(replace(replace(coalesce(%s, ''), '-', ' '), '.', ' '), "
    "'/', ' ')) + ' ') CONTAINS (' ' + term + ' ')"
)

SEARCH_CYPHER = f"""
MATCH (paper:Paper)
WHERE (NOT paper:Private OR paper.owner_user_id = $owner)
  AND (
    $topic IS NULL OR EXISTS {{
      MATCH (paper)-[:RELATED_TO]->(t:Topic)
      WHERE t.id = $topic OR toLower(t.name) = toLower($topic)
    }}
  )
OPTIONAL MATCH (paper)-[:RELATED_TO]->(topic:Topic)
WHERE any(term IN $terms WHERE {_TOKEN % "topic.name"})
OPTIONAL MATCH (paper)-[:CONTAINS]->(kw:Keyword)
WHERE any(term IN $terms WHERE {_TOKEN % "kw.name"})
OPTIONAL MATCH (paper)-[:DISCUSSES]->(concept:Concept)
WHERE any(term IN $terms WHERE {_TOKEN % "concept.name"})
WITH paper,
     [name IN collect(DISTINCT topic.name) WHERE name IS NOT NULL] AS topics,
     [name IN collect(DISTINCT kw.name) WHERE name IS NOT NULL] AS keywords,
     [name IN collect(DISTINCT concept.name) WHERE name IS NOT NULL] AS concepts
WHERE size(topics) + size(keywords) + size(concepts) > 0
   OR any(term IN $terms WHERE {_TOKEN % "paper.title"})
RETURN paper.id AS id, paper.title AS title, paper.year AS year,
       paper.summary AS summary, topics, keywords, concepts,
       (size(topics) * 3 + size(keywords) * 2 + size(concepts) * 2
        + CASE WHEN any(term IN $terms WHERE {_TOKEN % "paper.title"})
          THEN 2 ELSE 0 END) AS score
ORDER BY score DESC, paper.year DESC
LIMIT $limit
"""


def token_in_text(term: str, text: str) -> bool:
    """'ding' must not hit 'embedding'."""
    needle = re.sub(r"[^a-z0-9]+", " ", (term or "").lower()).strip()
    hay = f" {re.sub(r'[^a-z0-9]+', ' ', (text or '').lower())} "
    return bool(needle) and f" {needle} " in hay


def query_terms(text: str) -> list[str]:
    raw = (text or "").lower()
    phrases: list[str] = []
    if re.search(r"web\s*3(?:\.0)?", raw) or "web3" in raw:
        phrases.extend(["web3", "web 3"])
    words = re.findall(r"[a-z0-9]+", raw)
    terms = [
        word
        for word in words
        if word not in _STOP and word not in _WEAK and (len(word) >= 4 or word in _KNOWN)
    ]
    extra: list[str] = []
    for term in list(phrases) + terms:
        if term == "cybersecurity":
            extra.extend(["cyber", "security", "intrusion"])
    return list(dict.fromkeys(phrases + terms + extra))


def looks_like_title(text: str) -> bool:
    """A paper title, not a research question. Bag search on titles dumps random works."""
    raw = text or ""
    if _TOPIC_QUERY.search(raw):
        return False
    words = [word for word in re.findall(r"[a-zA-Z0-9]+", raw) if word.lower() not in _STOP]
    if len(words) < 3:
        return False
    return not any(word.lower() in _ASPECT for word in words)


def catalog_query(text: str) -> str:
    """OpenAlex bag-of-words search treats 'technology' as a hit on everything."""
    raw = (text or "").strip()
    if re.search(r"web\s*3(?:\.0)?", raw, flags=re.I) or "web3" in raw.lower():
        return "web 3.0"
    if looks_like_title(raw):
        return " ".join(raw.split())[:200]
    terms = query_terms(raw)
    return " ".join(terms[:5]) or raw[:200]


def catalog_terms(text: str, terms: list[str]) -> list[str]:
    """Title tokens the catalog row must carry. 'need' is not a field."""
    required = [
        term
        for term in terms
        if " " in term or (len(re.sub(r"[^a-z0-9]+", "", term)) >= 5 and term not in _WEAK)
    ]
    return required or [term for term in terms if term not in _WEAK]


def record_matches_terms(record: dict, terms: list[str], *, require_all: bool = True) -> bool:
    title = (record.get("title") or "").lower()
    extra = "" if require_all else (record.get("abstract") or record.get("summary") or "").lower()
    hay = title if require_all else f"{title} {extra}"
    compact = re.sub(r"[^a-z0-9]+", "", hay)
    required = catalog_terms("", terms)
    if not required:
        return False
    hits = 0
    for term in required:
        needle = re.sub(r"[^a-z0-9]+", "", term.lower())
        matched = bool(needle and needle in compact) or term.lower() in hay
        if matched:
            hits += 1
        elif require_all:
            return False
    return hits > 0


def title_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def same_title(query: str, title: str, *, min_ratio: float = 0.90) -> bool:
    """Homage titles ('... In Speech Separation') are not the paper the user named."""
    left = re.sub(r"[^a-z0-9]+", "", (query or "").lower())
    right = re.sub(r"[^a-z0-9]+", "", (title or "").lower())
    if len(left) < 8 or len(right) < 8:
        return False
    if left == right:
        return True
    return SequenceMatcher(None, left, right).ratio() >= min_ratio


def title_hits(rows: list[dict], query: str) -> list[dict]:
    return [
        row
        for row in rows
        if same_title(query, ((row.get("paper") or {}).get("title") or ""))
    ]


def local_title_covers_query(rows: list[dict], query: str) -> bool:
    """The graph already has this paper. Do not pad the page with catalog leftovers."""
    return bool(title_hits(rows, query))


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


def _looks_like_keysmash(token: str) -> bool:
    """Long random letter runs are not a field. Short acronyms stay."""
    compact = re.sub(r"[^a-z0-9]+", "", (token or "").lower())
    if not compact or compact in _KNOWN or any(ch.isdigit() for ch in compact):
        return False
    letters = re.sub(r"[^a-z]", "", compact)
    if len(letters) < 8:
        return False
    vowels = sum(1 for ch in letters if ch in "aeiouy")
    return (vowels / len(letters)) < 0.22 or bool(re.search(r"[^aeiouy]{5,}", letters))


def query_is_meaningful(text: str) -> bool:
    """Rule out keysmash and empty chatter before any index or model is called."""
    raw = (text or "").strip()
    if len(raw) < 4:
        return False
    words = re.findall(r"[a-z0-9]+", raw.lower())
    content = [word for word in words if word not in _STOP and word not in _WEAK]
    if content and all(_looks_like_keysmash(word) for word in content):
        return False
    if looks_like_title(raw):
        return True
    if re.search(r"web\s*3(?:\.0)?", raw, flags=re.I) or "web3" in raw.lower():
        return True
    terms = query_terms(raw)
    return any(term in _KNOWN or " " in term or len(re.sub(r"[^a-z0-9]+", "", term)) >= 6 for term in terms)


def filter_graph_hits(rows: list[dict], query: str) -> list[dict]:
    """A paper title is not a license to dump every cousin that shares one token."""
    if not looks_like_title(query):
        return rows
    return title_hits(rows, query)


def fallback_intent(text: str) -> dict:
    terms = query_terms(text)
    ok = query_is_meaningful(text)
    return {
        "field": "",
        "intent": (text or "").strip(),
        "topics": terms,
        "methods": [],
        "must_match": terms[:4],
        "catalog_query": catalog_query(text),
        "valid": ok,
        "reason": "" if ok else "That doesn't look like a research question, so we didn't search.",
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
        base["catalog_query"] = catalog
    field = " ".join(str(payload.get("field") or "").split())[:120]
    question = " ".join(str(payload.get("intent") or "").split())[:400]
    if field and field.lower() not in _WEAK:
        base["field"] = field
    if question:
        base["intent"] = question
    if payload.get("valid") is False:
        base["valid"] = False
        base["reason"] = " ".join(str(payload.get("reason") or base["reason"]).split())[:200]
    elif payload.get("valid") is True:
        base["valid"] = True
        base["reason"] = ""
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


def lexical_relevance(row: dict, terms: list[str]) -> int:
    title = (row.get("paper") or {}).get("title") or ""
    reasons = " ".join(row.get("reasons") or [])
    score = 0
    for term in terms:
        if token_in_text(term, title):
            score += 3
        elif token_in_text(term, reasons):
            score += 1
    if row.get("source") == "graph":
        score += 1
    return score


def keep_relevant_rows(rows: list[dict], terms: list[str]) -> list[dict]:
    """No keyword leftovers. A row stays only if a field token is in the title."""
    kept = []
    for row in rows:
        title = (row.get("paper") or {}).get("title") or ""
        if any(token_in_text(term, title) for term in terms):
            item = dict(row)
            item["relevance"] = lexical_relevance(item, terms)
            kept.append(item)
    kept.sort(key=lambda row: (-int(row.get("relevance") or 0), row.get("source") != "graph"))
    return kept


def bind_search_brief(rows: list[dict], narrative: dict | None, terms: list[str] | None = None) -> tuple[str, list[dict]]:
    """Rank retrieved ids by relevance. Invented ids die. Irrelevant ids are dropped."""
    terms = terms or []
    known = {row["paper"]["id"]: row for row in rows if row.get("paper") and row["paper"].get("id")}
    brief = " ".join(str((narrative or {}).get("brief") or "").split())[:1200]
    if not isinstance(narrative, dict) or "hits" not in narrative:
        return brief, keep_relevant_rows(rows, terms)
    bound = []
    seen: set[str] = set()
    for item in narrative.get("hits") or []:
        if not isinstance(item, dict):
            continue
        paper_id = item.get("id")
        if paper_id not in known or paper_id in seen:
            continue
        if item.get("relevant") is False:
            seen.add(paper_id)
            continue
        row = dict(known[paper_id])
        why = " ".join(str(item.get("why") or "").split())
        if why:
            row["why"] = why[:400]
        try:
            row["relevance"] = int(item.get("score") or lexical_relevance(row, terms))
        except (TypeError, ValueError):
            row["relevance"] = lexical_relevance(row, terms)
        bound.append(row)
        seen.add(paper_id)
    if not bound:
        if narrative.get("hits"):
            return brief, []
        return brief, keep_relevant_rows(rows, terms)
    bound.sort(key=lambda row: -int(row.get("relevance") or 0))
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
        title = record["title"] or ""
        if not any(token_in_text(term, title) or any(token_in_text(term, name) for name in reasons) for term in terms):
            continue
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
