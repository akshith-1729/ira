import { Icon } from "../Icons";

const WASH = {
  teal: "from-teal via-sky to-violet",
  violet: "from-violet via-sky to-teal",
  sky: "from-sky via-teal to-lime",
  lime: "from-lime via-teal to-sky",
  amber: "from-amber via-rose to-violet",
};

export default function AuthFrame({ tone = "teal", icon = "user", title, lede, children }) {
  return (
    <div className="grid overflow-hidden rounded-[1.6rem] border border-line bg-panel shadow-card lg:grid-cols-[0.85fr_1.15fr]">
      <div className={`bg-gradient-to-br ${WASH[tone] || WASH.teal} p-8 text-ink sm:p-10`}>
        <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-ink/15">
          <Icon name={icon} className="h-6 w-6" />
        </span>
        <h1 className="mt-6 font-serif text-4xl leading-[1.05] sm:text-5xl">{title}</h1>
        {lede ? <p className="mt-4 max-w-sm text-[17px] leading-7 text-ink/80">{lede}</p> : null}
      </div>
      <div className="p-6 sm:p-10">{children}</div>
    </div>
  );
}
