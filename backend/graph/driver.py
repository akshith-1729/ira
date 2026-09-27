"""Neo4j driver. Embeddings live on Paper.embedding in this same database."""

from __future__ import annotations

import logging
from contextlib import contextmanager

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from config import Settings

log = logging.getLogger(__name__)

SCHEMA = [
    "CREATE CONSTRAINT paper_id IF NOT EXISTS FOR (p:Paper) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT author_id IF NOT EXISTS FOR (a:Author) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE",
    "CREATE CONSTRAINT keyword_id IF NOT EXISTS FOR (k:Keyword) REQUIRE k.id IS UNIQUE",
    "CREATE CONSTRAINT venue_id IF NOT EXISTS FOR (v:Venue) REQUIRE v.id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT gap_id IF NOT EXISTS FOR (g:Gap) REQUIRE g.id IS UNIQUE",
    "CREATE CONSTRAINT direction_id IF NOT EXISTS FOR (d:Direction) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (c:Claim) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE",
    """
    CREATE VECTOR INDEX paper_embedding IF NOT EXISTS
    FOR (p:Paper) ON (p.embedding)
    OPTIONS {indexConfig: {
      `vector.dimensions`: 768,
      `vector.similarity_function`: 'cosine'
    }}
    """,
]

VECTOR_SET = """
MATCH (p:Paper {id: $id})
SET p.embedding = vector($embedding, 768, FLOAT32)
"""

LIST_SET = """
MATCH (p:Paper {id: $id})
SET p.embedding = $embedding
"""


class Graph:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.available = False
        self._driver = None
        self._vector_mode = "unknown"

    def connect(self) -> None:
        try:
            self._driver = GraphDatabase.driver(
                self.settings.neo4j_uri,
                auth=(self.settings.neo4j_user, self.settings.neo4j_password),
                connection_timeout=2,
                # Drop sockets left over from a database restart before reuse.
                max_connection_lifetime=30,
                liveness_check_timeout=0,
            )
            self._driver.verify_connectivity()
            self.available = True
        except Exception as exc:
            self.available = False
            log.warning("Neo4j unavailable: %s", exc)
            if self._driver is not None:
                self._driver.close()
                self._driver = None

    def ensure_schema(self) -> None:
        if not self.available or self._driver is None:
            return
        with self.session() as session:
            for statement in SCHEMA:
                try:
                    session.run(statement).consume()
                except Neo4jError as exc:
                    log.warning("Schema statement skipped: %s", exc)

    @contextmanager
    def session(self):
        if self._driver is None:
            raise RuntimeError("Neo4j is not connected. Start it with docker compose up -d")
        with self._driver.session() as session:
            yield session

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def set_embedding(self, paper_id: str, values: list[float]) -> None:
        if len(values) != 768:
            raise ValueError("Paper embeddings must be 768 floats")
        if self._vector_mode != "list":
            try:
                with self.session() as session:
                    session.run(VECTOR_SET, id=paper_id, embedding=values).consume()
                self._vector_mode = "vector"
                return
            except (Neo4jError, ServiceUnavailable) as exc:
                log.info("Native VECTOR property unavailable, storing a list: %s", exc)
                self._vector_mode = "list"
        with self.session() as session:
            session.run(LIST_SET, id=paper_id, embedding=values).consume()

    def get_embedding(self, paper_id: str) -> list[float] | None:
        query = "MATCH (p:Paper {id: $id}) RETURN p.embedding AS embedding"
        with self.session() as session:
            record = session.run(query, id=paper_id).single()
        if record is None or record["embedding"] is None:
            return None
        return [float(value) for value in record["embedding"]]
