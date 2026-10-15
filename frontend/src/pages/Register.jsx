import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { emailProblem } from "../emailCheck";
import AuthFrame from "../components/ui/AuthFrame";
import Button from "../components/ui/Button";

export default function Register() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [confirm, setConfirm] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const emailNote = email ? emailProblem(email) : "";
  const confirmNote = confirm && confirm.trim().toLowerCase() !== email.trim().toLowerCase() ? "Those emails do not match." : "";

  async function submit(event) {
    event.preventDefault();
    const problem = emailProblem(email);
    if (problem) {
      setError(problem);
      return;
    }
    if (confirm.trim().toLowerCase() !== email.trim().toLowerCase()) {
      setError("Those emails do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Use at least 8 characters.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const created = await api("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      navigate("/verify", { state: created });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthFrame
      tone="violet"
      icon="mail"
      title="Create an account"
      lede="We check that the address is real, then ask you to confirm it before you can sign in."
    >
      <form onSubmit={submit}>
        <label className="block text-sm text-mute" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          className="field mt-2 w-full rounded-2xl border border-line bg-panel px-4 py-3 text-[17px] outline-none"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
        {emailNote && <p className="mt-2 text-sm text-amber">{emailNote}</p>}
        <label className="mt-5 block text-sm text-mute" htmlFor="confirm">
          Confirm email
        </label>
        <input
          id="confirm"
          className="field mt-2 w-full rounded-2xl border border-line bg-panel px-4 py-3 text-[17px] outline-none"
          type="email"
          autoComplete="email"
          value={confirm}
          onChange={(event) => setConfirm(event.target.value)}
          required
        />
        {confirmNote && <p className="mt-2 text-sm text-amber">{confirmNote}</p>}
        <label className="mt-5 block text-sm text-mute" htmlFor="password">
          Password
        </label>
        <input
          id="password"
          className="field mt-2 w-full rounded-2xl border border-line bg-panel px-4 py-3 text-[17px] outline-none"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
        <div className="mt-3 h-1 overflow-hidden rounded-full bg-line">
          <div
            className="h-full rounded-full bg-teal transition-all duration-300"
            style={{ width: `${Math.min(100, (password.length / 8) * 100)}%` }}
          />
        </div>
        <p className="mt-2 text-sm text-mute">At least 8 characters.</p>
        {error && <p className="mt-4 text-sm text-amber">{error}</p>}
        <Button className="mt-6" disabled={busy} type="submit">
          {busy ? "Checking…" : "Create account"}
        </Button>
        <p className="mt-6 text-sm text-mute">
          Already have an account?{" "}
          <Button to="/login" tone="ghost" className="px-0 py-0 shadow-none">
            Sign in
          </Button>
        </p>
      </form>
    </AuthFrame>
  );
}
