import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import AuthFrame from "../components/ui/AuthFrame";
import Button from "../components/ui/Button";

export default function Verify() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setUser } = useAuth();
  const incoming = location.state || {};
  const [email, setEmail] = useState(incoming.email || "");
  const [code, setCode] = useState("");
  const [shown, setShown] = useState(incoming.delivery === "screen" ? incoming.code || "" : "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const user = await api("/auth/verify", {
        method: "POST",
        body: JSON.stringify({ email, code }),
      });
      setUser(user);
      navigate("/profile");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setError("");
    try {
      const body = await api("/auth/verify/send", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setShown(body.delivery === "screen" ? body.code : "");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <AuthFrame
      tone="lime"
      icon="check"
      title="Confirm your email"
      lede="Enter the 6-digit code for this address. It expires in 15 minutes."
    >
      {shown && (
        <p className="mb-6 rounded-2xl border border-teal/40 bg-teal/10 px-5 py-4 text-[17px]">
          Mail is not set up on this computer, so the code is shown here once:{" "}
          <span className="font-medium tracking-[0.2em]">{shown}</span>
        </p>
      )}
      <form onSubmit={submit}>
        <label className="block text-sm text-mute" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          className="field mt-2 w-full rounded-2xl border border-line bg-panel px-4 py-3 text-[17px] outline-none"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
        <label className="mt-5 block text-sm text-mute" htmlFor="code">
          Code
        </label>
        <input
          id="code"
          className="field mt-2 w-full rounded-2xl border border-line bg-panel px-4 py-3 text-[17px] tracking-[0.3em] outline-none"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          value={code}
          onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
          required
        />
        {error && <p className="mt-4 text-sm text-amber">{error}</p>}
        <div className="mt-6 flex flex-wrap items-center gap-4">
          <Button disabled={busy || code.length !== 6} type="submit">
            {busy ? "Checking…" : "Confirm"}
          </Button>
          <Button tone="ghost" className="px-0 shadow-none" onClick={resend} type="button">
            Send a new code
          </Button>
        </div>
      </form>
    </AuthFrame>
  );
}
