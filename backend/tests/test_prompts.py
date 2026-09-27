from ai.prompts import build_prefix, parse_json, search_brief_task
from jobs.pipeline import ground_contributions


def test_prefix_is_stable_for_the_same_paper():
    chunks = [{"id": "P:s1", "section": "Introduction", "text": "We begin."}]
    first = build_prefix("Title", "Abstract", chunks)
    second = build_prefix("Title", "Abstract", chunks)
    assert first == second
    assert first.startswith("TITLE: Title")
    assert "[P:s1] SECTION Introduction:" in first


def test_prefix_keeps_a_whole_results_section():
    body = "We report 91.4 percent recall. " * 200
    chunks = [{"id": "P:abstract", "section": "abstract", "text": "Abstract"}]
    chunks += [
        {"id": f"P:s{i}", "section": f"Method {i}", "text": "Method text. " * 100}
        for i in range(1, 12)
    ]
    chunks.append({"id": "P:s99", "section": "V. RESULTS", "text": body})
    prefix = build_prefix("Title", "Abstract", chunks)
    # The old 8000-character budget dropped the results section entirely.
    assert "[P:s99] SECTION V. RESULTS:" in prefix
    assert "91.4 percent recall" in prefix
    # The abstract is not repeated as a section block.
    assert prefix.count("Abstract") == 1


def test_parse_json_accepts_fenced_output():
    payload = parse_json('```json\n{"summary": "Done."}\n```')
    assert payload["summary"] == "Done."


def test_contributions_attach_to_the_named_section():
    summary = {"contributions": [{"text": "A result", "section": "Results"}]}
    chunks = [
        {"id": "P:abstract", "section": "abstract", "text": "abs"},
        {"id": "P:s2", "section": "Results", "text": "numbers"},
    ]
    grounded = ground_contributions(summary, chunks, "P")
    assert grounded[0]["chunk_ids"] == ["P:s2"]


def test_contributions_ignore_grobid_section_numbering():
    summary = {"contributions": [{"text": "A result", "section": "Evaluation of Summarization"}]}
    chunks = [
        {"id": "P:abstract", "section": "abstract", "text": "abs"},
        {"id": "P:s23", "section": "C. Evaluation of Summarization", "text": "numbers"},
    ]
    grounded = ground_contributions(summary, chunks, "P")
    assert grounded[0]["chunk_ids"] == ["P:s23"]


def test_contributions_accept_a_named_chunk_id():
    summary = {"contributions": [{"text": "A result", "chunk_id": "P:s23"}]}
    chunks = [
        {"id": "P:abstract", "section": "abstract", "text": "abs"},
        {"id": "P:s23", "section": "C. Evaluation", "text": "numbers"},
    ]
    grounded = ground_contributions(summary, chunks, "P")
    assert grounded[0]["chunk_ids"] == ["P:s23"]


def test_search_brief_lists_only_retrieved_ids():
    task = search_brief_task(
        "new flaws in web 3.0 technology",
        {"field": "Web 3.0 security", "intent": "Documented Web 3.0 flaws"},
        [
            {
                "paper": {"id": "W1", "title": "Web 3.0 Emerging", "year": 2009, "summary": "Semantic web."},
                "reasons": ["Semantic Web and Ontologies"],
            }
        ],
    )
    assert "id=W1" in task
    assert "W999" not in task
    assert "new flaws in web 3.0 technology" in task


def test_unknown_chunk_id_falls_back_to_the_abstract():
    summary = {"contributions": [{"text": "A result", "chunk_id": "P:invented"}]}
    chunks = [{"id": "P:abstract", "section": "abstract", "text": "abs"}]
    grounded = ground_contributions(summary, chunks, "P")
    assert grounded[0]["chunk_ids"] == ["P:abstract"]
