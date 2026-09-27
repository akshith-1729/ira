import xml.etree.ElementTree as ET

import httpx

from records import PaperRecord

_ATOM = "http://www.w3.org/2005/Atom"
_ARXIV = "http://arxiv.org/schemas/atom"
_NS = {"a": _ATOM, "arxiv": _ARXIV}


def parse_arxiv_atom(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    entry = root.find("a:entry", _NS)
    if entry is None:
        raise ValueError("arXiv returned no entry")
    title = " ".join((entry.findtext("a:title", default="", namespaces=_NS) or "").split())
    if not title or title.lower().startswith("error"):
        raise ValueError(title or "arXiv id was not found")
    summary = " ".join((entry.findtext("a:summary", default="", namespaces=_NS) or "").split())
    published = entry.findtext("a:published", default="", namespaces=_NS) or ""
    year = int(published[:4]) if len(published) >= 4 and published[:4].isdigit() else None
    doi = entry.findtext("arxiv:doi", default=None, namespaces=_NS)
    arxiv_id = ""
    raw_id = entry.findtext("a:id", default="", namespaces=_NS) or ""
    if "/abs/" in raw_id:
        arxiv_id = raw_id.split("/abs/")[-1].split("v")[0]
    authors = []
    for index, author in enumerate(entry.findall("a:author", _NS)):
        name = " ".join((author.findtext("a:name", default="", namespaces=_NS) or "").split())
        if name:
            slug = name.lower().replace(" ", "-")
            authors.append({"id": f"arxiv-author:{arxiv_id or index}:{slug}", "name": name})
    return {
        "title": title,
        "abstract": summary,
        "year": year,
        "doi": doi,
        "arxiv_id": arxiv_id,
        "authors": authors,
    }


def arxiv_to_record(meta: dict) -> PaperRecord:
    arxiv_id = meta.get("arxiv_id") or "unknown"
    return {
        "id": f"arxiv:{arxiv_id}",
        "title": meta["title"],
        "year": meta.get("year"),
        "doi": meta.get("doi"),
        "abstract": meta.get("abstract") or "",
        "authors": meta.get("authors") or [],
        "topics": [],
        "keywords": [],
        "venue": {"id": "arxiv", "name": "arXiv", "kind": "repository"},
        "openalex_id": None,
        "arxiv_id": arxiv_id,
    }


def fetch_arxiv(arxiv_id: str, client: httpx.Client | None = None) -> dict:
    owns = client is None
    client = client or httpx.Client(timeout=30.0)
    try:
        response = client.get(
            "https://export.arxiv.org/api/query",
            params={"id_list": arxiv_id},
        )
        response.raise_for_status()
        return parse_arxiv_atom(response.text)
    finally:
        if owns:
            client.close()
