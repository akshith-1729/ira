import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, pollJob } from "../api";
import Thumbs from "../components/Thumbs";

export default function Search() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [topic, setTopic] = useState("");
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [looking, setLooking] = useState("");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = await api("/search", {
        method: "POST",
        body: JSON.stringify({ query, topic: topic.trim() || null }),
      });
      setPayload(body);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function analyze(openalexId) {
    setLooking(openalexId);
    setError("");
    try {
      const created = await api("/papers/lookup", {
        method: "POST",
        body: JSON.stringify({ openalex_id: openalexId }),
      });
      pollJob(created.job_id, (job) => {
        if (job.status === "done" && job.paper_id) {
          navigate(`/papers/${encodeURIComponent(job.paper_id)}`);
        }
        if (job.status === "error") {
          setError(job.error || "Lookup failed");
          setLooking("");
        }
      });
    } catch (err) {
      setError(err.message);
      setLooking("");
    }
  }

  const local = payload?.results || [];
  const catalog = payload?.catalog || [];

  return (
    <div>
      <p className="text-xs uppercase tracking-[0.16em] text-teal">Search</p>
      <h1 className="mt-2 font-serif text-4xl">Ask a research question. The graph and catalog answer with related work, not keyword hits.</h1>
      <form onSubmit={submit} className="mt-6 flex flex-col gap-3 md:flex-row">
        <input
          className="flex-1 rounded border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-teal"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="new flaws in web 3.0 technology"
        />
        <input
          className="rounded border border-line bg-panel px-3 py-2 text-sm outline-none focus:border-teal md:w-56"
          value={topic}
          onChange={(event) => setTopic(event.target.value)}
          placeholder="Topic name or id"
        />
        <button className="rounded bg-teal px-4 py-2 text-sm text-ink disabled:opacity-50" disabled={busy || !query.trim()}>
          {busy ? "Reading literature…" : "Search"}
        </button>
      </form>
      {error && <p className="mt-4 text-sm text-amber">{error}</p>}

      {payload && (payload.field || payload.intent || payload.brief) && (
        <section className="mt-8 rounded-lg border border-line bg-panel p-4">
          <h2 className="text-xs uppercase tracking-[0.16em] text-teal">Related work</h2>
          {payload.field && <p className="mt-2 text-xs text-mute">{payload.field}</p>}
          {payload.intent && <p className="mt-1 font-serif text-xl">{payload.intent}</p>}
          {payload.brief && <p className="mt-3 text-sm leading-6">{payload.brief}</p>}
        </section>
      )}

      {payload && (
        <section className="mt-8">
          <h2 className="text-xs uppercase tracking-[0.16em] text-teal">In this graph</h2>
          {local.length === 0 && (
            <p className="mt-3 text-sm text-mute">
              Nothing ingested here discusses that field. Analyze a catalog paper to put it on the graph.
            </p>
          )}
          <ResultList rows={local} />
        </section>
      )}

      {payload && (
        <section className="mt-8">
          <h2 className="text-xs uppercase tracking-[0.16em] text-teal">OpenAlex catalog</h2>
          {catalog.length === 0 && (
            <p className="mt-3 text-sm text-mute">No additional catalog hits for this query.</p>
          )}
          <ResultList rows={catalog} onAnalyze={analyze} looking={looking} />
        </section>
      )}

      <Thumbs feedbackId={payload?.feedback_id} />
    </div>
  );
}

function ResultList({ rows, onAnalyze, looking }) {
  return (
    <ul className="mt-3 space-y-3">
      {rows.map((row) => (
        <li key={row.paper.id} className="rounded-lg border border-line bg-panel p-4">
          {row.source === "openalex" ? (
            <p className="font-serif text-xl">{row.paper.title}</p>
          ) : (
            <Link className="font-serif text-xl hover:text-teal" to={`/papers/${encodeURIComponent(row.paper.id)}`}>
              {row.paper.title}
            </Link>
          )}
          <p className="mt-1 text-xs text-mute">
            {row.paper.year || "n.d."} · {row.paper.id}
          </p>
          {(row.reasons || []).length > 0 && <p className="mt-1 text-xs text-mute">{row.reasons.join(" · ")}</p>}
          {row.why && <p className="mt-2 text-sm leading-6">{row.why}</p>}
          {!row.why && row.paper.summary && <p className="mt-2 text-sm text-mute">{row.paper.summary}</p>}
          {onAnalyze && (
            <button
              className="mt-3 rounded border border-line px-3 py-1 text-xs text-teal disabled:opacity-50"
              disabled={Boolean(looking)}
              onClick={() => onAnalyze(row.paper.id)}
            >
              {looking === row.paper.id ? "Analyzing…" : "Analyze this paper"}
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
