import { Link } from "react-router-dom";

const TONES = {
  teal: "bg-teal text-ink hover:brightness-110",
  violet: "bg-violet text-ink hover:brightness-110",
  sky: "bg-sky text-ink hover:brightness-110",
  amber: "bg-amber text-ink hover:brightness-110",
  outline: "border border-line bg-panel text-cream hover:border-teal",
  rose: "border border-rose/40 bg-rose/10 text-rose hover:border-rose",
  ghost: "text-teal hover:text-cream",
};

export default function Button({ to, tone = "teal", className = "", children, ...props }) {
  const classes = `inline-flex items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium shadow-card transition duration-200 hover:-translate-y-0.5 disabled:translate-y-0 disabled:opacity-40 ${TONES[tone] || TONES.teal} ${className}`;
  if (to) {
    return (
      <Link className={classes} to={to} {...props}>
        {children}
      </Link>
    );
  }
  return (
    <button className={classes} {...props}>
      {children}
    </button>
  );
}
