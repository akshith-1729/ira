import logging
import threading
import time
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from ai.embeddings import embed_paper
from ai.prompts import build_prefix
from graph.search import (
    bind_search_brief,
    catalog_queries,
    fallback_intent,
    intent_terms,
    keep_relevant_rows,
    looks_like_title,
    merge_intent,
    query_is_meaningful,
    query_terms,
    record_matches_terms,
    same_title,
    title_hits,
    title_key,
)
from ingestion.ids import classify_id
from ingestion.openalex import OpenAlex
from jobs.pipeline import Deps, run_lookup, run_upload
from auth import current_user, require_user, viewer_id
from venues.catalog import build_venue_advice

log = logging.getLogger(__name__)
router = APIRouter()

MAX_PDF = 20 * 1024 * 1024
_GROBID_TTL = 45.0
_grobid = {"at": 0.0, "status": "down"}


def _grobid_status(url: str) -> str:
    now = time.monotonic()
    if now - _grobid["at"] < _GROBID_TTL:
        return _grobid["status"]
    status = "down"
    try:
        import httpx

        response = httpx.get(f"{url.rstrip('/')}/api/isalive", timeout=0.4)
        if response.status_code == 200:
            status = "up"
    except Exception:
        status = "down"
    _grobid["at"] = now
    _grobid["status"] = status
    return status


def _timed(fn, timeout: float):
    holder: list = []

    def work() -> None:
        try:
            holder.append(("ok", fn()))
        except Exception as exc:
            holder.append(("err", exc))

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive() or not holder:
        return None
    status, value = holder[0]
    if status != "ok":
        return None
    return value


def _search_brief(llm, query: str, intent: dict, retrieved: list[dict], terms: list[str]) -> tuple[str, list[dict]]:
    if not retrieved:
        return "", []
    narrative = _timed(lambda: llm.narrate_search(query, intent, retrieved), 3.0)
    if narrative is None:
        return "", keep_relevant_rows(retrieved, terms)
    return bind_search_brief(retrieved, narrative, terms)


def _catalog_from_index(
    searcher,
    lookups,
    *,
    query: str,
    seen: set,
    seen_titles: set,
    terms: list[str],
    title_mode: bool,
    source: str,
    limit: int = 5,
) -> list[dict]:
    catalog = []
    for lookup in lookups:
        if len(catalog) >= limit:
            break
        found = 0
        raw_hits = 0
        lookup_gates = query_terms(lookup) or terms
        records = _timed(
            lambda q=lookup: searcher.search_works(q, limit=8, title=title_mode),
            5.0,
        )
        if not records:
            continue
        for record in records:
            raw_hits += 1
            compact = title_key(record.get("title") or "")
            if record["id"] in seen or (compact and compact in seen_titles):
                continue
            if title_mode and not same_title(query, record.get("title") or ""):
                continue
            if not record_matches_terms(record, lookup_gates, require_all=title_mode):
                continue
            catalog.append(
                {
                    "paper": {
                        "id": record.get("doi") or record["id"],
                        "title": record["title"],
                        "year": record.get("year"),
                        "summary": (record.get("abstract") or "")[:400],
                    },
                    "score": 0,
                    "reasons": [topic["name"] for topic in (record.get("topics") or [])[:3]],
                    "source": source,
                }
            )
            seen.add(record["id"])
            if record.get("doi"):
                seen.add(record["doi"])
            if compact:
                seen_titles.add(compact)
            found += 1
            if len(catalog) >= limit:
                break
        if title_mode:
            if found:
                break
            continue
        if found or raw_hits:
            break
    return catalog


class LookupIn(BaseModel):
    openalex_id: str = Field(min_length=1)


class SearchIn(BaseModel):
    query: str = Field(min_length=1)
    topic: str | None = None


class AskIn(BaseModel):
    question: str = Field(min_length=1)
    scope: str | None = None


class FeedbackIn(BaseModel):
    rating: str


def _deps(request: Request, user_id: str) -> Deps:
    state = request.app.state
    return Deps(
        settings=state.settings,
        openalex=state.openalex,
        store=state.store,
        db=state.db,
        llm=state.llm,
        embed=embed_paper,
        user_id=user_id,
    )


def _require_db(request: Request) -> None:
    if not request.app.state.db.available:
        raise HTTPException(status_code=503, detail="Jobs are offline.")


