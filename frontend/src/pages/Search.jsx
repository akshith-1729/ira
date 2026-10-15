import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, pollJob } from "../api";
import PageHero from "../components/PageHero";
import ResultRow from "../components/ResultRow";
import SearchField from "../components/SearchField";
import Thumbs from "../components/Thumbs";
import Chip from "../components/ui/Chip";
import Empty from "../components/ui/Empty";

export default function Search() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState(params.get("q") || "");
  const [topic, setTopic] = useState("");
  const [filterOpen, setFilterOpen] = useState(false);
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [looking, setLooking] = useState("");
  const lastQuery = useRef("");

  async function run(nextQuery) {
    const q = (nextQuery ?? query).trim();
    if (!q) return;
    const key = `${q}::${topic.trim()}`;
    lastQuery.current = key;
    setBusy(true);
    setError("");
    setPayload(null);
    try {
      const body = await api("/search", {
        method: "POST",
        body: JSON.stringify({ query: q, topic: topic.trim() || null }),
      });
      setPayload(body);
      if (params.get("q") !== q) setParams({ q }, { replace: true });
    } catch (err) {
      lastQuery.current = "";
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    const q = params.get("q");
    if (!q) return;
    setQuery(q);
    const key = `${q}::${topic.trim()}`;
    if (lastQuery.current === key) return;
    run(q);
  }, [params]);

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

  const ranked = payload
    ? [...(payload.results || []), ...(payload.catalog || [])].sort(
        (a, b) => (b.relevance || 0) - (a.relevance || 0)
      )
    : [];

  return (
    <div>
      <PageHero icon="search" tone="violet" title="Find papers">
        Ask a research question or paste a title. We skip nonsense, then list papers you already
        analyzed and public matches.
      </PageHero>

      <div className="mt-8 rounded-[1.6rem] border border-violet/30 bg-gradient-to-br from-violet/20 via-sky/10 to-panel p-4 shadow-card sm:p-6">
      <SearchField
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        onSubmit={() => {
          lastQuery.current = "";
          run();
        }}
        placeholder="Ask a research question"
        action="Search"
        busy={busy}
        disabled={!query.trim()}
      />
      </div>

      <button
        className="mt-3 text-sm text-mute hover:text-cream"
        type="button"
        onClick={() => setFilterOpen((open) => !open)}
      >
        {filterOpen ? "Hide topic filter" : "Narrow by topic"}
      </button>
      {filterOpen && (
        <input
          className="mt-3 w-full max-w-md rounded-2xl border border-line bg-panel px-4 py-3 text-sm outline-none focus:border-teal"
          value={topic}
          onChange={(event) => setTopic(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              lastQuery.current = "";
              run();
            }
          }}
          placeholder="Optional topic name"
        />
      )}

      {error && <p className="mt-6 text-sm text-amber">{error}</p>}
      {busy && (
        <div className="mt-10 flex items-center gap-4 rounded-[1.35rem] border border-line bg-panel px-6 py-5">
          <span className="h-6 w-6 animate-spin rounded-full border-2 border-line border-t-teal" />
          <p className="font-serif text-2xl">Checking the question, then ranking papers…</p>
        </div>
      )}

      {payload && (payload.field || payload.intent || payload.brief) && (
        <section className="mt-10 max-w-3xl">
          {payload.field && <Chip tone="violet">{payload.field}</Chip>}
          {payload.intent && payload.intent !== query && (
            <p className="mt-2 font-serif text-3xl leading-snug">{payload.intent}</p>
          )}
          {payload.brief && <p className="mt-3 text-[17px] leading-7 text-mute">{payload.brief}</p>}
        </section>
      )}

      {payload && (
        <section className="mt-12">
          <div className="flex items-end justify-between gap-3">
            <h2 className="font-serif text-3xl">Papers</h2>
            <span className="text-sm text-mute">{ranked.length}</span>
          </div>
          {ranked.length === 0 && (
            <div className="mt-4">
              <Empty icon="search" tone="violet">
                {payload.brief || "No relevant paper turned up for this question."}
              </Empty>
            </div>
          )}
          <ul className="mt-6 space-y-4">
            {ranked.map((row) => (
              <ResultRow key={row.paper.id} row={row} onAnalyze={analyze} looking={looking} />
            ))}
          </ul>
        </section>
      )}

      <Thumbs feedbackId={payload?.feedback_id} />
    </div>
  );
}
