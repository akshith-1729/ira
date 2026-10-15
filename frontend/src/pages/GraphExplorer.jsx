import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import ForceGraph2D from "react-force-graph-2d";
import { api } from "../api";

const COLORS = {
  Paper: "#f4efe6",
  Author: "#8f8a82",
  Topic: "#3ecfaf",
  Gap: "#e8a85c",
  Direction: "#7eb6ff",
  Venue: "#d2a4ff",
};

const KIND_LABELS = {
  Paper: "Paper",
  Author: "Author",
  Topic: "Field",
  Gap: "What’s missing",
  Direction: "What to try",
  Venue: "Venue",
};

export default function GraphExplorer() {
  const { paperId } = useParams();
  const navigate = useNavigate();
  const wrap = useRef(null);
  const [size, setSize] = useState({ width: 640, height: 560 });
  const [graph, setGraph] = useState(null);
  const [paper, setPaper] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const measure = () => {
      if (!wrap.current) return;
      setSize({
        width: wrap.current.clientWidth,
        height: Math.max(480, wrap.current.clientHeight),
      });
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  useEffect(() => {
    let stopped = false;
    setError("");
    Promise.all([
      api(`/papers/${encodeURIComponent(paperId)}/graph`),
      api(`/papers/${encodeURIComponent(paperId)}`),
    ])
      .then(([graphBody, paperBody]) => {
        if (stopped) return;
        setGraph(graphBody);
        setPaper(paperBody);
      })
      .catch((err) => {
        if (!stopped) setError(err.message);
      });
    return () => {
      stopped = true;
    };
  }, [paperId]);

  const data = useMemo(() => graph || { nodes: [], links: [] }, [graph]);

  function openPaper(node) {
    if (node.kind !== "Paper") return;
    if (node.ref === paperId) return;
    navigate(`/papers/${encodeURIComponent(node.ref)}/graph`);
  }

  return (
    <div>
      <div className="mb-4 flex items-end justify-between gap-3">
        <div>
          <p className="text-sm text-mute">Related papers</p>
          <h1 className="mt-1 max-w-3xl font-serif text-3xl md:text-4xl">
            {paper?.title || "Related papers"}
          </h1>
        </div>
        {paper && (
          <Link className="text-sm text-teal" to={`/papers/${encodeURIComponent(paper.id)}`}>
            Back to paper
          </Link>
        )}
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div ref={wrap} className="h-[70vh] overflow-hidden rounded-2xl border border-line bg-panel shadow-card">
          {error && <p className="p-4 text-amber">{error}</p>}
          {graph && (
            <ForceGraph2D
              width={size.width}
              height={size.height}
              graphData={data}
              backgroundColor="#12141b"
              nodeLabel={(node) => `${KIND_LABELS[node.kind] || node.kind}: ${node.label}`}
              nodeColor={(node) => COLORS[node.kind] || "#f4efe6"}
              nodeRelSize={5}
              nodeVal={(node) => (node.seed ? 6 : 2)}
              linkColor={() => "#3a3f4a"}
              linkDirectionalArrowLength={3}
              linkDirectionalArrowRelPos={1}
              onNodeClick={openPaper}
            />
          )}
        </div>
        <aside className="rounded-2xl border border-line bg-panel p-5 shadow-card">
          <p className="text-sm text-mute">This paper</p>
          {paper ? (
            <>
              <h2 className="mt-2 font-serif text-2xl leading-snug">{paper.title}</h2>
              <p className="mt-3 text-sm leading-6 text-mute">{paper.summary || "No summary yet."}</p>
              <Link className="mt-3 inline-block text-sm text-teal" to={`/papers/${encodeURIComponent(paper.id)}`}>
                Full detail
              </Link>
            </>
          ) : error ? (
            <p className="mt-3 text-sm text-amber">{error}</p>
          ) : (
            <p className="mt-3 text-sm text-mute">Loading…</p>
          )}
          <h3 className="mt-6 text-sm text-mute">Nearby papers</h3>
          <ul className="mt-2 max-h-56 space-y-2 overflow-auto">
            {(graph?.nodes || [])
              .filter((node) => node.kind === "Paper" && !node.seed)
              .map((node) => (
                <li key={node.id}>
                  <button className="text-left text-sm hover:text-teal" onClick={() => openPaper(node)}>
                    {node.label}
                  </button>
                </li>
              ))}
          </ul>
          <ul className="mt-6 flex flex-wrap gap-2 text-[11px] text-mute">
            {Object.entries(COLORS).map(([kind, color]) => (
              <li key={kind} className="flex items-center gap-1">
                <span className="inline-block h-2 w-2 rounded-full" style={{ background: color }} />
                {KIND_LABELS[kind] || kind}
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </div>
  );
}
