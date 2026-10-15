from jobs.pipeline import Deps, is_parseable_paper, looks_scholarly, run_lookup


def _work(wid, title, refs=None):
    return {
        "id": f"https://openalex.org/{wid}",
        "display_name": title,
        "publication_year": 2020,
        "abstract_inverted_index": {"Hello": [0], "graph": [1]},
        "authorships": [{"author": {"id": "https://openalex.org/A1", "display_name": "Ada Lovelace"}}],
        "topics": [{"id": "https://openalex.org/T1", "display_name": "Graphs"}],
        "keywords": ["graphs"],
        "primary_location": {
            "source": {"id": "https://openalex.org/S1", "display_name": "Nature", "type": "journal"}
        },
        "referenced_works": refs or [],
    }


class _Graph:
    def set_embedding(self, paper_id, vector):
        assert len(vector) == 3


class _Store:
    def __init__(self):
        self.graph = _Graph()
        self.written = []
        self.seed = None

    def upsert_paper(self, record, *, private, owner):
        self.seed = record

    def upsert_references(self, seed_id, records):
        self.refs = records

    def write_chunks(self, paper_id, chunks):
        pass

    def chunks_for(self, paper_id, *, include_neighbors):
        return [{"id": f"{paper_id}:abstract", "section": "abstract", "text": "Hello graph", "position": 0}]

    def set_summary(self, paper_id, summary, contributions, *, paper_type="", demonstrated=""):
        self.summary = summary

    def write_claims(self, paper_id, claims, *, kind):
        pass

    def add_keywords(self, paper_id, keywords):
        pass

    def replace_concepts(self, paper_id, concepts):
        pass

    def add_concepts(self, paper_id, concepts):
        pass

    def cited_records(self, paper_id):
        return []

    def clear_gaps(self, paper_id):
        pass

    def concept_diff(self, paper_id, *, min_neighbors=1):
        return []

    def gap_diff(self, paper_id, *, min_neighbors=1):
        # One neighbor only, so the corroborated pass finds nothing and the fallback runs.
        if min_neighbors > 1:
            return []
        return [
            {
                "topic_id": "T9",
                "topic_name": "Uncertainty",
                "papers": [{"id": "W2", "title": "Neighbor"}],
            }
        ]

    def write_gap(self, paper_id, gap):
        self.written.append(gap)

    def venues_for_topics(self, topics, *, exclude_id=None):
        assert exclude_id == "W1"
        return [{"id": "S1", "name": "Nature", "source_papers": ["Neighbor"], "papers": 1, "topic_hits": 1}]

    def link_venue(self, direction_id, venue_id):
        self.venue = venue_id


class _OpenAlex:
    def get_work(self, work_id):
        if work_id == "W1":
            return _work("W1", "Seed paper", ["https://openalex.org/W2"])
        return _work(work_id, "Neighbor")

    def walk_references(self, work, limit):
        return [self.get_work("W2")]

    def walk_related(self, work, limit):
        return []


class _DB:
    def __init__(self):
        self.states = []

    def update_job(self, job_id, status, progress, *, paper_id=None, error=None):
        self.states.append((status, progress, paper_id, error))

    def add_to_library(self, user_id, paper_id, *, title, year, private):
        self.shelf = (user_id, paper_id, title, private)


class _LLM:
    def summarize(self, prefix):
        assert prefix.startswith("TITLE:")
        return {"summary": "Seed summary.", "contributions": [{"text": "One finding", "section": "abstract"}]}

    def narrate_gaps(self, prefix, diff):
        assert prefix.startswith("TITLE:")
        return {
            "gaps": [
                {
                    "topic_id": "T9",
                    "statement": "Neighbors cover uncertainty.",
                    "direction": "Measure uncertainty here.",
                    "claims": [{"text": "The neighbor measures it.", "paper_ids": ["W2"]}],
                },
                {"topic_id": "MADEUP", "statement": "Invented.", "direction": "No.", "claims": []},
            ]
        }

    def keywords(self, prefix):
        return []

    def concepts(self, prefix):
        return []

    def neighbor_concepts(self, neighbors):
        return {}


def test_lookup_pipeline_keeps_only_graph_gaps(monkeypatch):
    store = _Store()
    db = _DB()
    deps = Deps(
        settings=type("S", (), {"citation_walk_limit": 25, "local_user_id": "local", "embed_on_ingest": False})(),
        openalex=_OpenAlex(),
        store=store,
        db=db,
        llm=_LLM(),
        embed=lambda title, abstract: [0.1, 0.2, 0.3],
    )
    run_lookup("job-1", "W1", deps)
    assert store.seed["title"] == "Seed paper"
    assert [gap["topic_id"] for gap in store.written] == ["T9"]
    assert store.written[0]["claims"][0]["chunks"][0]["id"] == "W2:abstract"
    assert store.venue == "S1"
    assert db.states[-1][0] == "done", db.states[-1]


def test_story_pdf_without_structure_is_not_parseable():
    parsed = {"title": "Untitled upload", "abstract": "", "doi": None, "sections": []}
    assert not is_parseable_paper(parsed, [])
    assert not looks_scholarly(parsed, [])


def test_paper_with_title_and_sections_is_parseable():
    parsed = {
        "title": "A Review of Intrusion Detection",
        "abstract": "",
        "doi": None,
        "sections": [
            {"section": "Introduction", "text": "We study IDS."},
            {"section": "Method", "text": "Signature rules."},
        ],
    }
    assert is_parseable_paper(parsed, [])
