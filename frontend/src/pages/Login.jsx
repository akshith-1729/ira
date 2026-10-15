import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import AuthFrame from "../components/ui/AuthFrame";
import Button from "../components/ui/Button";

export default function Login() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const user = await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setUser(user);
      navigate("/");
    } catch (err) {
      if (err.status === 403) {
        navigate("/verify", { state: { email } });
        return;
      }
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthFrame tone="sky" icon="user" title="Sign in" lede="Use the email and password for your account.">
      <form onSubmit={submit}>
        <label className="block text-sm text-mute" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          className="mt-2 w-full rounded-2xl border border-line bg-panel px-4 py-3 text-[17px] outline-none focus:border-teal"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
        <label className="mt-5 block text-sm text-mute" htmlFor="password">
          Password
        </label>
        <input
          id="password"
          className="mt-2 w-full rounded-2xl border border-line bg-panel px-4 py-3 text-[17px] outline-none focus:border-teal"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
        {error && <p className="mt-4 text-sm text-amber">{error}</p>}
        <Button className="mt-6" disabled={busy} type="submit">
          {busy ? "Signing in…" : "Sign in"}
        </Button>
        <p className="mt-6 text-sm text-mute">
          No account yet?{" "}
          <Button to="/register" tone="ghost" className="px-0 py-0 shadow-none">
            Create one
          </Button>
        </p>
      </form>
    </AuthFrame>
  );
}
