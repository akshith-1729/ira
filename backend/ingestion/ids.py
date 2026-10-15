import re

_ARXIV = re.compile(r"^(?:arxiv:)?(\d{4}\.\d{4,5})(v\d+)?$", re.IGNORECASE)


def classify_id(raw: str) -> tuple[str, str]:
    """Return ('openalex'|'doi'|'arxiv', id). Rejects keyword search."""
    text = raw.strip()
    lowered = text.lower()
    if "search=" in lowered or text.startswith("?"):
        raise ValueError("Use a DOI, arXiv number, or paper id. A search phrase won’t work here.")

    if "openalex.org/" in lowered:
        wid = text.split("openalex.org/")[-1].split("/")[0].split("?")[0]
        if re.fullmatch(r"W\d+", wid):
            return "openalex", wid
        raise ValueError("That paper id is not valid.")

    if re.fullmatch(r"W\d+", text):
        return "openalex", text

    if "doi.org/" in lowered:
        doi = re.split(r"doi\.org/", text, flags=re.IGNORECASE)[-1].strip().strip("/")
        return "doi", doi

    if lowered.startswith("doi:"):
        return "doi", text.split(":", 1)[1].strip()

    if text.startswith("10."):
        return "doi", text

    compact = text.replace(" ", "")
    match = _ARXIV.match(compact)
    if match:
        return "arxiv", match.group(1)

    raise ValueError("Use a DOI, arXiv number, or paper id.")
