import {
  BarChart3,
  Calendar,
  Check,
  FileText,
  Library,
  Lock,
  LogOut,
  Mail,
  Moon,
  Search,
  Sparkles,
  Sun,
  Upload,
  User,
} from "lucide-react";

const ICONS = {
  spark: Sparkles,
  upload: Upload,
  search: Search,
  books: Library,
  file: FileText,
  sun: Sun,
  moon: Moon,
  user: User,
  mail: Mail,
  lock: Lock,
  check: Check,
  chart: BarChart3,
  calendar: Calendar,
  out: LogOut,
};

const TONES = {
  teal: "bg-teal/15 text-teal",
  violet: "bg-violet/15 text-violet",
  amber: "bg-amber/15 text-amber",
  sky: "bg-sky/15 text-sky",
  rose: "bg-rose/15 text-rose",
  lime: "bg-lime/15 text-lime",
};

export function Icon({ name, className = "h-5 w-5" }) {
  const Glyph = ICONS[name] || Sparkles;
  return <Glyph className={className} strokeWidth={1.8} aria-hidden="true" />;
}

export function IconBadge({ name, tone = "teal", className = "" }) {
  return (
    <span
      className={`inline-flex h-11 w-11 items-center justify-center rounded-2xl ${TONES[tone] || TONES.teal} ${className}`}
    >
      <Icon name={name} />
    </span>
  );
}
