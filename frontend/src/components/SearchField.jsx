import { Icon } from "./Icons";

export default function SearchField({
  value,
  onChange,
  onSubmit,
  placeholder,
  action,
  disabled,
  busy,
}) {
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit?.(event);
      }}
      className="mt-0"
    >
      <div className="flex flex-col gap-3 rounded-[1.35rem] border border-line bg-panel p-2 shadow-card transition focus-within:border-violet/60 sm:flex-row sm:items-center sm:p-2.5">
        <Icon name="search" className="ml-3 hidden h-5 w-5 text-violet sm:block" />
        <input
          className="min-h-[3.25rem] flex-1 bg-transparent px-4 text-[17px] outline-none placeholder:text-mute/70"
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          autoFocus
        />
        <button
          className="inline-flex items-center justify-center gap-2 rounded-full bg-violet px-6 py-3 text-sm font-medium text-ink transition hover:brightness-110 disabled:opacity-40"
          disabled={disabled || busy}
          type="submit"
        >
          <Icon name="search" className="h-4 w-4" />
          {busy ? "Searching…" : action || "Search"}
        </button>
      </div>
    </form>
  );
}
