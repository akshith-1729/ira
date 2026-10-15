from unittest.mock import MagicMock

from graph.gaps import GAP_DIFF_CYPHER, bind_gaps, gap_diff
from graph.papers import VENUES_FOR_TOPICS
from graph.search import (
    SEARCH_CYPHER,
    SIMILAR_CYPHER,
    bind_search_brief,
    catalog_query,
    filter_graph_hits,
    intent_terms,
    keep_relevant_rows,
    local_title_covers_query,
    looks_like_title,
    merge_intent,
    query_is_meaningful,
    query_terms,
    record_matches_terms,
    same_title,
    search_papers,
    similar_papers,
    token_in_text,
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
    assert len(catalog_query("modern flaws in cybersecurity applications and technology").split()) <= 5
    assert "cybersecurity" in query_terms("A project based on modern flaws in cybersecurity")
    assert "security" in query_terms("A project based on modern flaws in cybersecurity")


def test_catalog_keeps_web3_and_drops_unrelated_titles():
    terms = query_terms("new flaws in web 3.0 technology")
    assert record_matches_terms({"title": "Web 3.0 and medicine", "abstract": "", "topics": []}, terms)
    assert not record_matches_terms(
        {"title": "Blood Cells Counting using Python OpenCV", "abstract": "", "topics": []},
        terms,
    )


def test_attention_title_does_not_match_diabetes_or_vitamin_d():
    query = "Attention is all you need"
    assert looks_like_title(query)
    assert "need" not in query_terms(query)
    assert catalog_query(query).lower().startswith("attention is all you need")
    terms = query_terms(query)
    assert record_matches_terms({"title": "Attention Is All You Need", "abstract": "", "topics": []}, terms)
    assert not record_matches_terms(
        {
            "title": "Blood glucose levels in elderly subjects with type 2 diabetes",
            "abstract": "Patients need attention during COVID-19.",
            "topics": [],
        },
        terms,
    )
    assert not record_matches_terms(
        {"title": "Effect of vitamin D status on pharmacological treatment efficiency", "abstract": "", "topics": []},
        terms,
    )
    assert local_title_covers_query(
        [{"paper": {"id": "W1", "title": "Attention Is All You Need"}}],
        query,
    )
    assert same_title(query, "Attention Is All You Need")
    assert not same_title(query, "Attention Is All You Need In Speech Separation")
    assert not same_title(query, "Channel Attention Is All You Need for Video Frame Interpolation")


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
    assert [row["paper"]["id"] for row in bound] == ["W1"]
    assert bound[0]["why"].startswith("Defines")


def test_nonsense_query_is_rejected_before_search():
    assert not query_is_meaningful("ding doong")
    assert not query_is_meaningful("lsajgkjasbg")
    assert not query_is_meaningful("asdfghjkl")
    assert not query_is_meaningful("the the the")
    assert query_is_meaningful("Attention is all you need")
    assert query_is_meaningful("new flaws in web 3.0 technology")
    assert query_is_meaningful("BERT")
    assert query_is_meaningful("quantum computing")
    assert query_is_meaningful("artificial intelligence and its effects")
    assert query_is_meaningful("Effects of AI on Information technology")
    assert query_is_meaningful("Counting red Blood cells using opencv")


def test_topic_questions_are_not_treated_as_paper_titles():
    assert looks_like_title("Attention is all you need")
    assert not looks_like_title("artificial intelligence and its effects")
    assert not looks_like_title("Effects of AI on Information technology")
    assert "ai" in query_terms("Effects of AI on Information technology")


def test_title_query_does_not_keep_keyword_cousins_from_the_graph():
    rows = [
        {"paper": {"id": "W1", "title": "Attention Is All You Need"}},
        {"paper": {"id": "W2", "title": "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks"}},
    ]
    kept = filter_graph_hits(rows, "Attention is all you need")
    assert [row["paper"]["id"] for row in kept] == ["W1"]


def test_keep_relevant_rows_drops_titles_outside_the_field():
    rows = [
        {"paper": {"id": "W1", "title": "Web 3.0 Emerging"}, "source": "graph", "reasons": []},
        {"paper": {"id": "W2", "title": "White blood cell nucleus segmentation"}, "source": "graph", "reasons": ["imaging"]},
    ]
    kept = keep_relevant_rows(rows, ["web3", "web 3"])
    assert [row["paper"]["id"] for row in kept] == ["W1"]


def test_field_catalog_keeps_a_paper_that_carries_one_field_phrase():
    gates = ["web 3.0", "smart contracts", "blockchain"]
    assert record_matches_terms(
        {"title": "Web 3.0 Emerging", "abstract": "", "topics": []},
        gates,
        require_all=False,
    )
    assert not record_matches_terms(
        {"title": "Blood Cells Counting using Python OpenCV", "abstract": "", "topics": []},
        gates,
        require_all=False,
    )


def test_ding_does_not_match_embedding_or_finding():
    assert token_in_text("attention", "Attention Is All You Need")
    assert not token_in_text("ding", "Sentence Embeddings using Siamese BERT-Networks")
    assert not token_in_text("ding", "Why Most Published Research Findings Are False")
    session = MagicMock()
    session.run.return_value = [
        {
            "id": "W9",
            "title": "Sentence Embeddings using Siamese BERT-Networks",
            "year": 2019,
            "summary": None,
            "topics": [],
            "keywords": [],
            "concepts": [],
            "score": 2,
        }
    ]
    assert search_papers(session, terms=["ding", "doong"], topic=None, owner="local", limit=10) == []


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


def test_venues_rank_shared_topics_on_the_graph():
    session = MagicMock()
    session.run.return_value = [
        {
            "id": "S1",
            "name": "Nature",
            "kind": "journal",
            "papers": 2,
            "topic_hits": 3,
            "source_papers": ["Cited survey", "Neighbor"],
        }
    ]
    graph = MagicMock()
    graph.session.return_value.__enter__.return_value = session
    from graph.papers import PaperStore

    rows = PaperStore(graph).venues_for_topics(["T1", "Graphs"], exclude_id="W1")
    query = session.run.call_args.args[0]
    assert query == VENUES_FOR_TOPICS
    assert "PUBLISHED_IN" in query
    assert "topic_hits DESC" in query
    assert "$exclude_id" in query
    assert "acceptance" not in query.lower()
    assert session.run.call_args.kwargs["exclude_id"] == "W1"
    assert rows[0]["name"] == "Nature"
    assert rows[0]["source_papers"] == ["Cited survey", "Neighbor"]
    assert rows[0]["topic_hits"] == 3


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


def test_get_paper_does_not_walk_similar_papers_or_graph_venues():
    import inspect

    from api.routes import _paper_or_404, get_paper

    for fn in (get_paper, _paper_or_404):
        source = inspect.getsource(fn)
        assert "similar_papers" not in source
        assert "venues_for_topics" not in source
    assert "build_venue_advice" in inspect.getsource(get_paper)

    paper = {
        "id": "W-attn",
        "title": "Attention Is All You Need",
        "abstract": (
            "We propose the Transformer, a model architecture based solely on "
            "attention mechanisms for machine translation."
        ),
        "topics": [{"id": "T1", "name": "Natural Language Processing Techniques"}],
        "keywords": ["Transformer", "Machine learning", "Language model"],
        "topic_keys": ["T1", "Natural Language Processing Techniques"],
        "authors": [],
        "gaps": [],
        "contributions": ["scaled dot-product attention"],
        "citation_context": {"cited": 0, "cited_with_topics": 0},
    }
    request = MagicMock()
    request.app.state.graph.available = True
    request.app.state.store.get_paper.return_value = dict(paper)
    request.app.state.store.similar_papers = MagicMock()
    request.app.state.store.venues_for_topics = MagicMock()
    request.app.state.settings.local_user_id = "local"

    body = get_paper("W-attn", request)

    request.app.state.store.similar_papers.assert_not_called()
    request.app.state.store.venues_for_topics.assert_not_called()
    assert "topic_keys" not in body
    assert "similar_papers" not in body
    assert len(body["venue_advice"]["shortlist"]) == 5
    assert body["venue_advice"]["shortlist"] == body["venue_advice"]["venues"][:5]
