"""Hand-curated public venue snapshots."""

import copy
import csv
from pathlib import Path

from venues.cache import VENUE_LOOKUP_CACHE
from venues.feasibility import score_feasibility
from venues.gap_analyzer import analyze_gaps
from venues.match import paper_text, score_venues

CATALOG_PATH = Path(__file__).with_name("venues.csv")
SHORTLIST_SIZE = 5

VENUE_FIELDS = (
    "id",
    "name",
    "kind",
    "tier",
    "fields",
    "sjr",
    "sjr_quartile",
    "avg_review_days",
    "acceptance_rate",
    "acceptance_year",
    "acceptance_source",
    "homepage",
    "publisher",
    "scopus",
    "open_access",
    "fit",
)

ADVICE_NOTES = (
    "These are public snapshots, not a live Scopus check or a promise of acceptance.",
)

MATCH_NOTES = (
    "Suggestions are for this paper. Scopus flags are a public snapshot, not a live index check. Not a promise you will be accepted.",
)

_KINDS = frozenset({"journal", "conference", "repository"})
_TIERS = frozenset({"top", "strong", "specialist"})
_QUARTILES = frozenset({"Q1", "Q2", "Q3", "Q4"})
_FLAGS = frozenset({"yes", "no", "unknown"})


def _blank(value: str) -> str | None:
    text = (value or "").strip()
    return text or None


def _number(value: str, cast):
    text = _blank(value)
    if text is None:
        return None
    return cast(text)


def _flag(raw: dict, key: str) -> str:
    value = (raw.get(key) or "unknown").strip().lower()
    if value not in _FLAGS:
        raise ValueError(f"Unknown {key} flag: {value}")
    return value


def _row(raw: dict) -> dict:
    kind = raw["kind"].strip()
    tier = raw["tier"].strip()
    if kind not in _KINDS:
        raise ValueError(f"Unknown venue kind: {kind}")
    if tier not in _TIERS:
        raise ValueError(f"Unknown venue tier: {tier}")
    quartile = _blank(raw.get("sjr_quartile") or "")
    if quartile and quartile not in _QUARTILES:
        raise ValueError(f"Unknown SJR quartile: {quartile}")
    rate = _number(raw.get("acceptance_rate") or "", float)
    if rate is not None and not 0 <= rate <= 1:
        raise ValueError(f"Acceptance rate must be a public fraction in [0, 1]: {rate}")
    homepage = _blank(raw.get("homepage") or "")
    if not homepage or not homepage.startswith(("http://", "https://")):
        raise ValueError(f"Venue homepage must be an http URL: {homepage}")
    fields = [name.strip() for name in (raw.get("fields") or "").split(";") if name.strip()]
    return {
        "id": raw["id"].strip(),
        "name": raw["name"].strip(),
        "kind": kind,
        "tier": tier,
        "fields": fields,
        "sjr": _number(raw.get("sjr") or "", float),
        "sjr_quartile": quartile,
        "avg_review_days": _number(raw.get("avg_review_days") or "", int),
        "acceptance_rate": rate,
        "acceptance_year": _number(raw.get("acceptance_year") or "", int),
        "acceptance_source": _blank(raw.get("acceptance_source") or ""),
        "homepage": homepage,
        "publisher": _blank(raw.get("publisher") or ""),
        "scopus": _flag(raw, "scopus"),
        "open_access": _flag(raw, "open_access"),
        "fit": placeholder_fit(),
    }


def placeholder_fit() -> dict:
    return {"score": None, "method": "placeholder", "reasons": []}


def _read_catalog(target: Path) -> list[dict]:
    with target.open(encoding="utf-8", newline="") as handle:
        rows = [_row(raw) for raw in csv.DictReader(handle)]
    if len(rows) < 20 or len(rows) > 40:
        raise ValueError(f"Venue catalog must hold 20-40 rows, found {len(rows)}")
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Venue catalog ids must be unique")
    return rows


def load_catalog(path: Path | None = None) -> list[dict]:
    target = path or CATALOG_PATH
    key = f"catalog:{target.resolve()}"
    rows = VENUE_LOOKUP_CACHE.get_or_set(key, lambda: _read_catalog(target))
    return copy.deepcopy(rows)


def clear_catalog_cache() -> None:
    VENUE_LOOKUP_CACHE.clear()


def build_venue_advice(paper: dict | None = None, llm=None) -> dict:
    """Catalog, fit, readiness, gaps, and a top-five shortlist for this paper."""
    catalog = load_catalog()
    paper_id = None
    if isinstance(paper, dict):
        paper_id = paper.get("id")
        if paper_text(paper).strip():
            scored = score_venues(paper, catalog)
            ready = score_feasibility(paper, scored)
            venues = ready["venues"]
            return {
                "paper_id": paper_id,
                "venues": venues,
                "shortlist": venues[:SHORTLIST_SIZE],
                "feasibility": ready["summary"],
                "gaps": analyze_gaps(paper, llm),
                "notes": list(MATCH_NOTES),
            }
    return {
        "paper_id": paper_id,
        "venues": catalog,
        "shortlist": [],
        "feasibility": None,
        "gaps": None,
        "notes": list(ADVICE_NOTES),
    }
