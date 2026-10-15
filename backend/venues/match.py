"""Topic-space venue matching. Does not load SPECTER2."""

from __future__ import annotations

import math
import re

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "for",
        "in",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
        "all",
        "you",
        "need",
    }
)

# Extra phrases that belong to a catalog field. Exact field names are matched too.
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "machine learning": (
        "deep learning",
        "neural network",
        "transformer",
        "self-attention",
        "representation learning",
        "reinforcement learning",
        "gradient descent",
    ),
    "artificial intelligence": ("intelligent agent",),
    "natural language processing": (
        "nlp",
        "machine translation",
        "language model",
        "named entity",
        "text generation",
        "seq2seq",
    ),
    "computer vision": (
        "object detection",
        "image segmentation",
        "convolutional",
        "visual recognition",
    ),
    "data mining": ("knowledge discovery",),
    "information retrieval": ("search ranking", "query expansion"),
    "web": ("web search", "world wide web"),
    "security": (
        "side channel",
        "malware",
        "cryptograph",
        "vulnerability",
        "authentication",
        "memory safety",
    ),
    "software engineering": (
        "program repair",
        "code review",
        "requirements engineering",
    ),
    "human-computer interaction": ("user study", "usability", "interface design"),
    "databases": ("query optimizer", "transaction processing", "relational database"),
    "multidisciplinary": (),
    "preprint": (),
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def tokenize(text: str) -> list[str]:
    return [tok for tok in _TOKEN.findall((text or "").lower()) if tok not in _STOP and len(tok) > 1]


def paper_text(paper: dict) -> str:
    parts = [paper.get("title") or "", paper.get("abstract") or ""]
    for topic in paper.get("topics") or []:
        if isinstance(topic, dict):
            parts.append(topic.get("name") or "")
        elif topic:
            parts.append(str(topic))
    for keyword in paper.get("keywords") or []:
        parts.append(str(keyword))
    return " ".join(part for part in parts if part)


def field_space(catalog: list[dict]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for row in catalog:
        for field in row.get("fields") or []:
            key = _norm(field)
            if key and key not in seen:
                seen.add(key)
                names.append(key)
    return names


def field_activation(text: str, field: str) -> tuple[float, list[str]]:
    """How strongly `text` sits on one catalog-field dimension."""
    blob = _norm(text)
    reasons: list[str] = []
    score = 0.0
    if field and field in blob:
        score += 2.0
        reasons.append(field)
    for alias in FIELD_ALIASES.get(field, ()):
        if _norm(alias) and _norm(alias) in blob:
            score += 1.0
            reasons.append(alias)
    field_tokens = tokenize(field)
    paper_tokens = set(tokenize(text))
    if field_tokens:
        overlap = len(set(field_tokens) & paper_tokens) / len(set(field_tokens))
        if overlap:
            score += overlap
    return score, reasons


def embed_paper(text: str, fields: list[str]) -> tuple[list[float], dict[str, list[str]]]:
    vector = []
    hits: dict[str, list[str]] = {}
    for field in fields:
        value, reasons = field_activation(text, field)
        vector.append(value)
        if reasons:
            hits[field] = reasons
    return vector, hits


def embed_venue(venue: dict, fields: list[str]) -> list[float]:
    owned = {_norm(name) for name in venue.get("fields") or []}
    return [1.0 if field in owned else 0.0 for field in fields]


def cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    na = math.sqrt(sum(a * a for a in left))
    nb = math.sqrt(sum(b * b for b in right))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def score_venues(paper: dict, catalog: list[dict]) -> list[dict]:
    fields = field_space(catalog)
    text = paper_text(paper)
    paper_vec, hits = embed_paper(text, fields)
    scored = []
    for venue in catalog:
        value = cosine(paper_vec, embed_venue(venue, fields))
        reasons = []
        for field in venue.get("fields") or []:
            reasons.extend(hits.get(_norm(field), []))
        row = dict(venue)
        row["fit"] = {
            "score": round(value, 3),
            "method": "topic_embedding",
            "reasons": list(dict.fromkeys(reasons)),
        }
        scored.append(row)
    scored.sort(key=lambda row: (-(row["fit"]["score"] or 0), row["name"]))
    return scored
