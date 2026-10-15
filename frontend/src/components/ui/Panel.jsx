import { IconBadge } from "../Icons";

const EDGES = {
  teal: "from-teal via-sky to-transparent",
  violet: "from-violet via-sky to-transparent",
  amber: "from-amber via-rose to-transparent",
  sky: "from-sky via-teal to-transparent",
  rose: "from-rose via-amber to-transparent",
  lime: "from-lime via-teal to-transparent",
};

export default function Panel({ tone = "teal", icon, kicker, title, children, className = "" }) {
  return (
    <section className={`overflow-hidden rounded-[1.35rem] border border-line bg-panel shadow-card ${className}`}>
      <div className={`h-1.5 bg-gradient-to-r ${EDGES[tone] || EDGES.teal}`} />
      <div className="p-6 sm:p-8">
        {icon ? <IconBadge name={icon} tone={tone} /> : null}
        {kicker ? <p className="mt-4 text-sm text-mute">{kicker}</p> : null}
        {title ? <h2 className="mt-2 font-serif text-3xl leading-tight">{title}</h2> : null}
        {children}
      </div>
    </section>
  );
}
