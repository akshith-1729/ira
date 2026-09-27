# Research Assistant

A paper goes in by PDF or by OpenAlex / DOI / arXiv id. Neo4j stores the citation graph and the SPECTER2 embedding. Groq writes the summary and narrates gaps that a Cypher query already found.

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

2. Copy `.env.example` to `.env` and set `OPENALEX_API_KEY` and `GROQ_API_KEY`. Both are free.

3. Backend:

```
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\pip install -r requirements-embed.txt
.venv\Scripts\uvicorn api.main:app --reload --port 8000
```

SPECTER2 stays on CPU. Generation never calls a local model server.

4. Frontend:

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.
