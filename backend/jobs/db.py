import logging
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Json

from config import Settings

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  progress TEXT NOT NULL,
  paper_id TEXT,
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS feedback (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  kind TEXT NOT NULL,
  query TEXT NOT NULL,
  retrieved_set JSONB NOT NULL,
  output JSONB NOT NULL,
  rating SMALLINT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.available = False

    def _connect(self):
        import psycopg

        return psycopg.connect(
            self.settings.postgres_dsn,
            row_factory=dict_row,
            connect_timeout=2,
        )

    def ensure_schema(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute(SCHEMA)
                conn.execute(
                    "INSERT INTO users (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
                    (self.settings.local_user_id,),
                )
                conn.commit()
            self.available = True
        except Exception as exc:
            self.available = False
            log.warning("Postgres unavailable: %s", exc)

    def create_job(self, kind: str) -> str:
        job_id = str(uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, user_id, kind, status, progress)
                VALUES (%s, %s, %s, 'queued', 'queued')
                """,
                (job_id, self.settings.local_user_id, kind),
            )
            conn.commit()
        return job_id

    def update_job(
        self,
        job_id: str,
        status: str,
        progress: str,
        *,
        paper_id: str | None = None,
        error: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = %s,
                    progress = %s,
                    paper_id = COALESCE(%s, paper_id),
                    error = %s,
                    updated_at = now()
                WHERE id = %s
                """,
                (status, progress, paper_id, error, job_id),
            )
            conn.commit()

    def get_job(self, job_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, status, progress, paper_id, error FROM jobs WHERE id = %s",
                (job_id,),
            ).fetchone()
        return dict(row) if row else None

    def log_feedback(self, kind: str, query: str, retrieved_set, output) -> str:
        feedback_id = str(uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO feedback (id, user_id, kind, query, retrieved_set, output)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    feedback_id,
                    self.settings.local_user_id,
                    kind,
                    query,
                    Json(retrieved_set),
                    Json(output),
                ),
            )
            conn.commit()
        return feedback_id

    def set_rating(self, feedback_id: str, rating: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE feedback SET rating = %s WHERE id = %s AND user_id = %s",
                (rating, feedback_id, self.settings.local_user_id),
            )
            conn.commit()
            return cursor.rowcount == 1
