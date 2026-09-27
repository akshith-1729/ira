import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from records import ChunkRecord

_NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def _text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return " ".join(" ".join(element.itertext()).split())


def parse_tei(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    title = _text(root.find(".//tei:titleStmt/tei:title", _NS))
    if not title:
        title = _text(root.find(".//tei:analytic/tei:title", _NS))
    abstract = " ".join(_text(p) for p in root.findall(".//tei:profileDesc/tei:abstract//tei:p", _NS))
    doi = None
    for idno in root.findall(".//tei:idno", _NS):
        if (idno.get("type") or "").upper() == "DOI" and idno.text:
            doi = idno.text.strip()
            break
    authors = []
    for author in root.findall(".//tei:fileDesc//tei:analytic/tei:author", _NS):
        fore = " ".join(_text(e) for e in author.findall(".//tei:forename", _NS)).strip()
        sur = " ".join(_text(e) for e in author.findall(".//tei:surname", _NS)).strip()
        name = " ".join(part for part in (fore, sur) if part)
        if not name:
            continue
        slug = name.lower().replace(" ", "-")
        authors.append({"id": f"local-author:{slug}", "name": name})
    sections = []
    for index, div in enumerate(root.findall("./tei:text/tei:body/tei:div", _NS)):
        head = _text(div.find("./tei:head", _NS)) or f"Section {index + 1}"
        paragraphs = [_text(p) for p in div.findall(".//tei:p", _NS)]
        body = " ".join(p for p in paragraphs if p)
        if body:
            sections.append({"section": head, "text": body, "position": index + 1})
    return {
        "title": title or "Untitled upload",
        "abstract": abstract,
        "doi": doi,
        "authors": authors,
        "sections": sections,
    }


def parse_bibliography(xml_text: str) -> list[dict]:
    """Reference list from the TEI. An unpublished upload has no DOI of its own, so this
    is the only citation data available for it."""
    root = ET.fromstring(xml_text)
    references = []
    for index, entry in enumerate(root.findall(".//tei:listBibl/tei:biblStruct", _NS)):
        title = _text(entry.find('.//tei:title[@level="a"]', _NS)) or _text(entry.find(".//tei:title", _NS))
        if not title:
            continue
        doi = None
        for idno in entry.findall(".//tei:idno", _NS):
            if (idno.get("type") or "").upper() == "DOI" and idno.text:
                doi = idno.text.strip()
                break
        year = None
        date = entry.find(".//tei:date", _NS)
        if date is not None:
            when = (date.get("when") or "").strip()
            if when[:4].isdigit():
                year = int(when[:4])
        references.append({"position": index, "title": title, "doi": doi, "year": year})
    return references


def section_chunks(paper_id: str, parsed: dict) -> list[ChunkRecord]:
    chunks: list[ChunkRecord] = []
    for section in parsed["sections"]:
        chunks.append(
            {
                "id": f"{paper_id}:s{section['position']}",
                "section": section["section"],
                "text": section["text"],
                "position": section["position"],
            }
        )
    return chunks


def tei_to_local_record(parsed: dict, paper_id: str) -> dict:
    return {
        "id": paper_id,
        "title": parsed["title"],
        "year": None,
        "doi": parsed.get("doi"),
        "abstract": parsed.get("abstract") or "",
        "authors": parsed.get("authors") or [],
        "topics": [],
        "keywords": [],
        "venue": None,
        "openalex_id": None,
        "arxiv_id": None,
    }


def parse_pdf(path: Path, grobid_url: str, client: httpx.Client | None = None) -> str:
    owns = client is None
    client = client or httpx.Client(timeout=180.0)
    try:
        with path.open("rb") as handle:
            response = client.post(
                f"{grobid_url.rstrip('/')}/api/processFulltextDocument",
                files={"input": (path.name, handle, "application/pdf")},
            )
        response.raise_for_status()
        return response.text
    except httpx.HTTPError as exc:
        raise RuntimeError(
            "GROBID is not reachable. Start it with: docker compose --profile pdf up -d"
        ) from exc
    finally:
        if owns:
            client.close()
