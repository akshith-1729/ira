import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import Thumbs from "../components/Thumbs";

function gapReason(paper) {
  const { cited = 0, cited_with_topics: resolved = 0 } = paper.citation_context || {};
  if (cited === 0) {
    return "No references were read out of this paper, so there is no citation neighborhood to compare it against.";
  }
  if (resolved === 0) {
    return `${cited} references were read, but none carry OpenAlex topics. Coverage gaps still come from cited methods and from missing results in this paper.`;
  }
  return "No coverage gap showed up once generic field tags were dropped.";
}

function gapLabel(gap) {
  if (gap.source === "evidence") return "From this paper's sections";
  if (gap.source === "method" || gap.source === "concept") return "Cited method not used";
  return gap.topic_name || "Coverage";
}

export default function PaperDetail() {
  const { paperId } = useParams();
  const [paper, setPaper] = useState(null);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [asking, setAsking] = useState(false);

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
  if (!paper) return <p className="text-mute">Loading paper…</p>;

  return (
    <article>
      <p className="text-xs uppercase tracking-[0.16em] text-teal">
        {paper.year || "n.d."}
        {paper.private ? " · private" : ""}
        <span className="ml-3 font-mono normal-case tracking-normal text-mute">{paper.id}</span>
      </p>
      <h1 className="mt-2 font-serif text-4xl leading-tight">{paper.title}</h1>
      <p className="mt-2 text-sm text-mute">
        {(paper.authors || []).map((author) => author.name).join(", ") || "Authors unknown"}
      </p>
      <p className="mt-4">
        <Link className="text-sm text-teal" to={`/papers/${encodeURIComponent(paper.id)}/graph`}>
          Open in the graph
        </Link>
      </p>

      {(paper.paper_type || paper.demonstrated) && (
        <p className="mt-4 max-w-3xl text-sm text-mute">
          {paper.paper_type ? <span className="mr-3 uppercase tracking-[0.14em] text-teal">{paper.paper_type}</span> : null}
          {paper.demonstrated}
        </p>
      )}

      <Section title="Summary">
        <p className="max-w-3xl leading-7">{paper.summary || "No summary yet."}</p>
      </Section>

      <Section title="Contributions">
        {(paper.contributions || []).length === 0 && <p className="text-mute">None stored.</p>}
        <ul className="list-disc space-y-2 pl-5">
          {(paper.contributions || []).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </Section>

      <Section title="Gaps">
        {(paper.gaps || []).length === 0 && <p className="text-mute">{gapReason(paper)}</p>}
        <div className="space-y-4">
          {(paper.gaps || []).map((gap) => (
            <div key={gap.id} className="rounded-lg border border-line bg-panel p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-amber">{gapLabel(gap)}</p>
              {gap.topic_name && gap.source !== "evidence" && (
                <p className="mt-1 text-xs text-mute">{gap.topic_name}</p>
              )}
              <p className="mt-2 leading-7">{gap.statement}</p>
              {gap.direction && <p className="mt-2 text-sm text-mute">Direction: {gap.direction}</p>}
              <div className="mt-3 flex flex-wrap gap-2">
                {(gap.claims || []).flatMap((claim) =>
                  claim.chunk_id ? (
                    <span
                      key={claim.id}
                      title={claim.excerpt || claim.text}
                      className="rounded-full border border-line px-2 py-1 text-xs text-mute"
                    >
                      supported by {claim.section || "chunk"}
                    </span>
                  ) : null
                )}
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Similar papers">
        <PaperList rows={paper.recommended_papers || []} />
      </Section>

      <Section title="Venues from the graph">
        {(paper.recommended_venues || []).length === 0 && (
          <p className="text-mute">No venue is linked to these topics yet.</p>
        )}
        <ul className="space-y-2">
          {(paper.recommended_venues || []).map((venue) => (
            <li key={venue.id} className="text-sm">
              {venue.name}
              <span className="ml-2 text-mute">
                via {(venue.source_papers || []).join(", ") || "recorded papers"}
              </span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Ask this paper">
        <form onSubmit={ask} className="flex gap-2">
          <input
            className="flex-1 rounded border border-line bg-ink px-3 py-2 text-sm outline-none focus:border-teal"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="What does the method assume?"
          />
          <button
            className="rounded bg-teal px-3 py-2 text-sm text-ink disabled:opacity-50"
            disabled={asking || !question.trim()}
          >
            Ask
          </button>
        </form>
        {error && <p className="mt-3 text-sm text-amber">{error}</p>}
        {answer && (
          <div className="mt-4">
            <p className="leading-7">{answer.answer}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {(answer.supporting_chunks || []).map((chunk) => (
                <span key={chunk.id} title={chunk.excerpt} className="rounded-full border border-line px-2 py-1 text-xs text-mute">
                  {chunk.section || chunk.id}
                </span>
              ))}
            </div>
            <Thumbs feedbackId={answer.feedback_id} />
          </div>
        )}
      </Section>
    </article>
  );
}

function Section({ title, children }) {
  return (
    <section className="mt-8 border-t border-line pt-5">
      <h2 className="text-xs uppercase tracking-[0.16em] text-teal">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function PaperList({ rows }) {
  if (!rows.length) {
    return (
      <p className="text-mute">
        No other paper in this graph shares a topic, a method, or a citation path with this one.
      </p>
    );
  }
  return (
    <ul className="space-y-3">
      {rows.map((row) => (
        <li key={row.paper.id}>
          <Link className="hover:text-teal" to={`/papers/${encodeURIComponent(row.paper.id)}`}>
            {row.paper.title}
          </Link>
          <span className="ml-2 text-xs text-mute">{row.paper.year || ""}</span>
          {(row.reasons || []).length > 0 && (
            <p className="mt-1 text-xs text-mute">{row.reasons.join(" · ")}</p>
          )}
        </li>
      ))}
    </ul>
  );
}
