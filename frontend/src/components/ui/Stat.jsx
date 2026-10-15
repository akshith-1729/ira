import { IconBadge } from "../Icons";

export default function Stat({ icon = "spark", tone = "teal", label, value, className = "" }) {
  return (
    <div className={`rounded-[1.35rem] border border-line bg-panel p-5 shadow-card ${className}`}>
      <IconBadge name={icon} tone={tone} />
      <p className="mt-4 text-sm text-mute">{label}</p>
      <p className="mt-1 font-serif text-2xl leading-tight">{value}</p>
    </div>
  );
}
