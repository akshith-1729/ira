# Ira

Ira reads one research paper and lays out what that paper actually did, what it left open, and which journals or conferences are a reasonable place to send it.

You start with a paper you already have. Upload the PDF, or paste an OpenAlex id, a DOI, or an arXiv id. Ira pulls the bibliographic record, reads the text it can get, and follows the references far enough to see what the surrounding work is about. The result is a page for that paper, not a general survey of the field.

On that page, four things are filled in from the paper itself:

**What this paper showed.** A short summary and a list of contributions, written from the paper’s own sections. The wording comes from Groq, and it stays tied to text Ira stored for that paper.

**What’s missing.** Gaps Ira can point at. Some come from claims and limits inside the paper. Others are topics or methods that show up in the papers it cites and do not show up here, with a concrete direction for what to try next. If the reference list could not be read, Ira says so and stays with the paper’s own text.

**Where to send this paper.** A shortlist of venues matched to this paper’s subject, with more options underneath. The match is for this manuscript. It is a suggestion, and acceptance is a separate decision.

**Ask.** A question box. Answers are drawn from this paper’s sections, and each answer points at the passages it used. You can mark an answer up or down.

**Related papers** opens the citation graph: the paper in the middle, the work it cites, and the links Ira stored while reading it.

Search is separate from that page. You type a research question, Ira checks papers already in your graph, and it also looks through the OpenAlex catalog. A result you open can be brought in and read the same way as a paper you submitted yourself.

Your account keeps a library of the papers you have submitted or saved. Register with an email address. If SMTP is set, the confirmation code arrives by mail. If it is left blank, the code is shown on screen so you can still finish signing up. Profile and password live on the account page.

Underneath, Neo4j holds the papers, citations, and topics. Postgres holds accounts, the library, and the job that tracks each upload or lookup while it runs. GROBID turns an uploaded PDF into sections and a reference list. Groq writes the summary, the gap narration, and the answers. SPECTER2 can embed a paper on CPU, and that step stays off unless `EMBED_ON_INGEST=true`. Search uses the graph and OpenAlex, not that embedding.

## Run

1. Install Docker Desktop, then from this folder:

```
docker compose up -d
docker compose --profile pdf up -d
```

The `pdf` profile starts GROBID. Skip it until you upload a PDF. On an 8GB machine, stop GROBID when you are not parsing:

```
docker compose --profile pdf down
```

Neo4j and Postgres should stay up (`docker compose up -d`). Use `127.0.0.1` rather than `localhost` if Windows IPv6 hangs.

2. Copy `.env.example` to `.env` and set `OPENALEX_API_KEY` and `GROQ_API_KEY`. Both are free. SMTP settings are optional.

3. Backend:

```
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\pip install -r requirements-embed.txt
.venv\Scripts\uvicorn api.main:app --reload --port 8000
```

SPECTER2 stays on CPU and is off by default (`EMBED_ON_INGEST=false`). Search uses the graph, not that vector. Generation always goes to Groq over HTTPS.

4. Frontend:

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The API is at http://127.0.0.1:8000.
