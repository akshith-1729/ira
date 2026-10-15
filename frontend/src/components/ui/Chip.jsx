const TONES = {
  teal: "bg-teal/15 text-teal",
  violet: "bg-violet/15 text-violet",
  amber: "bg-amber/15 text-amber",
  sky: "bg-sky/15 text-sky",
  rose: "bg-rose/15 text-rose",
  lime: "bg-lime/15 text-lime",
};

export default function Chip({ tone = "teal", children, className = "", ...props }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${TONES[tone] || TONES.teal} ${className}`} {...props}>
      {children}
    </span>
  );
}
