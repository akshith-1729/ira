import httpx

from ingestion.openalex import (
    OpenAlex,
    WorkNotFound,
    reconstruct_abstract,
    reference_ids,
    related_ids,
    to_record,
    work_url,
)


def test_abstract_keeps_word_order():
    text = reconstruct_abstract({"a": [0, 2], "b": [1]})
    assert text == "a b a"


def test_work_url_is_a_single_record_lookup():
    assert work_url("W123") == "https://api.openalex.org/works/W123"
    assert work_url("10.1000/xyz") == "https://api.openalex.org/works/doi:10.1000%2Fxyz"
    assert "search" not in work_url("W123")
    with pytest_raises():
        work_url("?search=bert")


def pytest_raises():
    import pytest

    return pytest.raises(ValueError)


def test_reference_ids_come_from_referenced_works_only():
    work = {"referenced_works": ["https://openalex.org/W2", "https://openalex.org/W3"]}
    assert reference_ids(work) == ["W2", "W3"]


def test_related_ids_are_work_ids():
    work = {"related_works": ["https://openalex.org/W9", "https://openalex.org/W8"]}
    assert related_ids(work) == ["W9", "W8"]


def test_get_work_never_calls_search():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        assert "search" not in str(request.url)
        assert request.url.path == "/works/W100"
        return httpx.Response(
            200,
            json={
                "id": "https://openalex.org/W100",
                "display_name": "Citation Graphs",
                "publication_year": 2021,
                "authorships": [
                    {"author": {"id": "https://openalex.org/A9", "display_name": "Grace Hopper"}}
                ],
                "abstract_inverted_index": {"Citation": [0], "graphs": [1]},
                "topics": [{"id": "https://openalex.org/T7", "display_name": "Bibliometrics"}],
                "keywords": [{"display_name": "citations"}],
                "primary_location": {
                    "source": {
                        "id": "https://openalex.org/S3",
                        "display_name": "JCDL",
                        "type": "conference",
                    }
                },
                "referenced_works": ["https://openalex.org/W101"],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    record = to_record(OpenAlex("test-key", client=client).get_work("W100"))
    assert record["title"] == "Citation Graphs"
    assert record["year"] == 2021
    assert record["authors"][0]["name"] == "Grace Hopper"
    assert record["abstract"] == "Citation graphs"
    assert seen and all("/works/W100" in url for url in seen)


def _title_response(display_name: str) -> dict:
    return {
        "results": [
            {
                "id": "https://openalex.org/W77",
                "display_name": display_name,
                "publication_year": 2017,
                "topics": [{"id": "https://openalex.org/T5", "display_name": "Transformers"}],
            }
        ]
    }


def test_title_lookup_accepts_a_close_match():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        return httpx.Response(200, json=_title_response("Attention Is All You Need"))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    work = OpenAlex("test-key", client=client).find_by_title("Attention is all you need")
    assert work is not None
    assert to_record(work)["topics"][0]["name"] == "Transformers"
    assert seen[0]["filter"] == "title.search:Attention is all you need"


def test_title_lookup_rejects_a_different_paper():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_title_response("A survey of graph neural networks"))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert OpenAlex("test-key", client=client).find_by_title("Attention is all you need") is None


def test_title_lookup_strips_filter_separators():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        return httpx.Response(200, json={"results": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    OpenAlex("test-key", client=client).find_by_title("BERT: Pre-training, of deep transformers")
    assert "," not in seen[0]["filter"]
    assert ":" not in seen[0]["filter"].removeprefix("title.search:")


def test_walk_follows_referenced_work_ids():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "search" not in str(request.url)
        wid = request.url.path.rsplit("/", 1)[-1]
        assert wid in {"W1", "W2"}
        refs = ["https://openalex.org/W2"] if wid == "W1" else []
        return httpx.Response(
            200,
            json={
                "id": f"https://openalex.org/{wid}",
                "display_name": wid,
                "publication_year": 2020,
                "referenced_works": refs,
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    api = OpenAlex("test-key", client=client)
    seed = api.get_work("W1")
    cited = api.walk_references(seed, limit=25)
    assert [item["display_name"] for item in cited] == ["W2"]


def test_walk_skips_a_missing_reference():
    def handler(request: httpx.Request) -> httpx.Response:
        wid = request.url.path.rsplit("/", 1)[-1]
        if wid == "W404":
            return httpx.Response(404, json={"error": "not found"})
        return httpx.Response(
            200,
            json={"id": f"https://openalex.org/{wid}", "display_name": wid, "referenced_works": []},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    api = OpenAlex("test-key", client=client)
    cited = api.walk_references(
        {"referenced_works": ["https://openalex.org/W404", "https://openalex.org/W2"]},
        limit=25,
    )
    assert [item["display_name"] for item in cited] == ["W2"]


def test_missing_seed_is_a_work_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        OpenAlex("test-key", client=client).get_work("W9")
    except WorkNotFound as exc:
        assert exc.work_id == "W9"
        assert "api_key" not in str(exc)
    else:
        raise AssertionError("expected WorkNotFound")
