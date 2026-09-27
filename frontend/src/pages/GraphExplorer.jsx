import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import ForceGraph2D from "react-force-graph-2d";
import { api } from "../api";

const COLORS = {
  Paper: "#eceae4",
  Author: "#9a958b",
  Topic: "#3dbea5",
  Gap: "#e0a15a",
  Direction: "#7eb6ff",
  Venue: "#d2a4ff",
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
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div ref={wrap} className="h-[70vh] overflow-hidden rounded-lg border border-line bg-panel">
        {error && <p className="p-4 text-amber">{error}</p>}
        {graph && (
          <ForceGraph2D
            width={size.width}
            height={size.height}
            graphData={data}
            backgroundColor="#14161c"
            nodeLabel={(node) => `${node.kind}: ${node.label}`}
            nodeColor={(node) => COLORS[node.kind] || "#eceae4"}
            nodeRelSize={5}
            nodeVal={(node) => (node.seed ? 6 : 2)}
            linkColor={() => "#3a3f4a"}
            linkDirectionalArrowLength={3}
            linkDirectionalArrowRelPos={1}
            onNodeClick={openPaper}
          />
        )}
      </div>
      <aside className="rounded-lg border border-line bg-panel p-4">
        <p className="text-xs uppercase tracking-[0.16em] text-teal">Paper</p>
        {paper ? (
          <>
            <h1 className="mt-2 font-serif text-2xl leading-snug">{paper.title}</h1>
            <p className="mt-2 text-sm leading-6 text-mute">{paper.summary || "No summary yet."}</p>
            <Link className="mt-3 inline-block text-sm text-teal" to={`/papers/${encodeURIComponent(paper.id)}`}>
              Full detail
            </Link>
          </>
        ) : error ? (
          <p className="mt-3 text-sm text-amber">{error}</p>
        ) : (
          <p className="mt-3 text-sm text-mute">Loading…</p>
        )}
        <h2 className="mt-6 text-xs uppercase tracking-[0.14em] text-mute">Citation neighbors</h2>
        <ul className="mt-2 space-y-2">
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
              {kind}
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
