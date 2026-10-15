from uuid import uuid4

from fastapi.testclient import TestClient

from api.main import app
from auth import email_problem, hash_password, verify_password


def test_password_hash_round_trip():
    stored = hash_password("correct-horse")
    assert stored.startswith("scrypt$")
    assert verify_password("correct-horse", stored)
    assert not verify_password("wrong-horse", stored)
    assert not verify_password("correct-horse", "not-a-hash")


def test_upload_and_lookup_require_a_session():
    with TestClient(app) as client:
        upload = client.post(
            "/papers/upload",
            files={"file": ("note.pdf", b"%PDF-1.4\n", "application/pdf")},
        )
        lookup = client.post("/papers/lookup", json={"openalex_id": "W2741809807"})
        nonsense = client.post("/papers/lookup", json={"openalex_id": "?search=bert"})
    assert upload.status_code == 401
    assert lookup.status_code == 401
    assert nonsense.status_code == 400


def test_email_shape_rejects_incomplete_addresses():
    assert email_problem("a@b.c") == "Enter a valid email."
    assert email_problem("not-an-email") == "Enter a valid email."
    assert email_problem("person@example.com") is None


def _confirm(client, email: str, registered):
    body = registered.json()
    assert body["delivery"] == "screen"
    assert len(body["code"]) == 6
    verified = client.post("/auth/verify", json={"email": email, "code": body["code"]})
    assert verified.status_code == 200, verified.text
    assert verified.json()["verified"] is True
    return verified


def test_register_login_and_a_private_shelf():
    email_a = f"ira-{uuid4().hex}@example.com"
    email_b = f"ira-{uuid4().hex}@example.com"
    password = "correct-horse"
    created = []
    private_id = f"local:auth-{uuid4().hex[:12]}"
    public_id = f"Wauth{uuid4().hex[:8]}"
    with TestClient(app) as client:
        first = client.post("/auth/register", json={"email": email_a, "password": password})
        assert first.status_code == 200, first.text
        assert first.json()["email"] == email_a
        created.append(first.json()["id"])
        assert client.get("/auth/me").status_code == 401
        blocked = client.post("/auth/login", json={"email": email_a, "password": password})
        assert blocked.status_code == 403
        wrong_code = "000000" if first.json()["code"] != "000000" else "111111"
        bad_code = client.post("/auth/verify", json={"email": email_a, "code": wrong_code})
        assert bad_code.status_code == 400
        _confirm(client, email_a, first)
        me = client.get("/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == email_a
        assert me.json()["verified"] is True
        named = client.patch("/auth/profile", json={"display_name": "Shelf User"})
        assert named.status_code == 200
        assert named.json()["display_name"] == "Shelf User"

        duplicate = client.post("/auth/register", json={"email": email_a.upper(), "password": password})
        assert duplicate.status_code == 409

        client.post("/auth/logout")
        assert client.get("/auth/me").status_code == 401
        wrong = client.post("/auth/login", json={"email": email_a, "password": "not-the-password"})
        assert wrong.status_code == 401
        assert wrong.json()["detail"] == "Email or password is wrong."
        short = client.post("/auth/register", json={"email": email_b, "password": "short"})
        assert short.status_code == 400
        unreal = client.post(
            "/auth/register",
            json={"email": "person@no-such-ira-domain.invalid", "password": password},
        )
        assert unreal.status_code == 400

        signed_in = client.post("/auth/login", json={"email": email_a, "password": password})
        assert signed_in.status_code == 200
        user_a = signed_in.json()["id"]
        database = app.state.db
        database.add_to_library(user_a, "paper-a", title="Mine", year=2020, private=False)
        jar_a = _cookies(client)

        client.cookies.clear()
        registered = client.post("/auth/register", json={"email": email_b, "password": password})
        assert registered.status_code == 200, registered.text
        user_b = registered.json()["id"]
        created.append(user_b)
        early = client.post("/auth/login", json={"email": email_b, "password": password})
        assert early.status_code == 403
        _confirm(client, email_b, registered)
        database.add_to_library(user_b, "paper-b", title="Theirs", year=2021, private=False)
        jar_b = _cookies(client)

        _restore(client, jar_a)
        shelf = client.get("/library")
        assert shelf.status_code == 200
        assert [row["paper_id"] for row in shelf.json()["papers"]] == ["paper-a"]
        assert client.delete("/library/paper-b").status_code == 404
        assert client.delete("/library/paper-a").status_code == 200
        assert client.get("/library").json()["papers"] == []

        if app.state.graph.available:
            store = app.state.store
            store.upsert_paper(
                {
                    "id": public_id,
                    "title": "Cited neighbor",
                    "year": 2019,
                    "abstract": "Stays in the library.",
                    "authors": [],
                    "topics": [],
                    "keywords": [],
                },
                private=False,
                owner=None,
            )
            store.upsert_paper(
                {
                    "id": private_id,
                    "title": "Private note",
                    "year": 2024,
                    "abstract": "Only this account.",
                    "authors": [],
                    "topics": [],
                    "keywords": [],
                },
                private=True,
                owner=user_a,
            )
            store.upsert_references(
                private_id,
                [
                    {
                        "id": public_id,
                        "title": "Cited neighbor",
                        "year": 2019,
                        "abstract": "Stays in the library.",
                        "authors": [],
                        "topics": [],
                        "keywords": [],
                    }
                ],
            )
            database.add_to_library(user_a, private_id, title="Private note", year=2024, private=True)
            database.add_to_library(user_b, private_id, title="Private note", year=2024, private=True)
            _restore(client, jar_b)
            assert client.delete(f"/library/{private_id}").status_code == 404
            _restore(client, jar_a)
            assert client.get(f"/papers/{private_id}").status_code == 200
            assert client.delete(f"/library/{private_id}").status_code == 200
            assert client.get(f"/papers/{private_id}").status_code == 404
            assert client.get(f"/papers/{public_id}").status_code == 200
        _forget(created)


def _cookies(client) -> dict:
    return {cookie.name: cookie.value for cookie in client.cookies.jar}


def _restore(client, saved: dict) -> None:
    client.cookies.clear()
    for name, value in saved.items():
        client.cookies.set(name, value)


def _forget(user_ids: list[str]) -> None:
    database = app.state.db
    if not database.available:
        return
    with database._connect() as conn:
        for user_id in user_ids:
            conn.execute("DELETE FROM email_codes WHERE user_id = %s", (user_id,))
            conn.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
            conn.execute("DELETE FROM library WHERE user_id = %s", (user_id,))
            conn.execute("DELETE FROM jobs WHERE user_id = %s", (user_id,))
            conn.execute("DELETE FROM feedback WHERE user_id = %s", (user_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
