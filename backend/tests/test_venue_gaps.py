from ai.prompts import VENUE_GAP_TASK
from venues.gap_analyzer import analyze_gaps, deterministic_gaps, parse_llm_gaps


KNOWN = [
    {
        "id": "gap-results",
        "title": "Legal-RAG: a planned retrieval pipeline",
        "abstract": (
            "We propose a retrieval-augmented generation workflow for case law. "
            "Numerical performance results are left to future work."
        ),
        "paper_type": "proposal",
        "demonstrated": "nothing was shown",
        "expected": {"results"},
    },
    {
        "id": "gap-baseline",
        "title": "A new ranking loss for dense retrieval",
        "abstract": (
            "We introduce a ranking loss and evaluate on MS MARCO, reporting MRR@10 of 0.38. "
            "No baseline is compared."
        ),
        "paper_type": "empirical",
        "demonstrated": "MRR@10 0.38 on MS MARCO",
        "expected": {"baseline"},
    },
    {
        "id": "gap-none",
        "title": "BERT: Pre-training of Deep Bidirectional Transformers",
        "abstract": (
            "We pretrain bidirectional transformers and compare against ELMo and GPT "
            "on GLUE, reporting 80.5 average."
        ),
        "paper_type": "empirical",
        "demonstrated": "80.5 on GLUE vs ELMo and GPT",
        "expected": set(),
    },
]


def test_venue_gap_prompt_stays_grounded():
    assert "Do not invent citations" in VENUE_GAP_TASK
    assert "Do not name venues" in VENUE_GAP_TASK
    assert "results" in VENUE_GAP_TASK
    assert "baseline" in VENUE_GAP_TASK


def test_hand_picked_papers_have_known_gaps():
    for paper in KNOWN:
        kinds = {gap["kind"] for gap in analyze_gaps(paper)}
        assert kinds == paper["expected"], paper["id"]


def test_analyzer_does_not_need_the_graph_or_pipeline():
    gaps = deterministic_gaps(KNOWN[0])
    assert gaps[0]["source"] == "deterministic"
    assert gaps[0]["id"].startswith("gap-results:")


def test_llm_rows_merge_over_the_same_kind():
    paper = KNOWN[0]

    class Stub:
        def complete(self, prefix, instruction, **kwargs):
            assert paper["title"] in prefix
            assert instruction == VENUE_GAP_TASK
            return {
                "gaps": [
                    {
                        "kind": "results",
                        "statement": "Future-work language replaces a reported score.",
                        "evidence": "left to future work",
                    },
                    {
                        "kind": "scope",
                        "statement": "The legal-search claim is not bounded to a corpus.",
                        "evidence": "case law",
                    },
                    {"kind": "invented", "statement": "should drop"},
                ]
            }

    gaps = analyze_gaps(paper, Stub())
    by_kind = {gap["kind"]: gap for gap in gaps}
    assert by_kind["results"]["source"] == "llm"
    assert by_kind["results"]["statement"].startswith("Future-work")
    assert by_kind["scope"]["kind"] == "scope"
    assert "invented" not in by_kind


def test_malformed_llm_output_keeps_the_deterministic_gaps():
    class Boom:
        def complete(self, *args, **kwargs):
            raise RuntimeError("groq down")

    kinds = {gap["kind"] for gap in analyze_gaps(KNOWN[0], Boom())}
    assert kinds == {"results"}


def test_parse_llm_gaps_ignores_empty_statements():
    assert parse_llm_gaps({"id": "P"}, {"gaps": [{"kind": "results", "statement": ""}]}) == []
