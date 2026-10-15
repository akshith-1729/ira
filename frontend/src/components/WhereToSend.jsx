import { useState } from "react";
import VenueCard from "./VenueCard";

export default function WhereToSend({ advice }) {
  const [open, setOpen] = useState(false);
  if (!advice) return null;
  const shortlist = advice.shortlist?.length ? advice.shortlist : (advice.venues || []).slice(0, 5);
  const rest = (advice.venues || []).filter((row) => !shortlist.some((item) => item.id === row.id));

  return (
    <section id="send" className="mt-16 scroll-mt-28 border-t border-line pt-10">
      <h2 className="font-serif text-3xl md:text-4xl">Where to send this paper</h2>
      <p className="mt-3 max-w-xl text-[17px] leading-7 text-mute">
        For this paper, not a field in general. Not a promise you will be accepted.
      </p>

      {shortlist.length > 0 && (
        <div className="mt-8">
          <h3 className="font-serif text-2xl">Try these first</h3>
          <div className="mt-5 grid gap-5 md:grid-cols-2">
            {shortlist.map((venue, index) => (
              <div key={venue.id} className={index === 0 ? "md:col-span-2" : ""}>
                <VenueCard venue={venue} rank={index + 1} featured={index === 0} />
              </div>
            ))}
          </div>
        </div>
      )}

      {rest.length > 0 && (
        <div className="mt-8">
          <button
            type="button"
            className="text-sm text-teal transition hover:text-cream"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? "Hide more options" : `More options (${rest.length})`}
          </button>
          {open && (
            <div className="mt-4 space-y-2 rounded-[1.35rem] border border-line bg-lift/30 p-3 md:p-4">
              {rest.map((venue, index) => (
                <VenueCard key={venue.id} venue={venue} rank={index + 6} compact />
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
