const STEPS = ["queued", "parsing", "metadata", "citations", "embedding", "summary", "gaps", "done"];

const LABELS = {
  queued: "Queued",
  parsing: "Reading the PDF",
  metadata: "Looking up the paper",
  citations: "Reading references",
  embedding: "Saving the paper",
  summary: "Writing the summary",
  gaps: "Finding what’s missing",
  done: "Done",
};

export default function ProgressRail({ progress, status }) {
  const current = STEPS.indexOf(progress);
  const activeLabel = LABELS[progress] || "Working";
  const running = status === "queued" || status === "running";
  const failed = status === "error";
  const pct = current < 0 ? 8 : Math.round(((current + 1) / STEPS.length) * 100);

  return (
    <div className="mt-4">
      <div className="flex items-center gap-3">
        {running && (
          <span className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-line border-t-teal" />
        )}
        <p className={`font-serif text-xl ${failed ? "text-rose" : ""}`}>
          {failed ? "Analysis failed" : activeLabel}
        </p>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-line">
        <div
          className={`h-full rounded-full transition-all duration-500 ${failed ? "bg-rose" : "bg-gradient-to-r from-teal via-sky to-violet"}`}
          style={{ width: `${failed ? 100 : pct}%` }}
        />
      </div>
      <ol className="mt-4 flex flex-wrap gap-2">
        {STEPS.filter((step) => step !== "queued").map((step, index) => {
          const reached = failed ? false : current >= index + 1;
          const active = progress === step;
          return (
            <li
              key={step}
              className={`rounded-full border px-3 py-1 text-xs ${
                failed && active
                  ? "border-rose text-rose"
                  : active
                    ? "border-teal bg-teal/10 text-teal"
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
    </div>
  );
}
