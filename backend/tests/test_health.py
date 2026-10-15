from fastapi.testclient import TestClient

from api.main import app
from api.routes import _search_brief


def test_health_responds():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert "neo4j" in body and "postgres" in body


def test_search_brief_skips_groq_when_nothing_was_retrieved():
    class Boom:
        def narrate_search(self, *args, **kwargs):
            raise AssertionError("Groq should not run on an empty retrieve")

    brief, rows = _search_brief(Boom(), "lsajgkjasbg", {}, [], [])
    assert brief == ""
    assert rows == []


def test_lookup_rejects_keyword_search_before_a_job():
    with TestClient(app) as client:
        response = client.post("/papers/lookup", json={"openalex_id": "?search=bert"})
    assert response.status_code == 400