def _require_graph(request: Request) -> None:
    if not request.app.state.graph.available:
        raise HTTPException(status_code=503, detail="The library is offline.")


def _start(target, *args) -> None:
    threading.Thread(target=target, args=args, daemon=True).start()


@router.get("/health")
def health(request: Request):
    state = request.app.state
    neo4j = "up" if state.graph.available else "down"
    postgres = "up" if state.db.available else "down"
    grobid = _grobid_status(state.settings.grobid_url)
    status = "ok" if neo4j == "up" and postgres == "up" else "degraded"
    return {"status": status, "neo4j": neo4j, "postgres": postgres, "grobid": grobid}


@router.post("/papers/lookup")
def lookup_paper(body: LookupIn, request: Request):
    try:
        classify_id(body.openalex_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _require_db(request)
    _require_graph(request)
    user = require_user(request)
    job_id = request.app.state.db.create_job("lookup", user["id"])
    _start(run_lookup, job_id, body.openalex_id, _deps(request, user["id"]))
    return {"job_id": job_id}


@router.post("/papers/upload")
async def upload_paper(request: Request, file: UploadFile = File(...)):
    filename = (file.filename or "").lower()
    if not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a PDF")
    payload = await file.read()
    if len(payload) > MAX_PDF:
        raise HTTPException(status_code=413, detail="PDF exceeds 20MB")
    if not payload.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File is not a PDF")
    _require_db(request)
    _require_graph(request)
    user = require_user(request)
    job_id = request.app.state.db.create_job("upload", user["id"])
    folder = Path(request.app.state.settings.data_dir) / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{job_id}.pdf"
    path.write_bytes(payload)
    _start(run_upload, job_id, path, _deps(request, user["id"]))
    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, request: Request):
    _require_db(request)
    user = require_user(request)
    job = request.app.state.db.get_job(job_id)
    if job is None or job.get("user_id") != user["id"]:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "status": job["status"],
        "progress": job["progress"],
        "paper_id": job.get("paper_id"),
        "error": job.get("error"),
    }


def _paper_or_404(request: Request, paper_id: str) -> dict:
    _require_graph(request)
    paper = request.app.state.store.get_paper(paper_id, owner=viewer_id(request))
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


@router.get("/papers/{paper_id}")
def get_paper(paper_id: str, request: Request):
    paper = _paper_or_404(request, paper_id)
    paper.pop("topic_keys", [])
    user = current_user(request)
    paper["in_library"] = bool(
        user and request.app.state.db.available and request.app.state.db.library_row(user["id"], paper_id)
    )
    paper["venue_advice"] = build_venue_advice(paper)
    return paper


