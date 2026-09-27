import logging
import threading
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
    merge_intent,
    record_matches_terms,
)
from ingestion.ids import classify_id
from ingestion.openalex import OpenAlex
from jobs.pipeline import Deps, run_lookup, run_upload

log = logging.getLogger(__name__)
router = APIRouter()

MAX_PDF = 20 * 1024 * 1024


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


def _deps(request: Request) -> Deps:
    state = request.app.state
    return Deps(
        settings=state.settings,
        openalex=state.openalex,
        store=state.store,
        db=state.db,
        llm=state.llm,
        embed=embed_paper,
    )


def _require_db(request: Request) -> None:
    if not request.app.state.db.available:
        raise HTTPException(status_code=503, detail="Postgres is not running. Start it with docker compose up -d")


def _require_graph(request: Request) -> None:
    if not request.app.state.graph.available:
        raise HTTPException(status_code=503, detail="Neo4j is not running. Start it with docker compose up -d")


def _start(target, *args) -> None:
    threading.Thread(target=target, args=args, daemon=True).start()


@router.get("/health")
def health(request: Request):
    state = request.app.state
    neo4j = "up" if state.graph.available else "down"
    postgres = "up" if state.db.available else "down"
    grobid = "down"
    try:
        import httpx

        response = httpx.get(f"{state.settings.grobid_url.rstrip('/')}/api/isalive", timeout=1.5)
        if response.status_code == 200:
            grobid = "up"
    except Exception:
        grobid = "down"
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
    job_id = request.app.state.db.create_job("lookup")
    _start(run_lookup, job_id, body.openalex_id, _deps(request))
    return {"job_id": job_id}


@router.post("/papers/upload")
async def upload_paper(request: Request, file: UploadFile = File(...)):
    filename = (file.filename or "").lower()
    if not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a PDF")
    payload = await file.read()
    if len(payload) > MAX_PDF:
        raise HTTPException(status_code=413, detail="PDF exceeds 20MB")
    _require_db(request)
    _require_graph(request)
    job_id = request.app.state.db.create_job("upload")
    folder = Path(request.app.state.settings.data_dir) / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{job_id}.pdf"
    path.write_bytes(payload)
    _start(run_upload, job_id, path, _deps(request))
    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, request: Request):
    _require_db(request)
    job = request.app.state.db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "status": job["status"],
        "progress": job["progress"],
        "paper_id": job.get("paper_id"),
        "error": job.get("error"),
    }


def _paper_or_404(request: Request, paper_id: str) -> dict:
    _require_graph(request)
    paper = request.app.state.store.get_paper(paper_id, owner=request.app.state.settings.local_user_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


@router.get("/papers/{paper_id}")
def get_paper(paper_id: str, request: Request):
    paper = _paper_or_404(request, paper_id)
    topic_keys = paper.pop("topic_keys", [])
    try:
        recommended = request.app.state.store.similar_papers(
            paper_id,
            owner=request.app.state.settings.local_user_id,
            limit=8,
        )
    except Exception as exc:
        log.info("Similar-paper search skipped: %s", exc)
        recommended = []
    venues = request.app.state.store.venues_for_topics(topic_keys)
    paper["recommended_papers"] = recommended
    paper["recommended_venues"] = venues
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
    intent = fallback_intent(body.query)
    try:
        intent = merge_intent(body.query, request.app.state.llm.interpret_query(body.query))
    except Exception as exc:
        log.info("Query interpretation fell back: %s", exc)
    terms = intent_terms(intent, body.query)
    if not terms:
        raise HTTPException(status_code=400, detail="The query has no searchable terms")
    try:
        results = request.app.state.store.search(
            terms=terms,
            topic=body.topic,
            owner=request.app.state.settings.local_user_id,
            limit=10,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Graph search failed: {exc}") from exc
    catalog = []
    seen = {row["paper"]["id"] for row in results}
    gates = intent.get("must_match") or terms
    if request.app.state.settings.openalex_title_search:
        try:
            for lookup in catalog_queries(intent, body.query):
                if len(catalog) >= 5:
                    break
                found = 0
                for record in request.app.state.openalex.search_works(lookup, limit=8):
                    if record["id"] in seen or not record_matches_terms(record, gates):
                        continue
                    catalog.append(
                        {
                            "paper": {
                                "id": record["id"],
                                "title": record["title"],
                                "year": record.get("year"),
                                "summary": (record.get("abstract") or "")[:400],
                            },
                            "score": 0,
                            "reasons": [topic["name"] for topic in (record.get("topics") or [])[:3]],
                            "source": "openalex",
                        }
                    )
                    seen.add(record["id"])
                    found += 1
                    if len(catalog) >= 5:
                        break
                if found:
                    break
        except Exception as exc:
            log.info("OpenAlex catalog search skipped: %s", exc)
    retrieved = results + catalog
    brief = ""
    try:
        brief, retrieved = bind_search_brief(
            retrieved,
            request.app.state.llm.narrate_search(body.query, intent, retrieved),
        )
    except Exception as exc:
        log.info("Search brief fell back: %s", exc)
    results = [row for row in retrieved if row.get("source") != "openalex"]
    catalog = [row for row in retrieved if row.get("source") == "openalex"]
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
    feedback_id = request.app.state.db.log_feedback(
        "ask",
        body.question,
        [chunk["id"] for chunk in supporting],
        {"paper_id": paper_id, "answer": answer},
    )
    return {"answer": answer, "supporting_chunks": supporting, "feedback_id": feedback_id}


@router.get("/recommend/venues")
def recommend_venues(request: Request, topic: list[str] = Query(default=[])):
    _require_graph(request)
    return {"venues": request.app.state.store.venues_for_topics(topic)}


@router.post("/feedback/{feedback_id}")
def rate_feedback(feedback_id: str, body: FeedbackIn, request: Request):
    _require_db(request)
    rating = {"up": 1, "down": -1}.get(body.rating)
    if rating is None:
        raise HTTPException(status_code=400, detail="rating must be up or down")
    if not request.app.state.db.set_rating(feedback_id, rating):
        raise HTTPException(status_code=404, detail="Feedback row not found")
    return {"id": feedback_id, "rating": body.rating}
