import csv
from io import StringIO
from pathlib import Path

import pytest

from venues.cache import PAID_VENUE_APIS, VENUE_LOOKUP_CACHE
from venues.catalog import (
    ADVICE_NOTES,
    CATALOG_PATH,
    MATCH_NOTES,
    VENUE_FIELDS,
    build_venue_advice,
    clear_catalog_cache,
    load_catalog,
    placeholder_fit,
)


ADVICE_KEYS = {"paper_id", "venues", "shortlist", "feasibility", "gaps", "notes"}


def test_catalog_is_a_curated_public_snapshot():
    rows = load_catalog()
    assert 20 <= len(rows) <= 40
    ids = [row["id"] for row in rows]
    assert len(ids) == len(set(ids))
    for row in rows:
        assert tuple(row) == VENUE_FIELDS
        assert row["kind"] in {"journal", "conference", "repository"}
        assert row["tier"] in {"top", "strong", "specialist"}
        assert row["fields"]
        assert row["homepage"].startswith(("http://", "https://"))
        assert row["scopus"] in {"yes", "no", "unknown"}
        assert row["open_access"] in {"yes", "no", "unknown"}
        assert row["fit"] == placeholder_fit()
        if row["acceptance_rate"] is not None:
            assert 0 <= row["acceptance_rate"] <= 1
            assert row["acceptance_year"]
            assert row["acceptance_source"]
        if row["sjr_quartile"]:
            assert row["sjr_quartile"] in {"Q1", "Q2", "Q3", "Q4"}
        if row["id"] == "arxiv":
            assert row["scopus"] == "no"
            assert row["kind"] == "repository"


def test_empty_public_stats_stay_none():
    raw = CATALOG_PATH.read_text(encoding="utf-8")
    reader = csv.DictReader(StringIO(raw))
    blanks = next(row for row in reader if not (row.get("acceptance_rate") or "").strip())
    loaded = next(row for row in load_catalog() if row["id"] == blanks["id"])
    assert loaded["acceptance_rate"] is None
    assert loaded["acceptance_year"] is None
    assert loaded.get("acceptance_source") in {None, blanks.get("acceptance_source") or None}


def test_catalog_rejects_invented_acceptance_fractions(tmp_path: Path):
    path = tmp_path / "venues.csv"
    path.write_text(
        "id,name,kind,tier,fields,sjr,sjr_quartile,avg_review_days,acceptance_rate,acceptance_year,acceptance_source,homepage,publisher,scopus,open_access\n"
        "bad,Bad Venue,journal,top,ml,,,,1.4,2024,made up,https://example.com,X,unknown,unknown\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Acceptance rate"):
        load_catalog(path)


def test_venue_advice_contract_uses_placeholders_without_a_paper():
    advice = build_venue_advice()
    assert set(advice) == ADVICE_KEYS
    assert advice["paper_id"] is None
    assert advice["shortlist"] == []
    assert advice["feasibility"] is None
    assert advice["gaps"] is None
    assert advice["notes"] == list(ADVICE_NOTES)
    assert all(row["fit"]["method"] == "placeholder" for row in advice["venues"])
    assert all(row["fit"]["score"] is None for row in advice["venues"])


def _ids(advice: dict, n: int = 6) -> list[str]:
    return [row["id"] for row in advice["venues"][:n]]


def test_transformer_paper_fits_ml_and_nlp_venues():
    paper = {
        "id": "W-attn",
        "title": "Attention Is All You Need",
        "abstract": "We propose the Transformer, a model architecture based solely on attention mechanisms for machine translation.",
        "topics": [
            {"id": "T1", "name": "Natural Language Processing Techniques"},
            {"id": "T2", "name": "Multimodal Machine Learning Applications"},
        ],
        "keywords": ["Transformer", "Machine learning", "Language model", "Machine translation"],
    }
    advice = build_venue_advice(paper)
    assert advice["paper_id"] == "W-attn"
    assert advice["notes"] == list(MATCH_NOTES)
    assert advice["feasibility"]["method"] == "topic_tier_quality"
    assert advice["feasibility"]["venue_id"] in {
        "neurips",
        "icml",
        "iclr",
        "acl",
        "emnlp",
        "jmlr",
        "tmlr",
        "tacl",
        "naacl",
    }
    assert len(advice["shortlist"]) == 5
    assert advice["shortlist"] == advice["venues"][:5]
    assert {"neurips", "icml", "iclr", "acl", "emnlp", "jmlr", "tmlr", "tacl", "naacl"} & {
        row["id"] for row in advice["shortlist"]
    }
    assert all(row["fit"]["method"] == "topic_embedding" for row in advice["venues"])
    assert all(0 <= row["fit"]["score"] <= 1 for row in advice["venues"])
    top = set(_ids(advice, 8))
    assert {"neurips", "icml", "iclr", "acl", "emnlp"} & top
    assert _ids(advice, 1)[0] in {"neurips", "icml", "iclr", "acl", "emnlp", "jmlr", "tmlr", "tacl", "naacl"}
    bottom = {row["id"] for row in advice["venues"][-6:]}
    assert {"ieee-sp", "usenix-sec", "chi", "vldb"} & bottom


