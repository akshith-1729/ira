const STEPS = ["parsing", "metadata", "citations", "embedding", "summary", "gaps", "done"];

const LABELS = {
  parsing: "Parse",
  metadata: "Metadata",
  citations: "Citations",
  embedding: "Embed",
  summary: "Summary",
  gaps: "Gaps",
  done: "Done",
};

export default function ProgressRail({ progress, status }) {
  const current = STEPS.indexOf(progress);
  return (
    <ol className="mt-6 flex flex-wrap gap-2">
      {STEPS.map((step, index) => {
        const reached = status === "error" ? false : current >= index;
        const active = progress === step;
        return (
          <li
            key={step}
            className={`rounded-full border px-3 py-1 text-xs tracking-wide ${
              active
                ? "border-teal text-teal"
                : reached
                  ? "border-line text-cream"
                  : "border-line text-mute"
            }`}
          >
            {LABELS[step]}
          </li>
        );
      })}
    </ol>
  );
}
