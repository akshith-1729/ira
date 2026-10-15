import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import Thumbs from "../components/Thumbs";
import WhereToSend from "../components/WhereToSend";
import Button from "../components/ui/Button";
import Chip from "../components/ui/Chip";

function gapReason(paper) {
  const { cited = 0, cited_with_topics: resolved = 0 } = paper.citation_context || {};
  if (cited === 0) {
    return "We did not read the reference list. What’s missing here only comes from this paper’s own text.";
  }
  if (resolved === 0) {
    return `${cited} references were read, but none had topic tags. What’s missing still comes from this paper’s text.`;
  }
  return "No extra hole showed up once broad field labels were dropped.";
}

function gapLabel(gap) {
  if (gap.source === "evidence") return "In this paper";
  if (gap.source === "method" || gap.source === "concept") return "Used in related work, not here";
  return gap.topic_name || "What’s missing";
}

function gapTone(gap) {
  if (gap.source === "evidence") return "border-amber/40 bg-amber/10";
  if (gap.source === "method" || gap.source === "concept") return "border-violet/40 bg-violet/10";
  return "border-sky/40 bg-sky/10";
}

function contributionText(item) {
  if (typeof item === "string") return item;
  return item?.text || "";
}

function plainEnglish(text) {
  return (text || "")
    .replace(/\bThe seed’s\b/g, "This paper's")
    .replace(/\bthe seed’s\b/gi, "this paper's")
    .replace(/\bseed’s\b/gi, "this paper's")
    .replace(/\bThe seed paper\b/g, "This paper")
    .replace(/\bthe seed paper\b/gi, "this paper")
    .replace(/\bseed paper\b/gi, "this paper");
}

