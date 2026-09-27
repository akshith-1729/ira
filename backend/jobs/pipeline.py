import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ai.llm import LLM
from ai.prompts import build_prefix
from config import Settings
from graph.concepts import keep_concepts
from graph.evidence import evidence_gaps
from graph.gaps import bind_gaps
from graph.papers import PaperStore
from ingestion.arxiv import arxiv_to_record, fetch_arxiv
from ingestion.grobid import (
    parse_bibliography,
    parse_pdf,
    parse_tei,
    section_chunks,
    tei_to_local_record,
)
from ingestion.ids import classify_id
from ingestion.openalex import OpenAlex, to_record
from jobs.db import Database

log = logging.getLogger(__name__)


def _public_error(exc: BaseException) -> str:
    return re.sub(r"(?i)([?&]api_key=)[^&\s'\"<>]+", r"\1redacted", str(exc))


@dataclass
class Deps:
    settings: Settings
    openalex: OpenAlex
    store: PaperStore
    db: Database
    llm: LLM
    embed: Callable[[str, str], list[float]]


def _normalize_section(name: str) -> str:
    """GROBID heads carry numbering ("I. INTRODUCTION", "B. Data Description") that the
    model drops when it names the section, so compare without it."""
    cleaned = (name or "").strip().lower()
    cleaned = re.sub(r"^(?:[ivxlcdm]+|[a-z]|\d+)[.)]\s*", "", cleaned)
    return re.sub(r"[^a-z0-9]+", " ", cleaned).strip()


def ground_contributions(summary: dict, chunks: list[dict], paper_id: str) -> list[dict]:
    fallback = f"{paper_id}:abstract"
    by_id = {chunk["id"] for chunk in chunks if chunk.get("id")}
    by_section: dict[str, str] = {}
    for chunk in chunks:
        section = _normalize_section(chunk.get("section") or "")
        if section and chunk.get("id"):
            by_section.setdefault(section, chunk["id"])
    grounded = []
    for index, item in enumerate(summary.get("contributions") or []):
        if isinstance(item, str):
            text, section, named_id = item, "", ""
        else:
            text = item.get("text") or ""
            section = item.get("section") or ""
            named_id = item.get("chunk_id") or ""
        text = text.strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered.startswith("planned ") or "sim(" in lowered:
            continue
        status = "" if isinstance(item, str) else (item.get("status") or "")
        if status == "planned":
            continue
        chunk_id = named_id if named_id in by_id else by_section.get(_normalize_section(section), fallback)
        grounded.append(
            {
                "id": f"{paper_id}:contrib:{index}",
                "text": text,
                "chunk_ids": [chunk_id],
            }
        )
    return grounded


def _local_reference(reference: dict) -> dict:
    slug = re.sub(r"\W+", "-", reference["title"].lower()).strip("-")[:80]
    return {
        "id": f"local-ref:{slug}",
        "title": reference["title"],
        "year": reference.get("year"),
        "doi": reference.get("doi"),
        "abstract": "",
        "authors": [],
        "topics": [],
        "keywords": [],
        "venue": None,
        "openalex_id": None,
        "arxiv_id": None,
    }


def resolve_bibliography(references: list[dict], deps: Deps) -> list[dict]:
    """Turn a GROBID reference list into neighbor papers. A DOI gets the free single-record
    lookup; otherwise fall back to a verified title match, because a preprint cites by title
    only and an unresolved neighbor carries no topics for the gap diff. Anything still
    unresolved is kept by title so the citation edge exists."""
    records = []
    for reference in references[: deps.settings.citation_walk_limit]:
        doi = reference.get("doi")
        if doi:
            try:
                records.append(to_record(deps.openalex.get_work(doi)))
                continue
            except Exception:
                log.info("Reference DOI %s did not resolve", doi)
        if deps.settings.openalex_title_search:
            try:
                work = deps.openalex.find_by_title(reference["title"])
                if work is not None:
                    records.append(to_record(work))
                    continue
            except Exception as exc:
                log.warning("Title lookup failed for %r: %s", reference["title"], exc)
        records.append(_local_reference(reference))
    return records


def _usable_title(parsed: dict) -> str:
    title = (parsed.get("title") or "").strip()
    if title.lower() in {"", "untitled", "untitled upload"}:
        return ""
    return title


