import logging
import re
from difflib import SequenceMatcher
from urllib.parse import quote

import httpx

log = logging.getLogger(__name__)

from records import AuthorRecord, PaperRecord, TopicRecord, VenueRecord


class WorkNotFound(LookupError):
    """OpenAlex has no record for this work id. Citations do this; the seed should not."""

    def __init__(self, work_id: str):
        self.work_id = work_id
        super().__init__(f"OpenAlex has no work {work_id}")


def reconstruct_abstract(index: dict | None) -> str:
    if not index:
        return ""
    slots: dict[int, str] = {}
    for word, positions in index.items():
        for pos in positions:
            slots[int(pos)] = word
    if not slots:
        return ""
    return " ".join(slots[i] for i in sorted(slots))


def short_id(value: str | None) -> str:
    if not value:
        return ""
    return value.rstrip("/").split("/")[-1].split("?")[0]


def related_ids(work: dict) -> list[str]:
    ids: list[str] = []
    for ref in work.get("related_works") or []:
        wid = short_id(ref)
        if re.fullmatch(r"W\d+", wid):
            ids.append(wid)
    return ids


def reference_ids(work: dict) -> list[str]:
    ids: list[str] = []
    for ref in work.get("referenced_works") or []:
        wid = short_id(ref)
        if re.fullmatch(r"W\d+", wid):
            ids.append(wid)
    return ids


def work_url(work_id: str) -> str:
    """Single-record OpenAlex lookup. Never a list, filter, or search URL."""
    if work_id.startswith("10."):
        return "https://api.openalex.org/works/doi:" + quote(work_id, safe="")
    if not re.fullmatch(r"W\d+", work_id):
        raise ValueError(f"Not an OpenAlex work id or DOI: {work_id}")
    return f"https://api.openalex.org/works/{work_id}"


def _search_value(title: str) -> str:
    """Commas and pipes separate filter values in OpenAlex, so they cannot survive in one."""
    cleaned = re.sub(r"[,|:;]+", " ", title or "")
    return " ".join(cleaned.split())[:200]


def _title_ratio(wanted: str, found: str) -> float:
    def norm(value: str) -> str:
        return " ".join(re.sub(r"[^a-z0-9 ]+", " ", (value or "").lower()).split())

    return SequenceMatcher(None, norm(wanted), norm(found)).ratio()


def _authors(work: dict) -> list[AuthorRecord]:
    authors: list[AuthorRecord] = []
    for row in work.get("authorships") or []:
        author = row.get("author") or {}
        name = (author.get("display_name") or "").strip()
        if not name:
            continue
        author_id = short_id(author.get("id")) or "local-author:" + re.sub(r"\W+", "-", name.lower()).strip("-")
        authors.append({"id": author_id, "name": name})
    return authors


def _topics(work: dict) -> list[TopicRecord]:
    seen: set[str] = set()
    topics: list[TopicRecord] = []
    candidates = []
    if work.get("primary_topic"):
        candidates.append(work["primary_topic"])
    candidates.extend(work.get("topics") or [])
    for topic in candidates:
        topic_id = short_id(topic.get("id"))
        name = (topic.get("display_name") or "").strip()
        if not topic_id or not name or topic_id in seen:
            continue
        seen.add(topic_id)
        topics.append({"id": topic_id, "name": name})
    return topics


def _keywords(work: dict) -> list[str]:
    names: list[str] = []
    for item in work.get("keywords") or []:
        if isinstance(item, str):
            name = item
        else:
            name = item.get("display_name") or item.get("keyword") or ""
        name = name.strip()
        if name and name not in names:
            names.append(name)
    return names


def _venue(work: dict) -> VenueRecord | None:
    location = work.get("primary_location") or {}
    source = location.get("source") or {}
    venue_id = short_id(source.get("id"))
    name = (source.get("display_name") or "").strip()
    if not venue_id or not name:
        return None
    return {"id": venue_id, "name": name, "kind": source.get("type") or "source"}


