import { useState } from "react";
import { api } from "../api";

export default function Thumbs({ feedbackId }) {
  const [choice, setChoice] = useState("");
  if (!feedbackId) return null;

  const send = async (rating) => {
    setChoice(rating);
    await api(`/feedback/${feedbackId}`, {
      method: "POST",
      body: JSON.stringify({ rating }),
    }).catch(() => setChoice(""));
  };

  return (
    <div className="mt-4 flex items-center gap-2 text-xs text-mute">
      <span>Useful?</span>
      <button
        className={`rounded-full border px-3 py-1 transition ${
          choice === "up" ? "border-teal text-teal" : "border-line hover:text-cream"
        }`}
        onClick={() => send("up")}
        type="button"
      >
        Yes
      </button>
      <button
        className={`rounded-full border px-3 py-1 transition ${
          choice === "down" ? "border-amber text-amber" : "border-line hover:text-cream"
        }`}
        onClick={() => send("down")}
        type="button"
      >
        No
      </button>
    </div>
  );
}
