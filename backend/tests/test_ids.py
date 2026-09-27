import pytest

from ingestion.ids import classify_id


def test_openalex_doi_and_arxiv_ids():
    assert classify_id("W2741809807") == ("openalex", "W2741809807")
    assert classify_id("https://openalex.org/W2741809807") == ("openalex", "W2741809807")
    assert classify_id("10.7717/peerj.4375") == ("doi", "10.7717/peerj.4375")
    assert classify_id("https://doi.org/10.7717/peerj.4375") == ("doi", "10.7717/peerj.4375")
    assert classify_id("1706.03762") == ("arxiv", "1706.03762")


def test_keyword_search_is_rejected():
    with pytest.raises(ValueError):
        classify_id("?search=transformers")
    with pytest.raises(ValueError):
        classify_id("https://api.openalex.org/works?search=bert")