def looks_scholarly(parsed: dict, bibliography: list) -> bool:
    """DOI, a real reference list, or several headed sections — not a story PDF."""
    sections = parsed.get("sections") or []
    return bool(parsed.get("doi")) or len(bibliography) >= 3 or len(sections) >= 3


def is_parseable_paper(parsed: dict, bibliography: list) -> bool:
    title = _usable_title(parsed)
    abstract = (parsed.get("abstract") or "").strip()
    has_body = bool(abstract) or len(parsed.get("sections") or []) >= 2
    return bool(title and (has_body or looks_scholarly(parsed, bibliography)))


def _finish(
    job_id: str,
    record: dict,
    section_chunks_list: list[dict] | None,
    deps: Deps,
    *,
    embed: bool | None = None,
) -> None:
    paper_id = record["id"]
    deps.db.update_job(job_id, "running", "embedding", paper_id=paper_id)
    if section_chunks_list:
        deps.store.write_chunks(paper_id, section_chunks_list)
    do_embed = deps.settings.embed_on_ingest if embed is None else embed
    if do_embed:
        vector = deps.embed(record.get("title") or "", record.get("abstract") or "")
        deps.store.graph.set_embedding(paper_id, vector)

    deps.db.update_job(job_id, "running", "summary", paper_id=paper_id)
    chunks = deps.store.chunks_for(paper_id, include_neighbors=False)
    prefix = build_prefix(record.get("title") or "", record.get("abstract") or "", chunks)
    summary = deps.llm.summarize(prefix)
    grounded = ground_contributions(summary, chunks, paper_id)
    deps.store.set_summary(
        paper_id,
        (summary.get("summary") or "").strip(),
        [item["text"] for item in grounded],
        paper_type=str(summary.get("paper_type") or "").strip(),
        demonstrated=str(summary.get("demonstrated") or "").strip(),
    )
    deps.store.write_claims(paper_id, grounded, kind="summary")

    if not record.get("keywords"):
        try:
            deps.store.add_keywords(paper_id, deps.llm.keywords(prefix))
        except Exception as exc:
            # Not fatal, but log loudly: a retired model name shows up here first.
            log.warning("Keyword extraction failed for %s: %s", paper_id, exc)

    seed_concepts: list[dict] = []
    try:
        seed_concepts = keep_concepts(deps.llm.concepts(prefix))
    except Exception as exc:
        log.warning("Concept extraction failed for %s: %s", paper_id, exc)
    deps.store.replace_concepts(paper_id, seed_concepts)
    seed_names = {item["name"] for item in seed_concepts}

    try:
        neighbor_map = deps.llm.neighbor_concepts(deps.store.cited_records(paper_id))
        for neighbor_id, items in neighbor_map.items():
            deps.store.replace_concepts(neighbor_id, keep_concepts(items, seed_names, kinds={"method"}))
    except Exception as exc:
        log.warning("Neighbor concept extraction failed for %s: %s", paper_id, exc)

    deps.db.update_job(job_id, "running", "gaps", paper_id=paper_id)
    deps.store.clear_gaps(paper_id)
    for gap in evidence_gaps(paper_id, chunks):
        deps.store.write_gap(paper_id, gap)

    # Methods cited work uses that the seed does not. OpenAlex topic tags are a
    # fallback only, and the Cypher requires the seed itself to be tagged.
    concept_rows = deps.store.concept_diff(paper_id)[:3]
    topic_rows = []
    if not concept_rows:
        topic_rows = (deps.store.gap_diff(paper_id, min_neighbors=2) or deps.store.gap_diff(paper_id))[:2]
    diff = concept_rows or topic_rows
    if diff:
        try:
            narrative = deps.llm.narrate_gaps(prefix, diff)
        except Exception:
            log.exception("Gap narration failed for %s", paper_id)
            narrative = {"gaps": []}
        for gap in bind_gaps(diff, narrative, paper_id):
            deps.store.write_gap(paper_id, gap)
            venues = deps.store.venues_for_topics([gap["topic_id"], gap["topic_name"]])
            if venues:
                deps.store.link_venue(gap["direction_id"], venues[0]["id"])
    deps.db.update_job(job_id, "done", "done", paper_id=paper_id)


def refresh_generation(job_id: str, paper_id: str, deps: Deps) -> None:
    """Rewrite summary and gaps for a paper that is already in the graph."""
    try:
        paper = deps.store.get_paper(paper_id, owner=deps.settings.local_user_id)
        if paper is None:
            raise RuntimeError(f"Paper {paper_id} was not found")
        record = {
            "id": paper_id,
            "title": paper.get("title") or "",
            "abstract": paper.get("abstract") or "",
            "keywords": paper.get("keywords") or [],
        }
        _finish(job_id, record, None, deps, embed=False)
    except Exception as exc:
        log.exception("Refresh failed")
        deps.db.update_job(job_id, "error", "error", error=_public_error(exc))


