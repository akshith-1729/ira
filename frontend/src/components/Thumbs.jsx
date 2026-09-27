import { api } from "../api";

export default function Thumbs({ feedbackId }) {
  if (!feedbackId) return null;
  const send = async (rating) => {
    await api(`/feedback/${feedbackId}`, {
      method: "POST",
      body: JSON.stringify({ rating }),
    });
  };
  return (
    <div className="mt-3 flex items-center gap-2 text-xs text-mute">
      <span>Was this useful?</span>
      <button className="rounded border border-line px-2 py-1 hover:text-cream" onClick={() => send("up")}>
        Up
      </button>
      <button className="rounded border border-line px-2 py-1 hover:text-cream" onClick={() => send("down")}>
        Down
      </button>
    </div>
  );
}
