import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, pollJob } from "../api";
import ProgressRail from "../components/ProgressRail";

export default function Home() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [openalexId, setOpenalexId] = useState("");
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!job?.job_id || job.status === "done" || job.status === "error") return undefined;
    return pollJob(job.job_id, (update) => {
      setJob((current) => ({ ...current, ...update }));
      if (update.status === "done" && update.paper_id) {
        navigate(`/papers/${encodeURIComponent(update.paper_id)}`);
      }
    });
  }, [job?.job_id, job?.status, navigate]);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      let created;
      if (file) {
        const body = new FormData();
        body.append("file", file);
        created = await api("/papers/upload", { method: "POST", body });
      } else {
        created = await api("/papers/lookup", {
          method: "POST",
          body: JSON.stringify({ openalex_id: openalexId.trim() }),
        });
      }
      setJob({ job_id: created.job_id, status: "queued", progress: "queued" });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <p className="text-xs uppercase tracking-[0.18em] text-teal">Workflow A</p>
      <h1 className="mt-2 max-w-2xl font-serif text-4xl leading-tight">
        Put a paper in. Get the summary and the gaps the citation graph can support.
      </h1>
      <p className="mt-3 max-w-2xl text-sm text-mute">
        Upload a PDF, or paste an OpenAlex work id, DOI, or arXiv id. Lookups walk
        referenced works by id. The model only narrates topics the graph already found.
      </p>

      <form onSubmit={submit} className="mt-8 grid gap-4 md:grid-cols-2">
        <label className="block rounded-lg border border-dashed border-line bg-panel p-5">
          <span className="text-xs uppercase tracking-[0.14em] text-mute">PDF</span>
          <input
            className="mt-3 block w-full text-sm"
            type="file"
            accept="application/pdf"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
          <span className="mt-3 block text-xs text-mute">
            Needs the GROBID profile: docker compose --profile pdf up -d
          </span>
        </label>
        <label className="block rounded-lg border border-line bg-panel p-5">
          <span className="text-xs uppercase tracking-[0.14em] text-mute">OpenAlex, DOI, or arXiv</span>
          <input
            className="mt-3 w-full rounded border border-line bg-ink px-3 py-2 text-sm outline-none focus:border-teal"
            placeholder="W2741809807"
            value={openalexId}
            onChange={(event) => setOpenalexId(event.target.value)}
          />
        </label>
        <div className="md:col-span-2">
          <button
            className="rounded bg-teal px-4 py-2 text-sm font-medium text-ink disabled:opacity-50"
            disabled={busy || (!file && !openalexId.trim())}
            type="submit"
          >
            {busy ? "Starting…" : "Start analysis"}
          </button>
          {error && <p className="mt-3 text-sm text-amber">{error}</p>}
          {job && (
            <div className="mt-4">
              <p className="text-xs text-mute">
                Job {job.job_id} · {job.status}
                {job.paper_id ? ` · ${job.paper_id}` : ""}
              </p>
              <ProgressRail progress={job.progress} status={job.status} />
              {job.error && <p className="mt-3 text-sm text-amber">{job.error}</p>}
            </div>
          )}
        </div>
      </form>
    </div>
  );
}