@router.get("/papers/{paper_id}/graph")
def get_graph(paper_id: str, request: Request):
    _paper_or_404(request, paper_id)
    payload = request.app.state.store.subgraph(paper_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return payload


@router.post("/search")
def search(body: SearchIn, request: Request):
    _require_graph(request)
    _require_db(request)
    if not query_is_meaningful(body.query):
        return {
            "field": "",
            "intent": body.query,
            "brief": "That doesn't look like a research question, so we didn't search.",
            "results": [],
            "catalog": [],
            "feedback_id": None,
        }
    intent = fallback_intent(body.query)
    interpreted = _timed(lambda: request.app.state.llm.interpret_query(body.query), 3.0)
    if interpreted:
        intent = merge_intent(body.query, interpreted)
    if intent.get("valid") is False:
        return {
            "field": "",
            "intent": body.query,
            "brief": intent.get("reason") or "That doesn't look like a research question, so we didn't search.",
            "results": [],
            "catalog": [],
            "feedback_id": None,
        }
    terms = intent_terms(intent, body.query)
    if not terms:
        raise HTTPException(status_code=400, detail="That doesn't look like a research question, so we didn't search.")
    try:
        graph_rows = request.app.state.store.search(
            terms=terms,
            topic=body.topic,
            owner=viewer_id(request),
            limit=10,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Search failed.") from exc
    exact_graph = title_hits(graph_rows, body.query)
    catalog = []
    seen = {row["paper"]["id"] for row in exact_graph}
    seen_titles = {title_key(row["paper"].get("title") or "") for row in exact_graph}
    title_guess = looks_like_title(body.query)
    lookups = catalog_queries(intent, body.query)
    confirmed_title = False
    if request.app.state.settings.openalex_title_search:
        try:
            if title_guess:
                catalog = _catalog_from_index(
                    request.app.state.openalex,
                    [" ".join(body.query.split())[:200]],
                    query=body.query,
                    seen=seen,
                    seen_titles=seen_titles,
                    terms=terms,
                    title_mode=True,
                    source="openalex",
                )
            if exact_graph or catalog:
                results = exact_graph
                intent["intent"] = " ".join(body.query.split())
                confirmed_title = True
            else:
                seen = {row["paper"]["id"] for row in graph_rows}
                seen_titles = {title_key(row["paper"].get("title") or "") for row in graph_rows}
                results = graph_rows
                catalog = _catalog_from_index(
                    request.app.state.openalex,
                    lookups,
                    query=body.query,
                    seen=seen,
                    seen_titles=seen_titles,
                    terms=terms,
                    title_mode=False,
                    source="openalex",
                )
        except Exception as exc:
            log.info("OpenAlex catalog search skipped: %s", exc)
            results = exact_graph or graph_rows
    else:
        results = exact_graph if (title_guess and exact_graph) else graph_rows
        confirmed_title = bool(title_guess and exact_graph)
    retrieved = results + catalog
    brief = ""
    try:
        brief, retrieved = _search_brief(
            request.app.state.llm, body.query, intent, retrieved, terms
        )
    except Exception as exc:
        log.info("Search brief fell back: %s", exc)
        retrieved = keep_relevant_rows(retrieved, terms)
    results = [row for row in retrieved if row.get("source") == "graph"]
    catalog = [row for row in retrieved if row.get("source") != "graph"]
    actor = current_user(request)
    feedback_id = request.app.state.db.log_feedback(
        "search",
        body.query,
        [row["paper"]["id"] for row in results] + [row["paper"]["id"] for row in catalog],
        {
            "topic": body.topic,
            "field": intent.get("field"),
            "intent": intent.get("intent"),
            "catalog": [row["paper"]["id"] for row in catalog],
        },
        user_id=actor["id"] if actor else None,
    )
    return {
        "field": intent.get("field") or "",
        "intent": intent.get("intent") or body.query,
        "brief": brief,
        "results": results,
        "catalog": catalog,
        "feedback_id": feedback_id,
    }


@router.post("/papers/{paper_id}/ask")
def ask_paper(paper_id: str, body: AskIn, request: Request):
    paper = _paper_or_404(request, paper_id)
    _require_db(request)
    include_neighbors = (body.scope or "paper") == "citations"
    chunks = request.app.state.store.chunks_for(paper_id, include_neighbors=include_neighbors)
    prefix = build_prefix(paper.get("title") or "", paper.get("abstract") or "", chunks)
    try:
        payload = request.app.state.llm.answer(prefix, body.question)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    allowed = {chunk["id"]: chunk for chunk in chunks}
    supporting = []
    for chunk_id in payload.get("chunk_ids") or []:
        chunk = allowed.get(chunk_id)
        if chunk:
            supporting.append(
                {
                    "id": chunk["id"],
                    "section": chunk.get("section"),
                    "excerpt": (chunk.get("text") or "")[:280],
                }
            )
    answer = payload.get("answer") or ""
    actor = current_user(request)
    feedback_id = request.app.state.db.log_feedback(
        "ask",
        body.question,
        [chunk["id"] for chunk in supporting],
        {"paper_id": paper_id, "answer": answer},
        user_id=actor["id"] if actor else None,
    )
    return {"answer": answer, "supporting_chunks": supporting, "feedback_id": feedback_id}


@router.get("/recommend/venues")
def recommend_venues(request: Request, topic: list[str] = Query(default=[])):
    _require_graph(request)
    return {"venues": request.app.state.store.venues_for_topics(topic)}


@router.get("/advice/venues")
def venue_advice():
    """Public venue list for this paper. Scopus flags are snapshots, not a live lookup."""
    return build_venue_advice()


@router.post("/feedback/{feedback_id}")
def rate_feedback(feedback_id: str, body: FeedbackIn, request: Request):
    _require_db(request)
    rating = {"up": 1, "down": -1}.get(body.rating)
    if rating is None:
        raise HTTPException(status_code=400, detail="rating must be up or down")
    actor = current_user(request)
    if not request.app.state.db.set_rating(feedback_id, rating, user_id=actor["id"] if actor else None):
        raise HTTPException(status_code=404, detail="Feedback row not found")
    return {"id": feedback_id, "rating": body.rating}
