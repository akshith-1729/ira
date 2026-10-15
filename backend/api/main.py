import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai.llm import LLM
from api.accounts import router as accounts_router
from api.routes import router
from config import get_settings
from graph.driver import Graph
from graph.papers import PaperStore
from ingestion.openalex import OpenAlex
from jobs.db import Database

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    graph = Graph(settings)
    graph.connect()
    graph.ensure_schema()
    database = Database(settings)
    database.ensure_schema()
    app.state.settings = settings
    app.state.graph = graph
    app.state.store = PaperStore(graph)
    app.state.db = database
    app.state.llm = LLM(settings)
    app.state.openalex = OpenAlex(settings.openalex_api_key, settings.openalex_mailto)
    yield
    graph.close()
    app.state.openalex.close()


app = FastAPI(title="Research Assistant", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(accounts_router)
