import hmac
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

ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique ON users (email);
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS email_codes (
  user_id TEXT PRIMARY KEY REFERENCES users(id),
  code_hash TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS library (
  user_id TEXT NOT NULL REFERENCES users(id),
  paper_id TEXT NOT NULL,
  title TEXT NOT NULL,
  year INT,
  private BOOLEAN NOT NULL DEFAULT false,
  added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, paper_id)
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
                already = conn.execute(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'users'
                      AND column_name = 'email_verified_at'
                    """
                ).fetchone()
                conn.execute(SCHEMA)
                if not already:
                    conn.execute(
                        """
                        UPDATE users
                        SET email_verified_at = created_at
                        WHERE email IS NOT NULL AND email_verified_at IS NULL
                        """
                    )
                conn.execute(
                    "INSERT INTO users (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
                    (self.settings.local_user_id,),
                )
                conn.commit()
            self.available = True
        except Exception as exc:
            self.available = False
            log.warning("Postgres unavailable: %s", exc)

    def create_user(self, email: str, password_hash: str) -> dict:
        user_id = str(uuid4())
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO users (id, email, password_hash)
                    VALUES (%s, %s, %s)
                    """,
                    (user_id, email, password_hash),
                )
                conn.commit()
        except Exception as exc:
            if getattr(exc, "sqlstate", None) == "23505" or "unique" in str(exc).lower():
                raise ValueError("email taken") from exc
            raise
        return {"id": user_id, "email": email}

    def user_by_email(self, email: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, email, password_hash, display_name, email_verified_at, created_at
                FROM users WHERE email = %s
                """,
                (email,),
            ).fetchone()
        return dict(row) if row else None

    def create_session(self, user_id: str, token_hash: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (token_hash, user_id, expires_at)
                VALUES (%s, %s, now() + interval '14 days')
                """,
                (token_hash, user_id),
            )
            conn.commit()

    def user_for_session(self, token_hash: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT u.id, u.email, u.display_name, u.email_verified_at, u.created_at
                FROM sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = %s AND s.expires_at > now()
                """,
                (token_hash,),
            ).fetchone()
        return dict(row) if row else None

    def save_email_code(self, user_id: str, code_hash: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO email_codes (user_id, code_hash, expires_at)
                VALUES (%s, %s, now() + interval '15 minutes')
                ON CONFLICT (user_id) DO UPDATE
                SET code_hash = EXCLUDED.code_hash,
                    expires_at = EXCLUDED.expires_at,
                    created_at = now()
                """,
                (user_id, code_hash),
            )
            conn.commit()

    def email_code_matches(self, user_id: str, code_hash: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT code_hash FROM email_codes
                WHERE user_id = %s AND expires_at > now()
                """,
                (user_id,),
            ).fetchone()
        if row is None:
            return False
        return hmac.compare_digest(row["code_hash"], code_hash)

    def mark_email_verified(self, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET email_verified_at = now() WHERE id = %s",
                (user_id,),
            )
            conn.execute("DELETE FROM email_codes WHERE user_id = %s", (user_id,))
            conn.commit()

    def set_display_name(self, user_id: str, name: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET display_name = %s WHERE id = %s",
                (name, user_id),
            )
            conn.commit()

    def set_password_hash(self, user_id: str, password_hash: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (password_hash, user_id),
            )
            conn.commit()

    def account_counts(self, user_id: str) -> dict:
        with self._connect() as conn:
            papers = conn.execute(
                "SELECT count(*) AS n FROM library WHERE user_id = %s",
                (user_id,),
            ).fetchone()["n"]
            analyses = conn.execute(
                "SELECT count(*) AS n FROM jobs WHERE user_id = %s",
                (user_id,),
            ).fetchone()["n"]
        return {"papers": papers, "analyses": analyses}

    def delete_session(self, token_hash: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = %s", (token_hash,))
            conn.commit()

    def add_to_library(
        self,
        user_id: str,
        paper_id: str,
        *,
        title: str,
        year: int | None,
        private: bool,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO library (user_id, paper_id, title, year, private)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id, paper_id) DO UPDATE
                SET title = EXCLUDED.title,
                    year = EXCLUDED.year,
                    private = EXCLUDED.private
                """,
                (user_id, paper_id, title or paper_id, year, private),
            )
            conn.commit()

    def library_for(self, user_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT paper_id, title, year, private, added_at
                FROM library
                WHERE user_id = %s
                ORDER BY added_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def library_row(self, user_id: str, paper_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT paper_id, title, year, private
                FROM library
                WHERE user_id = %s AND paper_id = %s
                """,
                (user_id, paper_id),
            ).fetchone()
        return dict(row) if row else None

    def remove_library(self, user_id: str, paper_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM library WHERE user_id = %s AND paper_id = %s",
                (user_id, paper_id),
            )
            conn.commit()
            return cursor.rowcount == 1

    def jobs_for(self, user_id: str, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, kind, status, progress, paper_id, error, created_at
                FROM jobs
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_job(self, kind: str, user_id: str | None = None) -> str:
        job_id = str(uuid4())
        owner = user_id or self.settings.local_user_id
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, user_id, kind, status, progress)
                VALUES (%s, %s, %s, 'queued', 'queued')
                """,
                (job_id, owner, kind),
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
                "SELECT id, status, progress, paper_id, error, user_id FROM jobs WHERE id = %s",
                (job_id,),
            ).fetchone()
        return dict(row) if row else None

    def log_feedback(self, kind: str, query: str, retrieved_set, output, user_id: str | None = None) -> str:
        feedback_id = str(uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO feedback (id, user_id, kind, query, retrieved_set, output)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    feedback_id,
                    user_id or self.settings.local_user_id,
                    kind,
                    query,
                    Json(retrieved_set),
                    Json(output),
                ),
            )
            conn.commit()
        return feedback_id

    def set_rating(self, feedback_id: str, rating: int, user_id: str | None = None) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE feedback SET rating = %s WHERE id = %s AND user_id = %s",
                (rating, feedback_id, user_id or self.settings.local_user_id),
            )
            conn.commit()
            return cursor.rowcount == 1
