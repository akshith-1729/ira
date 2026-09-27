from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        extra="ignore",
    )

    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "research-dev"
    postgres_dsn: str = "postgresql://research:research-dev@127.0.0.1:5432/research"
    grobid_url: str = "http://127.0.0.1:8070"

    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"
    groq_fast_model: str = "openai/gpt-oss-20b"

    cerebras_api_key: str = ""
    cerebras_base_url: str = "https://api.cerebras.ai/v1"
    cerebras_model: str = "gpt-oss-120b"

    openalex_api_key: str = ""
    openalex_mailto: str = ""
    citation_walk_limit: int = 25
    # Uploaded preprints cite by title, and a reference with no OpenAlex record has no topics,
    # which leaves gap analysis empty. This is the only metered OpenAlex call; set it false to
    # stay on free single-record lookups only.
    openalex_title_search: bool = True
    # SPECTER2 stays on disk. Search and similar-papers use the graph, not this vector.
    embed_on_ingest: bool = False
    local_user_id: str = "local"
    data_dir: Path = ROOT / "data"


@lru_cache
def get_settings() -> Settings:
    return Settings()
