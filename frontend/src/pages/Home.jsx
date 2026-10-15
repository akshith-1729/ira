import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, pollJob } from "../api";
import { useAuth } from "../auth";
import { Icon } from "../components/Icons";
import PageHero from "../components/PageHero";
import ProgressRail from "../components/ProgressRail";
import Button from "../components/ui/Button";
import Panel from "../components/ui/Panel";
import Stat from "../components/ui/Stat";
import { useHealth } from "../health";

export default function Home() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const health = useHealth();
  const [file, setFile] = useState(null);
  const [paperId, setPaperId] = useState("");
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const fileInput = useRef(null);
  const grobidUp = health?.grobid === "up";

  useEffect(() => {
    if (!job?.job_id || job.status === "done" || job.status === "error") return undefined;
    return pollJob(job.job_id, (update) => {
      setJob((current) => ({ ...current, ...update }));
      if (update.status === "done" && update.paper_id) {
        navigate(`/papers/${encodeURIComponent(update.paper_id)}`);
      }
    });
  }, [job?.job_id, job?.status, navigate]);

  function takeFile(next) {
    if (!next) return;
    if (!next.name.toLowerCase().endsWith(".pdf") && next.type !== "application/pdf") {
      setError("Upload a PDF");
      return;
    }
    setError("");
    setFile(next);
    setPaperId("");
  }

  function clearFile() {
    setFile(null);
    if (fileInput.current) fileInput.current.value = "";
  }

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
          body: JSON.stringify({ openalex_id: paperId.trim() }),
        });
      }
      setJob({ job_id: created.job_id, status: "queued", progress: "queued" });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const working = busy || (job && job.status !== "error" && job.status !== "done");

  return (
    <div>
      <PageHero icon="spark" tone="violet" title="Submit your paper">
        We read it, say what’s missing, and suggest where to send it.
      </PageHero>

      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        <Stat icon="file" tone="teal" label="1" value="Read the paper" />
        <Stat icon="search" tone="violet" label="2" value="See what’s missing" />
        <Stat icon="chart" tone="amber" label="3" value="See where to send it" />
      </div>

      {user === undefined && <p className="mt-10 text-mute">Loading…</p>}
      {user === null && (
        <Panel className="mt-8 max-w-xl" icon="user" tone="sky" title="Sign in to submit">
          <p className="mt-3 text-[17px] leading-7 text-mute">
            An account keeps the paper on your shelf, so you can open it again or remove it.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button to="/login">Sign in</Button>
            <Button to="/register" tone="outline">
              Create an account
            </Button>
          </div>
        </Panel>
      )}
      {user && !user.verified && (
        <Panel className="mt-8 max-w-xl" icon="mail" tone="amber" title="Confirm your email">
          <p className="mt-3 text-[17px] leading-7 text-mute">
            {user.email} is not confirmed yet. Enter the code before you submit a paper.
          </p>
          <Button className="mt-6" to="/verify">
            Enter the code
          </Button>
        </Panel>
      )}
      {user?.verified && (
      <form onSubmit={submit} className="mt-8 grid gap-5 lg:grid-cols-2">
        <div
          className={`relative overflow-hidden rounded-[1.35rem] border border-dashed bg-panel shadow-card transition duration-200 ${
            over ? "border-teal bg-teal/10" : "border-teal/40"
          } ${!grobidUp ? "opacity-70" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(event) => {
            event.preventDefault();
            setOver(false);
            takeFile(event.dataTransfer.files?.[0]);
          }}
        >
          <div className="h-1.5 bg-gradient-to-r from-teal via-sky to-transparent" />
          <div className="p-6 sm:p-8">
          <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-teal/15 text-teal">
            <Icon name="file" />
          </span>
          <p className="mt-4 text-sm text-teal">PDF</p>
          <p className="mt-2 font-serif text-3xl">Drop a paper here</p>
          <input
            ref={fileInput}
            className="mt-6 block w-full text-sm"
            type="file"
            accept="application/pdf"
            disabled={!grobidUp}
            onChange={(event) => takeFile(event.target.files?.[0] || null)}
          />
          {file && (
            <div className="mt-4 flex items-center justify-between gap-3">
              <p className="min-w-0 truncate text-sm text-teal">{file.name}</p>
              <Button tone="rose" className="shrink-0 px-3 py-1 shadow-none" onClick={clearFile} type="button">
                Remove
              </Button>
            </div>
          )}
          <p className="mt-4 text-sm leading-6 text-mute">
            {grobidUp
              ? "The PDF reader is ready."
              : "PDF upload needs the PDF reader. You can still submit with a paper id."}
          </p>
          </div>
        </div>

        <label className="block overflow-hidden rounded-[1.35rem] border border-violet/40 bg-panel shadow-card">
          <div className="h-1.5 bg-gradient-to-r from-violet via-sky to-transparent" />
          <div className="p-6 sm:p-8">
          <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-violet/15 text-violet">
            <Icon name="search" />
          </span>
          <p className="mt-4 text-sm text-violet">DOI, arXiv, or paper id</p>
          <p className="mt-2 font-serif text-3xl">Look up a published paper</p>
          <input
            className="mt-6 w-full rounded-2xl border border-line bg-ink px-4 py-3 text-[15px] outline-none transition focus:border-teal"
            placeholder="10.xxxx/… or 1706.03762"
            value={paperId}
            onChange={(event) => {
              setPaperId(event.target.value);
              if (event.target.value.trim()) clearFile();
            }}
          />
          <p className="mt-4 text-sm leading-6 text-mute">Paste a DOI, arXiv number, or a public paper id.</p>
          </div>
        </label>

        <div className="lg:col-span-2">
          <Button
            className="bg-gradient-to-r from-teal via-sky to-violet px-6 py-3"
            disabled={working || (!file && !paperId.trim()) || (file && !grobidUp)}
            type="submit"
          >
            {working ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-ink/30 border-t-ink" />
            ) : (
              <Icon name="spark" className="h-4 w-4" />
            )}
            {working ? "Reading…" : "Start analysis"}
          </Button>
          {error && <p className="mt-4 text-sm text-amber">{error}</p>}
          {job && (
            <div className="mt-6 rounded-[1.35rem] border border-line bg-panel p-6 shadow-card">
              <ProgressRail progress={job.progress} status={job.status} />
              {job.error && <p className="mt-3 text-sm text-amber">{job.error}</p>}
            </div>
          )}
        </div>
      </form>
      )}
    </div>
  );
}
