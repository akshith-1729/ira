import { IconBadge } from "../Icons";

export default function Empty({ icon = "books", tone = "amber", children }) {
  return (
    <div className="flex items-start gap-4 rounded-[1.35rem] border border-dashed border-line bg-panel p-6 text-[17px] leading-7 text-mute shadow-card">
      <IconBadge name={icon} tone={tone} />
      <span>{children}</span>
    </div>
  );
}
