import json
import re

# A whole parsed paper is normally 10k-60k characters. The earlier 8k budget cut
# every results section off, so summaries could only restate the abstract.
_PREFIX_LIMIT = 60000
_SECTION_LIMIT = 8000


def build_prefix(title: str, abstract: str, chunks: list[dict] | None = None) -> str:
    """Stable leading block shared by summary, gap, and ask calls."""
    parts = [f"TITLE: {title or ''}", f"ABSTRACT: {abstract or ''}"]
    for chunk in chunks or []:
        section = chunk.get("section") or "section"
        text = (chunk.get("text") or "")[:_SECTION_LIMIT]
        if not text:
            continue
        # The abstract is already the second block; repeating it wastes budget.
        if (chunk.get("section") or "").lower() == "abstract" and text in (abstract or ""):
            continue
        chunk_id = chunk.get("id")
        header = f"[{chunk_id}] SECTION {section}:" if chunk_id else f"SECTION {section}:"
        parts.append(f"{header}\n{text}")
    prefix = "\n\n".join(parts)
    return prefix[:_PREFIX_LIMIT]


def parse_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError("Model did not return JSON")
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("Model JSON was not an object")
    return value


SUMMARY_TASK = """
Write a reviewer brief of the paper in the leading block. Use only that text.

Do not paraphrase the abstract. Do not copy the paper's own contribution list or system-
overview slogans ("we combine X and Y"). Name concrete methods, datasets, metrics, and
numbers when they appear. If a later section only plans an evaluation, say that the result
is unspecified.

paper_type is one of: empirical, proposal, survey, position.
demonstrated is one sentence: what was actually measured or shown, or that nothing was.

Return JSON:
{"paper_type":"proposal|empirical|survey|position",
 "demonstrated":"what the text actually shows",
 "summary":"4-6 sentences: problem, specified method (names), evaluation status, what is not shown",
 "contributions":[{"text":"one technical choice that is not a module slogan","chunk_id":"id","status":"specified|demonstrated"}]}

Each chunk_id must be an id shown in square brackets in the leading block. Prefer method,
results, or evaluation sections over the abstract. Do not mention venues. Do not invent citations.
""".strip()


def gap_task(diff: list[dict]) -> str:
    lines = []
    for row in diff:
        papers = []
        for paper in row["papers"]:
            snippet = (paper.get("abstract") or "").strip()
            piece = f"{paper['id']}: {paper['title']}"
            if snippet:
                piece += f" | {snippet[:220]}"
            papers.append(piece)
        lines.append(
            f"- topic_id={row['topic_id']} topic={row['topic_name']} kind={row.get('kind') or 'topic'} covered_by={'; '.join(papers)}"
        )
    catalog = "\n".join(lines)
    return f"""
The leading block is the seed paper. A graph query found methods or topics that cited papers
use and the seed does not.

Narrate only the catalog below. Do not add items. Do not name venues.
Do not recommend a whole field (sentiment analysis, bioinformatics, computer science)
unless the seed's own pipeline would actually use that method.

For each item, name the seed's method and the cited paper's method, then say which
pipeline step would change. A sentence that only repeats the catalog label is not useful.

COVERAGE DIFF:
{catalog}

Return JSON:
{{"gaps":[{{"topic_id":"...","statement":"seed method vs cited method, one sentence","direction":"one measurable experiment","claims":[{{"text":"what the cited work does","paper_ids":["..."]}}]}}]}}
paper_ids must be chosen from the covered_by ids above.
""".strip()


ASK_TASK = """
Answer the question using only the paper text in the leading block.
Quote the paper's own terms, names, and numbers rather than describing them in general words.
Return JSON: {"answer":"...","chunk_ids":["chunk id", "..."]}
chunk_ids must be ids shown in square brackets in the leading block, and must be the sections the
answer actually came from. If the leading block does not contain the answer, say so plainly instead
of guessing.
""".strip()


KEYWORD_TASK = """
Extract up to 8 short topical keywords from the leading block.
Return JSON: {"keywords":["..."]}
""".strip()


CONCEPT_TASK = """
Extract technical concepts the seed paper's own system uses or specifies.
Include only methods, stores, and metrics from the design or experiments.
Do not include methods that appear only in related work or citations.
Do not invent. Do not include generic fields (computer science, NLP, machine learning).
Return JSON: {"concepts":[{"name":"Sentence-BERT","kind":"method"}]}
Max 16 items.
""".strip()