def test_vision_paper_fits_cv_venues():
    paper = {
        "id": "W-cv",
        "title": "Mask R-CNN",
        "abstract": "We present a framework for object detection and instance image segmentation.",
        "topics": [{"id": "T1", "name": "Computer vision"}],
        "keywords": ["object detection", "convolutional"],
    }
    top = set(_ids(build_venue_advice(paper), 5))
    assert {"cvpr", "iccv", "eccv", "tpami"} & top
    assert "acl" not in top


def test_security_paper_fits_security_venues():
    paper = {
        "id": "W-sec",
        "title": "Spectre Attacks: Exploiting Speculative Execution",
        "abstract": "We demonstrate a side channel vulnerability that leaks memory through speculative execution.",
        "topics": [{"id": "T1", "name": "Computer security"}],
        "keywords": ["side channel", "vulnerability"],
    }
    top = set(_ids(build_venue_advice(paper), 5))
    assert {"ieee-sp", "usenix-sec", "ccs", "ndss"} & top
    assert "chi" not in top


def test_advice_venues_route_returns_the_same_contract():
    from api.routes import venue_advice

    body = venue_advice()
    assert set(body) == ADVICE_KEYS
    assert body["paper_id"] is None
    assert body["venues"] == load_catalog()
    assert body["shortlist"] == []
    assert body["feasibility"] is None
    assert body["gaps"] is None


def test_advice_venues_http_contract():
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as client:
        response = client.get("/advice/venues")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == ADVICE_KEYS
    assert body["shortlist"] == []
    assert body["feasibility"] is None
    assert body["gaps"] is None
    assert len(body["venues"]) == len(load_catalog())
    assert all(row["fit"]["method"] == "placeholder" for row in body["venues"])


def test_catalog_lookups_are_cached():
    clear_catalog_cache()
    first = load_catalog()
    key = f"catalog:{CATALOG_PATH.resolve()}"
    assert key in VENUE_LOOKUP_CACHE
    second = load_catalog()
    assert first == second
    assert first is not second


def test_paid_venue_apis_are_flagged_not_implemented():
    assert PAID_VENUE_APIS == ("clarivate-jcr", "scopus", "web-of-science")
    assert "live" in " ".join(ADVICE_NOTES).lower()
    assert "live" in " ".join(MATCH_NOTES).lower()


def test_advice_contract_includes_known_gaps():
    paper = {
        "id": "gap-results",
        "title": "Legal-RAG: a planned retrieval pipeline",
        "abstract": (
            "We propose a retrieval-augmented generation workflow for case law. "
            "Numerical performance results are left to future work."
        ),
        "paper_type": "proposal",
        "demonstrated": "nothing was shown",
    }
    advice = build_venue_advice(paper)
    assert {gap["kind"] for gap in advice["gaps"]} == {"results"}
    assert advice["feasibility"]["method"] == "topic_tier_quality"


def _ml_paper(**extra) -> dict:
    paper = {
        "id": "W-ml",
        "title": "Attention Is All You Need",
        "abstract": "We propose the Transformer for machine translation.",
        "topics": [{"id": "T1", "name": "Natural Language Processing Techniques"}],
        "keywords": ["Transformer", "Machine learning"],
    }
    paper.update(extra)
    return paper


def test_empirical_paper_is_more_ready_than_an_untested_proposal():
    from venues.feasibility import quality_signal

    strong = _ml_paper(
        paper_type="empirical",
        demonstrated="BLEU improved 2.0 on WMT 2014 English-German.",
        contributions=[{"text": "scaled dot-product attention", "status": "demonstrated"}],
    )
    weak = _ml_paper(
        paper_type="proposal",
        demonstrated="nothing was shown",
        gaps=[{"source": "evidence", "statement": "no scores"}],
    )
    strong_q, _ = quality_signal(strong)
    weak_q, _ = quality_signal(weak)
    assert strong_q > weak_q
    strong_ready = build_venue_advice(strong)
    weak_ready = build_venue_advice(weak)
    assert strong_ready["feasibility"]["score"] > weak_ready["feasibility"]["score"]
    assert strong_ready["feasibility"]["signals"]["quality"] > weak_ready["feasibility"]["signals"]["quality"]


def test_same_paper_is_more_ready_for_a_specialist_venue_than_a_top_one():
    paper = _ml_paper(paper_type="proposal", demonstrated="nothing was shown")
    advice = build_venue_advice(paper)
    by_id = {row["id"]: row for row in advice["venues"]}
    assert by_id["arxiv"]["readiness"] > by_id["nature"]["readiness"]
    assert by_id["tmlr"]["readiness"] > by_id["neurips"]["readiness"]


def test_readiness_uses_only_upstream_quality_fields():
    from venues.feasibility import quality_signal

    score, reasons = quality_signal(
        {
            "paper_type": "empirical",
            "demonstrated": "Accuracy 91.4 on ImageNet.",
            "contributions": [{"status": "demonstrated"}],
            "gaps": [{"source": "evidence"}],
        }
    )
    assert 0 < score < 1
    assert "paper_type=empirical" in reasons
    assert "upstream evidence gap" in reasons
    assert "demonstrated result recorded" in reasons
