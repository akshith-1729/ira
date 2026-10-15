import { IconBadge } from "./Icons";

const WASH = {
  teal: "from-teal/25 via-sky/10",
  violet: "from-violet/25 via-sky/10",
  amber: "from-amber/25 via-rose/10",
  sky: "from-sky/25 via-teal/10",
  rose: "from-rose/20 via-amber/10",
  lime: "from-lime/25 via-teal/10",
};

export default function PageHero({ kicker, title, children, icon, tone = "teal" }) {
  return (
    <header className={`rounded-[1.6rem] border border-line/70 bg-gradient-to-br ${WASH[tone] || WASH.teal} to-panel p-6 shadow-card sm:p-8`}>
      {icon ? <IconBadge name={icon} tone={tone} /> : null}
      {kicker ? <p className="mt-4 text-sm text-teal">{kicker}</p> : null}
      <h1 className="mt-4 max-w-3xl font-serif text-[2.4rem] leading-[1.05] tracking-tight sm:text-5xl">{title}</h1>
      {children ? <div className="mt-4 max-w-xl text-[17px] leading-7 text-mute">{children}</div> : null}
    </header>
  );
}
