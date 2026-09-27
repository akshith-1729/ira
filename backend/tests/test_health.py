from fastapi.testclient import TestClient

from api.main import app


def test_health_responds():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert "neo4j" in body and "postgres" in body


def test_lookup_rejects_keyword_search_before_a_job():
    with TestClient(app) as client:
        response = client.post("/papers/lookup", json={"openalex_id": "?search=bert"})
    assert response.status_code == 400