def to_record(work: dict, arxiv_id: str | None = None) -> PaperRecord:
    paper_id = short_id(work.get("id"))
    if not re.fullmatch(r"W\d+", paper_id or ""):
        raise ValueError("OpenAlex response did not include a work id")
    abstract = work.get("abstract") if isinstance(work.get("abstract"), str) else ""
    if not abstract:
        abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    doi = work.get("doi") or None
    if isinstance(doi, str) and "doi.org/" in doi.lower():
        doi = re.split(r"doi\.org/", doi, flags=re.IGNORECASE)[-1]
    return {
        "id": paper_id,
        "title": (work.get("display_name") or "Untitled").strip(),
        "year": work.get("publication_year"),
        "doi": doi,
        "abstract": abstract or "",
        "authors": _authors(work),
        "topics": _topics(work),
        "keywords": _keywords(work),
        "venue": _venue(work),
        "openalex_id": paper_id,
        "arxiv_id": arxiv_id,
    }


class OpenAlex:
    def __init__(self, api_key: str, mailto: str = "", client: httpx.Client | None = None):
        self.api_key = api_key
        headers = {}
        if mailto:
            headers["User-Agent"] = f"research-assistant (mailto:{mailto})"
        self._client = client or httpx.Client(timeout=30.0, headers=headers)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def get_work(self, work_id: str) -> dict:
        if not self.api_key:
            raise RuntimeError("OPENALEX_API_KEY is required for OpenAlex lookups")
        url = work_url(work_id)
        if "search" in url.split("?", 1)[0]:
            raise ValueError("Keyword search is not used")
        response = self._client.get(url, params={"api_key": self.api_key})
        if response.status_code == 404:
            raise WorkNotFound(work_id)
        if response.is_error:
            raise RuntimeError(f"OpenAlex returned {response.status_code} for {work_id}")
        return response.json()

    def find_by_title(self, title: str, *, min_ratio: float = 0.90) -> dict | None:
        """The one metered call in this module. Uploaded preprints cite by title only, and
        without a resolved neighbor there is no topic to diff against, so gap analysis is
        empty. The match is verified against the returned title because a wrong match would
        put wrong topics in the graph."""
        if not self.api_key:
            raise RuntimeError("OPENALEX_API_KEY is required for OpenAlex lookups")
        query = _search_value(title)
        if len(query) < 20:
            return None
        response = self._client.get(
            "https://api.openalex.org/works",
            params={
                "filter": f"title.search:{query}",
                "per_page": 1,
                "api_key": self.api_key,
            },
        )
        if response.is_error:
            raise RuntimeError(f"OpenAlex title lookup returned {response.status_code}")
        results = response.json().get("results") or []
        if not results:
            return None
        found = results[0]
        if _title_ratio(title, found.get("display_name") or "") < min_ratio:
            return None
        return found

    def search_works(self, query: str, limit: int = 5) -> list[dict]:
        """Metered list call. Used only by the search page, never by citation walking."""
        if not self.api_key:
            raise RuntimeError("OPENALEX_API_KEY is required for OpenAlex lookups")
        cleaned = " ".join((query or "").split())[:200]
        if len(cleaned) < 4:
            return []
        response = self._client.get(
            "https://api.openalex.org/works",
            params={
                "search": cleaned,
                "per_page": min(max(limit, 1), 8),
                "api_key": self.api_key,
            },
        )
        if response.is_error:
            raise RuntimeError(f"OpenAlex search returned {response.status_code}")
        records = []
        for item in response.json().get("results") or []:
            try:
                records.append(to_record(item))
            except ValueError:
                continue
        return records

    def walk_references(self, work: dict, limit: int) -> list[dict]:
        works = []
        for wid in reference_ids(work)[:limit]:
            try:
                works.append(self.get_work(wid))
            except WorkNotFound:
                log.info("Skipping missing OpenAlex work %s", wid)
        return works

    def walk_related(self, work: dict, limit: int) -> list[dict]:
        """OpenAlex related_works are work IDs, so this stays on the free lookup path."""
        cited = set(reference_ids(work))
        works = []
        for wid in related_ids(work):
            if wid in cited:
                continue
            try:
                works.append(self.get_work(wid))
            except WorkNotFound:
                log.info("Skipping missing OpenAlex work %s", wid)
                continue
            if len(works) >= limit:
                break
        return works
