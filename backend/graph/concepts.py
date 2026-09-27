"""Normalize and filter concepts so OpenAlex field labels cannot become 'gaps'."""

from __future__ import annotations

import re

EVALUATION_ARTIFACTS = frozenset(
    {
        "accuracy",
        "bleu",
        "cifar",
        "f1",
        "glue",
        "imagenet",
        "mnli",
        "perplexity",
        "rouge",
        "squad",
        "wmt",
        "wmt 2014 english to french translation task",
        "wmt 2014 english to german translation task",
    }
)

GENERIC_CONCEPTS = frozenset(
    {
        "algorithm",
        "artificial intelligence",
        "computer science",
        "data mining",
        "data science",
        "database",
        "decoding methods",
        "deep learning",
        "encoder",
        "information retrieval",
        "information systems",
        "language model",
        "machine learning",
        "multimodal machine learning applications",
        "natural language processing",
        "natural language processing techniques",
        "parallelizable manifold",
        "sentence",
        "speech recognition",
        "survey",
        "systematic literature review",
        "systematic review",
        "task",
        "task (project management)",
        "case study",
        "dynamic analysis",
        "empirical study",
        "formal verification",
        "literature review",
        "penetration testing",
        "static analysis",
        "static code analysis",
    }
)


def generic_names() -> list[str]:
    names = {name.lower() for name in GENERIC_CONCEPTS}
    names.update(normalize_concept(name) for name in GENERIC_CONCEPTS)
    return sorted(names)


def normalize_concept(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def concept_id(name: str) -> str:
    slug = normalize_concept(name).replace(" ", "-")
    return f"concept:{slug}"


def is_generic(name: str) -> bool:
    key = normalize_concept(name)
    if not key or len(key) < 3:
        return True
    blocked = {normalize_concept(item) for item in GENERIC_CONCEPTS | EVALUATION_ARTIFACTS}
    if key in blocked:
        return True
    return any(token in blocked for token in key.split() if len(token) > 2 and token in {"wmt", "glue", "bleu", "rouge", "squad"})


_FAMILIES = (
    frozenset({"bert", "sentence bert", "sentence transformers", "sbert", "roberta"}),
    frozenset({"retrieval augmented generation", "rag"}),
    frozenset({"knowledge graph", "academic knowledge graph"}),
    frozenset({"transformer", "self attention"}),
)


def _expand(name: str) -> set[str]:
    key = normalize_concept(name)
    extra = {key} if key else set()
    for family in _FAMILIES:
        if key in family or any(key in member or member in key for member in family if key):
            extra |= family
    return extra


def covered_by(seed_names: set[str], candidate: str) -> bool:
    """A seed that uses Sentence-Transformers already covers BERT and Sentence-BERT."""
    target = normalize_concept(candidate)
    if not target:
        return False
    seeds: set[str] = set()
    for name in seed_names:
        seeds |= _expand(name)
    if target in seeds:
        return True
    expanded = _expand(candidate)
    if seeds & expanded:
        return True
    return any(target in seed or seed in target for seed in seeds if seed)


def keep_concepts(
    items: list[dict],
    seed_names: set[str] | None = None,
    *,
    kinds: set[str] | None = None,
) -> list[dict]:
    allowed = kinds or {"method", "dataset", "metric", "task"}
    kept: list[dict] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, str):
            name, kind = item, "method"
        else:
            name = (item.get("name") or "").strip()
            kind = (item.get("kind") or "method").strip().lower()
        if kind not in allowed or not name or is_generic(name):
            continue
        if seed_names is not None and covered_by(seed_names, name):
            continue
        key = normalize_concept(name)
        if key in seen:
            continue
        seen.add(key)
        kept.append({"id": concept_id(name), "name": name, "kind": kind})
    return kept
