from unittest.mock import MagicMock

from graph.gaps import GAP_DIFF_CYPHER, bind_gaps, gap_diff
from graph.search import (
    SEARCH_CYPHER,
    SIMILAR_CYPHER,
    bind_search_brief,
    catalog_query,
    intent_terms,
    merge_intent,
    query_terms,
    record_matches_terms,
    search_papers,
    similar_papers,
)


def test_gap_diff_is_one_cypher_query():
    session = MagicMock()
    session.run.return_value = [
        {
            "topic_id": "T1",
            "topic_name": "Graph neural nets",
            "papers": [{"id": "W2", "title": "Neighbor"}],
        }
    ]
    rows = gap_diff(session, "W1")
    assert session.run.call_count == 1
    query = session.run.call_args.args[0]
    assert query == GAP_DIFF_CYPHER
    assert "NOT (seed)-[:RELATED_TO]->(topic)" in query
    assert "(seed:Paper {id: $id})-[:RELATED_TO]->(:Topic)" in query
    assert "CITES" in query
    assert session.run.call_args.kwargs["generic"]
    assert rows[0]["topic_id"] == "T1"


def test_gap_diff_filters_uncorroborated_topics_in_cypher():
    session = MagicMock()
    session.run.return_value = []
    gap_diff(session, "W1", min_neighbors=2)
    assert session.run.call_args.kwargs["min_neighbors"] == 2
    # The threshold is applied in the query, not by filtering rows in Python.
    assert "size(papers) >= $min_neighbors" in GAP_DIFF_CYPHER


def test_bind_gaps_drops_topics_the_query_did_not_return():
    diff = [
        {
            "topic_id": "T1",
            "topic_name": "Graph neural nets",
            "papers": [{"id": "W2", "title": "Neighbor"}],
        }
    ]
    narrative = {
        "gaps": [
            {
                "topic_id": "T1",
                "statement": "Neighbors cover graph neural nets.",
                "direction": "Test that setting.",
                "claims": [{"text": "Neighbor studies them.", "paper_ids": ["W2", "W999"]}],
            },
            {
                "topic_id": "INVENTED",
                "statement": "The model made this up.",
                "direction": "Ignore.",
                "claims": [],
            },
        ]
    }
    bound = bind_gaps(diff, narrative, "W1")
    assert [gap["topic_id"] for gap in bound] == ["T1"]
    chunk_ids = [chunk["id"] for chunk in bound[0]["claims"][0]["chunks"]]
    assert chunk_ids == ["W2:abstract"]


def test_empty_narration_still_materializes_the_cypher_diff():
    diff = [{"topic_id": "T9", "topic_name": "Uncertainty", "papers": [{"id": "W8", "title": "U"}]}]
    bound = bind_gaps(diff, {"gaps": []}, "W1")
    assert bound[0]["topic_id"] == "T9"
    assert "Uncertainty" in bound[0]["statement"]
    assert bound[0]["claims"][0]["chunks"][0]["id"] == "W8:abstract"


def test_search_terms_drop_filler_and_expand_cybersecurity():
    assert "project" not in query_terms("A project based on modern flaws in cybersecurity")
    assert "technology" not in query_terms("new flaws in web 3.0 technology")
    assert "web3" in query_terms("new flaws in web 3.0 technology")
    assert catalog_query("new flaws in web 3.0 technology") == "web 3.0"
    assert "cybersecurity" in query_terms("A project based on modern flaws in cybersecurity")
    assert "security" in query_terms("A project based on modern flaws in cybersecurity")


def test_catalog_keeps_web3_and_drops_unrelated_titles():
    terms = query_terms("new flaws in web 3.0 technology")
    assert record_matches_terms({"title": "Web 3.0 and medicine", "abstract": "", "topics": []}, terms)
    assert not record_matches_terms(
        {"title": "Blood Cells Counting using Python OpenCV", "abstract": "", "topics": []},
        terms,
    )


def test_merge_intent_keeps_field_phrases_not_filler():
    intent = merge_intent(
        "new flaws in web 3.0 technology",
        {
            "field": "Web 3.0 security",
            "intent": "What security flaws are documented in Web 3.0 systems?",
            "topics": ["Web 3.0", "smart contract security", "technology"],
            "methods": ["literature review", "static analysis"],
            "must_match": ["web 3.0", "web3"],
            "catalog_query": "web 3.0 security vulnerabilities",
        },
    )
    assert "technology" not in [name.lower() for name in intent["topics"]]
    assert "Web 3.0" in intent["topics"]
    assert intent["catalog_query"] == "web 3.0 security vulnerabilities"
    terms = intent_terms(intent, "new flaws in web 3.0 technology")
    assert "web3" in terms or "web 3.0" in terms
    assert "security" not in terms
    assert "literature review" not in terms


def test_bind_search_brief_attaches_why_and_drops_invented_ids():
    rows = [
        {"paper": {"id": "W1", "title": "Web 3.0 Emerging"}, "source": "openalex"},
        {"paper": {"id": "W2", "title": "Web 3.0 and medicine"}, "source": "openalex"},
    ]
    brief, bound = bind_search_brief(
        rows,
        {
            "brief": "The set defines Web 3.0 more than it measures new flaws.",
            "hits": [
                {"id": "W1", "relevant": True, "why": "Defines emerging Web 3.0 stacks."},
                {"id": "W2", "relevant": False, "why": "Applies Web 3.0 to medicine, not protocol flaws."},
                {"id": "W999", "relevant": True, "why": "Invented."},
            ],
        },
    )
    assert "defines Web 3.0" in brief
    assert [row["paper"]["id"] for row in bound] == ["W1", "W2"]
    assert bound[0]["why"].startswith("Defines")
    assert "medicine" in bound[1]["why"]


def test_search_is_a_single_cypher_call():
    session = MagicMock()
    session.run.return_value = [
        {
            "id": "W2",
            "title": "Other",
            "year": 2020,
            "summary": None,
            "topics": ["graphs"],
            "keywords": [],
            "concepts": [],
            "score": 3,
        }
    ]
    rows = search_papers(session, terms=["graphs"], topic="graphs", owner="local", limit=5)
    assert session.run.call_count == 1
    query = session.run.call_args.args[0]
    assert query == SEARCH_CYPHER
    assert "db.index.vector.queryNodes" not in query
    assert "RELATED_TO" in query
    assert "CONTAINS" in query
    assert rows[0]["paper"]["id"] == "W2"
    assert rows[0]["reasons"] == ["graphs"]


def test_similar_papers_require_a_graph_path():
    session = MagicMock()
    session.run.return_value = [
        {
            "id": "W3",
            "title": "Intrusion survey",
            "year": 2018,
            "summary": None,
            "topics": ["Network Security and Intrusion Detection"],
            "concepts": [],
            "cited": True,
            "two_hop": False,
            "score": 4,
        }
    ]
    rows = similar_papers(session, "W1", owner="local", limit=8)
    assert session.run.call_count == 1
    query = session.run.call_args.args[0]
    assert query == SIMILAR_CYPHER
    assert "RELATED_TO" in query
    assert "DISCUSSES" in query
    assert "CITES" in query
    assert "db.index.vector.queryNodes" not in query
    assert rows[0]["paper"]["id"] == "W3"
    assert "Network Security and Intrusion Detection" in rows[0]["reasons"]
