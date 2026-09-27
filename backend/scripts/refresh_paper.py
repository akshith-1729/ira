"""Rewrite summary and gaps for a paper already in Neo4j."""

import sys

from ai.llm import LLM
from config import get_settings
from graph.driver import Graph
from graph.papers import PaperStore
from ingestion.openalex import OpenAlex
from jobs.db import Database
from jobs.pipeline import Deps, refresh_generation


def main(paper_id: str) -> None:
    settings = get_settings()
    graph = Graph(settings)
    graph.connect()
    if not graph.available:
        raise SystemExit("Neo4j is not connected")
    graph.ensure_schema()
    db = Database(settings)
    db.ensure_schema()
    job_id = db.create_job("refresh")
    deps = Deps(
        settings=settings,
        openalex=OpenAlex(settings.openalex_api_key, settings.openalex_mailto),
        store=PaperStore(graph),
        db=db,
        llm=LLM(settings),
        embed=lambda title, abstract: [],
    )
    refresh_generation(job_id, paper_id, deps)
    job = db.get_job(job_id)
    print(job["status"], job["progress"], job.get("error") or "")
    graph.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "local:665e3376f8cad3cb")
