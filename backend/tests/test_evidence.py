from graph.concepts import covered_by, is_generic, keep_concepts
from graph.evidence import evidence_gaps


def test_generic_openalex_fields_are_not_concepts():
    assert is_generic("Natural Language Processing Techniques")
    assert is_generic("Computer science")
    assert is_generic("BLEU")
    assert is_generic("WMT 2014 English-to-German translation task")
    assert is_generic("literature review")
    assert is_generic("empirical study")
    assert not is_generic("TransE")


def test_sentence_transformers_covers_transformer():
    assert covered_by({"Sentence-Transformers"}, "Transformer")
    assert covered_by({"Sentence Transformers"}, "Sentence-BERT")
    assert covered_by({"Sentence Transformers"}, "BERT")
    assert not covered_by({"Sentence-Transformers"}, "TransE")


def test_keep_concepts_drops_fields_the_seed_already_covers():
    kept = keep_concepts(
        [{"name": "Transformer", "kind": "method"}, {"name": "TransE", "kind": "method"}],
        {"Sentence-Transformers"},
    )
    assert [item["name"] for item in kept] == ["TransE"]


def test_evaluation_plan_without_scores_is_an_evidence_gap():
    chunks = [
        {
            "id": "P:s21",
            "section": "A. Evaluation of Semantic Retrieval",
            "text": "Precision@K and Recall@K can be measured with prepared queries.",
        },
        {
            "id": "P:s26",
            "section": "F. Expected Discussion",
            "text": "Because the system is not yet implemented, numerical performance results are left for the testing stage.",
        },
    ]
    gaps = evidence_gaps("P", chunks)
    assert gaps
    assert gaps[0]["source"] == "evidence"
    assert "does not report measured" in gaps[0]["statement"]


def test_a_scored_results_section_is_not_an_evidence_gap():
    chunks = [
        {
            "id": "P:s9",
            "section": "V. RESULTS",
            "text": "The model achieves 28.4 BLEU on WMT 2014 English-to-German.",
        }
    ]
    assert evidence_gaps("P", chunks) == []