def attach_openalex_neighbors(work: dict, deps: Deps) -> tuple[list[dict], list[dict]]:
    refs = [to_record(cited) for cited in deps.openalex.walk_references(work, deps.settings.citation_walk_limit)]
    related = []
    try:
        related = [to_record(item) for item in deps.openalex.walk_related(work, 8)]
    except Exception as exc:
        log.warning("OpenAlex related_works walk failed: %s", exc)
    return refs, related


def run_lookup(job_id: str, raw_id: str, deps: Deps) -> None:
    try:
        deps.db.update_job(job_id, "running", "metadata")
        kind, ident = classify_id(raw_id)
        refs = []
        related = []
        if kind == "arxiv":
            meta = fetch_arxiv(ident)
            record = arxiv_to_record(meta)
            if record.get("doi"):
                try:
                    work = deps.openalex.get_work(record["doi"])
                    resolved = to_record(work, arxiv_id=record.get("arxiv_id"))
                    record = resolved
                    deps.db.update_job(job_id, "running", "citations")
                    refs, related = attach_openalex_neighbors(work, deps)
                except Exception:
                    log.warning("OpenAlex did not resolve arXiv DOI %s", record.get("doi"))
        else:
            work = deps.openalex.get_work(ident)
            record = to_record(work)
            deps.db.update_job(job_id, "running", "citations")
            refs, related = attach_openalex_neighbors(work, deps)
        deps.store.upsert_paper(record, private=False, owner=None)
        if refs:
            deps.store.upsert_references(record["id"], refs)
        for neighbor in related:
            deps.store.upsert_paper(neighbor, private=False, owner=None)
        _finish(job_id, record, None, deps)
    except Exception as exc:
        log.exception("Lookup failed")
        deps.db.update_job(job_id, "error", "error", error=_public_error(exc))


def run_upload(job_id: str, pdf_path, deps: Deps) -> None:
    try:
        deps.db.update_job(job_id, "running", "parsing")
        tei = parse_pdf(pdf_path, deps.settings.grobid_url)
        parsed = parse_tei(tei)
        bibliography = parse_bibliography(tei)
        if not is_parseable_paper(parsed, bibliography):
            raise RuntimeError(
                "GROBID did not find a parseable paper (title plus abstract, sections, or references)."
            )
        deps.db.update_job(job_id, "running", "metadata")
        record = None
        refs = []
        related = []
        private = True
        work = None
        if parsed.get("doi"):
            try:
                work = deps.openalex.get_work(parsed["doi"])
            except Exception:
                log.warning("DOI %s was not resolved", parsed.get("doi"))
        if (
            work is None
            and deps.settings.openalex_title_search
            and looks_scholarly(parsed, bibliography)
            and parsed.get("title")
        ):
            # A published PDF often carries no machine-readable DOI. Matching the title gets
            # the paper its own topics and venue, without which gaps and venue fit are empty.
            try:
                work = deps.openalex.find_by_title(parsed["title"])
            except Exception as exc:
                log.warning("Title lookup failed for the upload: %s", exc)
        if work is not None:
            record = to_record(work)
            private = False
            deps.db.update_job(job_id, "running", "citations")
            refs, related = attach_openalex_neighbors(work, deps)
        if record is None:
            # Keyed by content, not by job, so re-uploading a PDF updates that paper
            # instead of adding a near-duplicate that then pollutes similarity search.
            digest = hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()[:16]
            record = tei_to_local_record(parsed, f"local:{digest}")
            private = True
        if not refs:
            deps.db.update_job(job_id, "running", "citations")
            refs = resolve_bibliography(bibliography, deps)
        deps.store.upsert_paper(record, private=private, owner=deps.settings.local_user_id if private else None)
        if refs:
            deps.store.upsert_references(record["id"], refs)
        for neighbor in related:
            deps.store.upsert_paper(neighbor, private=False, owner=None)
        _finish(job_id, record, section_chunks(record["id"], parsed), deps)
    except Exception as exc:
        log.exception("Upload failed")
        deps.db.update_job(job_id, "error", "error", error=_public_error(exc))