QUERY_TASK = """
Decide if the user's text is a research question or paper title. If it is keysmash,
gibberish, or has no scholarly field (for example "ding doong"), set valid=false.

If valid, turn it into a search intent. The words they typed are not always the
topics. Drop fillers (new, modern, flaws, technology, project, research, paper,
study, system, based). Expand the field into the topics a bibliographic index
would use for that meaning today.

Use the current research sense unless the user named the old one
(Web 3.0 → blockchain / smart contracts, not 2009 semantic web / RDF;
unless they said semantic web).

catalog_query is at most 6 words. It must name the specific problem, not a parent
word (technology) and not a decade-old homonym. Example: "smart contract
vulnerability", not only "web 3.0".
must_match are 1-3 short field names (smart contract, blockchain, transformer),
never exploit types or parent words.

Return JSON:
{"valid":true,
 "reason":"",
 "field":"short field name",
 "intent":"one sentence research question",
 "topics":["..."],
 "methods":["..."],
 "must_match":["..."],
 "catalog_query":"..."}
""".strip()


def query_task(query: str) -> str:
    return f"{QUERY_TASK}\n\nQUERY:\n{query.strip()}"


def search_brief_task(query: str, intent: dict, rows: list[dict]) -> str:
    lines = []
    for row in rows:
        paper = row.get("paper") or {}
        topics = " · ".join((row.get("reasons") or [])[:4])
        abstract = (paper.get("summary") or "")[:360]
        lines.append(
            f"- id={paper.get('id')} title={paper.get('title')} year={paper.get('year')}"
            f" topics={topics or '(none)'}\n  ABSTRACT: {abstract or '(none)'}"
        )
    catalog = "\n".join(lines) or "(no papers retrieved)"
    field = intent.get("field") or ""
    question = intent.get("intent") or query
    return f"""
The user asked: {query}
Interpreted field: {field}
Interpreted question: {question}

The papers below are the only evidence. Write a related-work brief of this set.
Do not add papers. Do not restate titles as a list. Name methods and claims that
appear in the abstracts. Say what this set does not cover for the question.

relevant=true only if the paper helps answer the interpreted question in the
current sense of the field (defines it, measures it, or studies the same problem).
relevant=false if it is a different field, or only an older homonym
(semantic-web "Web 3.0" when the question is smart contracts; cell imaging;
generic education when the field is Web 3.0).

Return JSON:
{{"brief":"3-5 sentences on what this set actually covers",
 "hits":[{{"id":"must be an id from the list","relevant":true,"score":8,"why":"why this paper belongs, or omit it"}}]}}
score is 1-10. 8-10 answers the question; 5-7 is the same problem nearby.
Omit score < 5 and every relevant=false row.

PAPERS:
{catalog}
""".strip()


def neighbor_concept_task(neighbors: list[dict]) -> str:
    lines = []
    for paper in neighbors:
        abstract = (paper.get("abstract") or "").strip()
        if not abstract:
            abstract = "(no abstract)"
        lines.append(f"- id={paper['id']} title={paper.get('title') or paper['id']}\n  ABSTRACT: {abstract[:800]}")
    catalog = "\n".join(lines)
    return f"""
Extract the method each cited paper introduces. Skip its evaluation datasets,
metrics, and tasks (WMT, BLEU, GLUE, SQuAD). Skip generic fields
(computer science, NLP, machine learning, algorithm).
Return JSON:
{{"papers":[{{"id":"...","concepts":[{{"name":"Transformer","kind":"method"}}]}}]}}

CITED PAPERS:
{catalog}
""".strip()


VENUE_GAP_TASK = """
The leading block is one paper. List submission-blocking gaps in that text only.

Kinds: results, baseline, dataset, scope.
- results: the method is specified but no measured score is reported
- baseline: scores are reported but no named comparison appears
- dataset: a claim is evaluated without naming the corpus
- scope: the claim is broader than the evidence in the text

Do not invent citations, numbers, or datasets. Do not name venues.
If the text already reports a score against a named baseline on a named dataset, return no gap of that kind.

Return JSON:
{"gaps":[{"kind":"results|baseline|dataset|scope","statement":"one sentence","evidence":"short quote from the leading block"}]}
""".strip()