export default function PaperDetail() {
  const { paperId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [paper, setPaper] = useState(null);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [asking, setAsking] = useState(false);
  const [removing, setRemoving] = useState(false);

  useEffect(() => {
    let stopped = false;
    setPaper(null);
    setError("");
    setAnswer(null);
    api(`/papers/${encodeURIComponent(paperId)}`)
      .then((body) => {
        if (!stopped) setPaper(body);
      })
      .catch((err) => {
        if (!stopped) setError(err.message);
      });
    return () => {
      stopped = true;
    };
  }, [paperId]);

  async function removePaper() {
    const message = paper.private
      ? "Remove this paper? Your copy will be deleted."
      : "Remove this paper from your shelf?";
    if (!window.confirm(message)) return;
    setRemoving(true);
    setError("");
    try {
      await api(`/library/${encodeURIComponent(paper.id)}`, { method: "DELETE" });
      navigate("/library");
    } catch (err) {
      setError(err.message);
      setRemoving(false);
    }
  }

  async function ask(event) {
    event.preventDefault();
    setAsking(true);
    setError("");
    try {
      const body = await api(`/papers/${encodeURIComponent(paperId)}/ask`, {
        method: "POST",
        body: JSON.stringify({ question, scope: "paper" }),
      });
      setAnswer(body);
    } catch (err) {
      setError(err.message);
    } finally {
      setAsking(false);
    }
  }

  if (error && !paper) return <p className="text-amber">{error}</p>;
  if (!paper) {
    return (
      <div className="animate-pulse space-y-5">
        <div className="h-4 w-28 rounded bg-lift" />
        <div className="h-14 w-3/4 rounded bg-lift" />
        <div className="h-40 rounded-[1.35rem] bg-panel" />
      </div>
    );
  }

  const contributions = paper.contributions || [];
  const gaps = paper.gaps || [];

  return (
    <article>
      <nav className="sticky top-16 z-10 mb-8 flex gap-2 overflow-x-auto rounded-full border border-line bg-ink/85 p-1.5 shadow-card backdrop-blur lg:top-4">
        <a className="shrink-0 rounded-full bg-teal/15 px-3 py-1.5 text-sm text-teal" href="#summary">
          What this paper showed
        </a>
        <a className="shrink-0 rounded-full bg-amber/15 px-3 py-1.5 text-sm text-amber" href="#missing">
          What’s missing
        </a>
        <a className="shrink-0 rounded-full bg-violet/15 px-3 py-1.5 text-sm text-violet" href="#send">
          Where to send this paper
        </a>
        <a className="shrink-0 rounded-full bg-sky/15 px-3 py-1.5 text-sm text-sky" href="#ask">
          Ask
        </a>
        <Link className="shrink-0 rounded-full bg-lime/15 px-3 py-1.5 text-sm text-lime" to={`/papers/${encodeURIComponent(paper.id)}/graph`}>
          Related papers
        </Link>
      </nav>
    <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_19rem]">
      <div>
        <p className="text-sm text-mute">
          {paper.year || "Year unknown"}
          {paper.private ? " · private copy" : ""}
        </p>
        <h1 className="mt-3 max-w-4xl font-serif text-[2.35rem] leading-[1.08] tracking-tight sm:text-[3.25rem] md:text-[4.25rem]">
          {paper.title}
        </h1>
        <p className="mt-4 max-w-2xl text-[17px] leading-7 text-mute">
          {(paper.authors || []).map((author) => author.name).join(", ") || "Authors unknown"}
        </p>
        {user && paper.in_library && (
          <button
            className="mt-5 rounded-full border border-line px-4 py-2 text-sm text-rose transition hover:border-rose disabled:opacity-40"
            disabled={removing}
            onClick={removePaper}
            type="button"
          >
            {removing ? "Removing…" : "Remove"}
          </button>
        )}
        {paper.demonstrated && (
          <p className="mt-5 max-w-2xl text-[17px] leading-7">{paper.demonstrated}</p>
        )}

        <section id="summary" className="mt-16 scroll-mt-28">
          <h2 className="font-serif text-3xl md:text-4xl">What this paper showed</h2>
          <p className="mt-3 max-w-xl text-sm text-mute">Written from this paper’s own text.</p>
          <p className="mt-6 max-w-3xl text-[17px] leading-8">
            {paper.summary || "No summary yet. Submit the paper again if analysis did not finish."}
          </p>
          <div className="mt-8">
            <h3 className="font-serif text-2xl">Contributions</h3>
            {contributions.length === 0 ? (
              <p className="mt-3 text-mute">None saved yet.</p>
            ) : (
              <ul className="mt-4 space-y-3">
                {contributions.map((item, index) => {
                  const text = contributionText(item);
                  if (!text) return null;
                  return (
                    <li key={text || index} className="max-w-3xl text-[17px] leading-7">
                      {text}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </section>

        <section id="missing" className="mt-16 scroll-mt-28 border-t border-line pt-10">
          <h2 className="font-serif text-3xl md:text-4xl">What’s missing</h2>
          {gaps.length === 0 ? (
            <p className="mt-4 max-w-xl text-[17px] leading-7 text-mute">{gapReason(paper)}</p>
          ) : (
            <div className="mt-6 space-y-4">
              {gaps.map((gap) => (
                <div key={gap.id} className={`rounded-[1.35rem] border p-6 shadow-card ${gapTone(gap)}`}>
                  <Chip tone={gap.source === "evidence" ? "amber" : gap.source === "method" || gap.source === "concept" ? "violet" : "sky"}>
                    {gapLabel(gap)}
                  </Chip>
                  <p className="mt-3 text-[17px] leading-7">{plainEnglish(gap.statement)}</p>
                  {gap.direction && (
                    <p className="mt-4 text-[17px] leading-7 text-mute">
                      <span className="text-cream">What to try next. </span>
                      {plainEnglish(gap.direction)}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        <WhereToSend advice={paper.venue_advice} />
      </div>

      <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
        <section id="ask" className="scroll-mt-28 rounded-[1.35rem] border border-line bg-panel p-6 shadow-card">
          <h2 className="font-serif text-2xl">Ask about this paper</h2>
          <p className="mt-2 text-sm leading-6 text-mute">Answers come from this paper’s sections.</p>
          <form className="mt-5" onSubmit={ask}>
            <textarea
              className="min-h-[7rem] w-full rounded-2xl border border-line bg-ink px-3 py-3 text-[15px] outline-none transition focus:border-teal"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="What does the method assume?"
            />
            <Button className="mt-3" disabled={asking || !question.trim()}>
              {asking ? "Reading…" : "Ask"}
            </Button>
          </form>
          {error && paper && <p className="mt-3 text-sm text-amber">{error}</p>}
          {answer && (
            <div className="mt-5">
              <p className="text-[15px] leading-7">{answer.answer}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {(answer.supporting_chunks || []).map((chunk) => (
                  <Chip key={chunk.id} tone="sky" className="cursor-help" title={chunk.excerpt}>
                    {chunk.section || "Passage"}
                  </Chip>
                ))}
              </div>
              <Thumbs feedbackId={answer.feedback_id} />
            </div>
          )}
        </section>
      </aside>
    </div>
    </article>
  );
}
