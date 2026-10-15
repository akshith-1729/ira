import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import PageHero from "../components/PageHero";
import Button from "../components/ui/Button";
import Chip from "../components/ui/Chip";
import Empty from "../components/ui/Empty";

const JOB_STATUS = {
  queued: "Queued",
  running: "Running",
  done: "Done",
  error: "Failed",
};

function when(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export default function Library() {
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState("");
  const [removing, setRemoving] = useState("");

  function load() {
    setError("");
    api("/library")
      .then(setPayload)
      .catch((err) => setError(err.message));
  }

  useEffect(() => {
    load();
  }, []);

  async function remove(paper) {
    const message = paper.private
      ? "Remove this paper? Your copy will be deleted."
      : "Remove this paper from your shelf?";
    if (!window.confirm(message)) return;
    setRemoving(paper.paper_id);
    setError("");
    try {
      await api(`/library/${encodeURIComponent(paper.paper_id)}`, { method: "DELETE" });
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setRemoving("");
    }
  }

  return (
    <div>
      <PageHero icon="books" tone="amber" title="Your papers">
        Papers you submitted. Open one, or remove it from this shelf.
      </PageHero>
      {error && <p className="mt-6 text-sm text-amber">{error}</p>}
      {!payload && !error && <p className="mt-8 text-mute">Loading…</p>}
      {payload && (
        <>
          <ul className="mt-8 grid gap-4 sm:grid-cols-2">
            {payload.papers.length === 0 && (
              <li className="sm:col-span-2">
                <Empty icon="books" tone="amber">
                  Nothing here yet. Submit a paper and it will show up on this shelf.
                </Empty>
              </li>
            )}
            {payload.papers.map((paper) => (
              <li
                key={paper.paper_id}
                className="flex flex-col gap-4 overflow-hidden rounded-[1.35rem] border border-line bg-panel shadow-card"
              >
                <div className={`h-1.5 ${paper.private ? "bg-teal" : "bg-sky"}`} />
                <div className="flex flex-1 flex-col px-5 pb-5">
                  <div className="flex flex-wrap gap-2">
                    <Chip tone={paper.private ? "teal" : "sky"}>{paper.private ? "Your upload" : "Public paper"}</Chip>
                    {paper.year ? <Chip tone="amber">{paper.year}</Chip> : null}
                  </div>
                  <Link
                    className="mt-3 block font-serif text-2xl leading-snug hover:text-teal"
                    to={`/papers/${encodeURIComponent(paper.paper_id)}`}
                  >
                    {paper.title}
                  </Link>
                  <p className="mt-2 text-sm text-mute">{when(paper.added_at)}</p>
                  <Button
                    className="mt-4 self-start"
                    tone="rose"
                    disabled={removing === paper.paper_id}
                    onClick={() => remove(paper)}
                    type="button"
                  >
                    {removing === paper.paper_id ? "Removing…" : "Remove"}
                  </Button>
                </div>
              </li>
            ))}
          </ul>

          <section className="mt-16 border-t border-line pt-10">
            <h2 className="font-serif text-3xl">Recent analyses</h2>
            <ul className="mt-6 space-y-3">
              {payload.jobs.length === 0 && <li className="text-mute">No analyses yet.</li>}
              {payload.jobs.map((job) => (
                <li key={job.id} className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-line bg-panel px-4 py-3">
                  <Chip tone={job.status === "error" ? "rose" : job.status === "done" ? "lime" : "amber"}>
                    {JOB_STATUS[job.status] || job.status}
                  </Chip>
                  <span className="text-sm text-mute">{when(job.created_at)}</span>
                  {job.error && <p className="w-full text-sm text-amber">{job.error}</p>}
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
