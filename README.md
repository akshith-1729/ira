# Ira

Ira is a research assistant for one paper at a time. You sign in, submit a PDF or an OpenAlex, DOI, or arXiv id, and Ira builds a citation graph, a short summary, and a suggestion of where the work could be sent.

## What it does

- Accounts with email confirmation. Leave SMTP blank and the code appears on screen.
- Paper intake by PDF upload or by OpenAlex, DOI, or arXiv id.
- A citation graph in Neo4j, with a visual explorer.
- Search across papers already in the graph and the OpenAlex catalog.
- A summary and answers about the paper, written by Groq from the stored text.
- Venue advice for where to send the work, plus a personal library.

Postgres stores accounts, jobs, and the library. GROBID reads uploaded PDFs. SPECTER2 embeddings stay on CPU and are off unless `EMBED_ON_INGEST=true`.

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
