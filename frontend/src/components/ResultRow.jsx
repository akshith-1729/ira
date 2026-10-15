import { Link } from "react-router-dom";
import Button from "./ui/Button";
import Chip from "./ui/Chip";

export default function ResultRow({ row, onAnalyze, looking }) {
  const already = row.source === "graph";
  return (
    <li
      className={`rounded-[1.35rem] border bg-panel p-6 shadow-card transition duration-200 hover:-translate-y-0.5 ${
        already ? "border-teal/50" : "border-violet/30"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Chip tone={already ? "teal" : "violet"}>{already ? "Already analyzed" : "Not added yet"}</Chip>
        {row.paper.year ? <Chip tone="sky">{row.paper.year}</Chip> : null}
      </div>
      {already ? (
        <Link
          className="mt-3 block font-serif text-3xl leading-snug transition hover:text-teal"
          to={`/papers/${encodeURIComponent(row.paper.id)}`}
        >
          {row.paper.title}
        </Link>
      ) : (
        <p className="mt-3 font-serif text-3xl leading-snug">{row.paper.title}</p>
      )}
      {row.why && <p className="mt-3 max-w-3xl text-[17px] leading-7 text-mute">{row.why}</p>}
      {!row.why && row.paper.summary && (
        <p className="mt-3 max-w-3xl text-[17px] leading-7 text-mute">{row.paper.summary}</p>
      )}
      {onAnalyze && !already && (
        <Button
          className="mt-5"
          tone="outline"
          disabled={Boolean(looking)}
          onClick={() => onAnalyze(row.paper.id)}
        >
          {looking === row.paper.id ? "Analyzing…" : "Analyze this paper"}
        </Button>
      )}
    </li>
  );
}
