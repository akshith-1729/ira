function scopusLabel(value) {
  if (value === "yes") return "Yes";
  if (value === "no") return "No";
  return "Not listed";
}

function kindLabel(kind) {
  if (kind === "journal") return "Journal";
  if (kind === "conference") return "Conference";
  if (kind === "repository") return "Preprint";
  return kind || "";
}

function formatAcceptance(venue) {
  if (venue.acceptance_rate == null || !venue.acceptance_source) return null;
  const percent = `${Math.round(venue.acceptance_rate * 100)}%`;
  const year = venue.acceptance_year ? ` (${venue.acceptance_year})` : "";
  return `${percent}${year} · ${venue.acceptance_source}`;
}

function whyLine(venue) {
  return (venue.fit?.reasons || []).slice(0, 3).join(", ");
}

export default function VenueCard({ venue, rank, featured = false, compact = false }) {
  const why = whyLine(venue);
  const days = venue.avg_review_days;
  const accept = formatAcceptance(venue);

  if (compact) {
    return (
      <article className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-2xl border border-line bg-panel px-4 py-3">
        {rank != null && <span className="w-7 shrink-0 text-sm text-mute">{rank}</span>}
        <div className="min-w-[10rem] flex-1">
          <h3 className="font-serif text-xl leading-tight">{venue.name}</h3>
          {why && <p className="mt-1 text-sm text-mute">{why}</p>}
        </div>
        <span className="rounded-full border border-line px-2.5 py-1 text-xs text-mute">{kindLabel(venue.kind)}</span>
        <span className="rounded-full bg-lift px-2.5 py-1 text-xs">Scopus {scopusLabel(venue.scopus)}</span>
        {days != null && days > 0 && <span className="text-sm text-mute">~{days} days</span>}
        {venue.homepage && (
          <a
            className="text-sm text-teal transition hover:text-cream"
            href={venue.homepage}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open site
          </a>
        )}
      </article>
    );
  }

  return (
    <article
      className={`group flex h-full flex-col rounded-[1.35rem] border bg-panel shadow-card transition duration-200 hover:-translate-y-0.5 hover:border-teal/40 p-6 ${
        featured ? "border-teal/50" : "border-line"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          {rank != null && (
            <p className={`font-serif ${featured ? "text-teal text-xl" : "text-mute text-sm"}`}>{rank}</p>
          )}
          <h3 className={`mt-1 font-serif leading-tight ${featured ? "text-3xl md:text-4xl" : "text-2xl"}`}>
            {venue.name}
          </h3>
        </div>
        <span className="shrink-0 rounded-full border border-line px-2.5 py-1 text-xs text-mute">
          {kindLabel(venue.kind)}
        </span>
      </div>

      <div className="mt-4 flex flex-wrap gap-2 text-xs">
        <span className="rounded-full bg-lift px-2.5 py-1 text-cream">Scopus {scopusLabel(venue.scopus)}</span>
        {venue.open_access === "yes" && (
          <span className="rounded-full bg-lift px-2.5 py-1 text-cream">Open access</span>
        )}
        {venue.open_access === "no" && (
          <span className="rounded-full bg-lift px-2.5 py-1 text-mute">Not open access</span>
        )}
      </div>

      <dl className={`mt-5 grid gap-3 ${featured ? "sm:grid-cols-2" : ""}`}>
        {days != null && (
          <div>
            <dt className="text-sm text-mute">Typical review</dt>
            <dd className={`mt-0.5 ${featured ? "font-serif text-3xl leading-none" : "text-[17px]"}`}>
              {days === 0 ? "None (preprint)" : `~${days} days`}
            </dd>
          </div>
        )}
        {venue.publisher && (
          <div>
            <dt className="text-sm text-mute">Publisher</dt>
            <dd className="mt-0.5 text-[17px]">{venue.publisher}</dd>
          </div>
        )}
      </dl>

      {accept && <p className="mt-3 text-sm text-mute">Acceptance {accept}</p>}
      {why && <p className="mt-3 text-sm leading-6 text-mute">Matches this paper: {why}</p>}

      {venue.homepage && (
        <a
          className={`mt-auto inline-flex w-fit pt-6 text-sm font-medium transition ${
            featured
              ? "rounded-full bg-teal px-4 py-2 text-ink hover:brightness-110"
              : "text-teal hover:text-cream"
          }`}
          href={venue.homepage}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open site
        </a>
      )}
    </article>
  );
}
