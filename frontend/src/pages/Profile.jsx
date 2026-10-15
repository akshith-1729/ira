import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import Button from "../components/ui/Button";
import Chip from "../components/ui/Chip";
import Panel from "../components/ui/Panel";
import Stat from "../components/ui/Stat";

function initials(user) {
  const source = user?.display_name || user?.email || "";
  const parts = source.split(/[\s@._-]+/).filter(Boolean);
  return (parts[0]?.[0] || "?").toUpperCase() + (parts[1]?.[0] || "").toUpperCase();
}

function when(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

export default function Profile() {
  const navigate = useNavigate();
  const { user, setUser } = useAuth();
  const [name, setName] = useState(user?.display_name || "");
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    setName(user?.display_name || "");
  }, [user?.display_name]);

  if (user === undefined) return <p className="text-mute">Loading…</p>;
  if (!user) {
    return (
      <div className="rise">
        <h1 className="font-serif text-5xl">Profile</h1>
        <p className="mt-4 text-mute">Sign in to see your account.</p>
        <Link className="mt-6 inline-block text-teal" to="/login">
          Sign in
        </Link>
      </div>
    );
  }

  async function saveName(event) {
    event.preventDefault();
    setBusy("name");
    setError("");
    setNote("");
    try {
      const body = await api("/auth/profile", {
        method: "PATCH",
        body: JSON.stringify({ display_name: name }),
      });
      setUser(body);
      setNote("Name saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function savePassword(event) {
    event.preventDefault();
    setBusy("password");
    setError("");
    setNote("");
    try {
      await api("/auth/password", {
        method: "POST",
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      setCurrent("");
      setNext("");
      setNote("Password updated.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function signOut() {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    setUser(null);
    navigate("/");
  }

  return (
    <div className="rise">
      <div className="flex flex-wrap items-center gap-5">
        <div className="pop flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-teal via-sky to-violet font-serif text-3xl text-ink">
          {initials(user)}
        </div>
        <div>
          <h1 className="font-serif text-5xl leading-none">{user.display_name || "Your profile"}</h1>
          <p className="mt-3 text-[17px] text-mute">{user.email}</p>
          <Chip className="mt-2" tone={user.verified ? "lime" : "amber"}>
            {user.verified ? "Email confirmed" : "Email not confirmed"}
          </Chip>
        </div>
      </div>

      <dl className="mt-8 grid gap-4 sm:grid-cols-3">
        <Stat icon="books" tone="teal" label="Papers" value={user.papers || 0} />
        <Stat icon="chart" tone="violet" label="Analyses" value={user.analyses || 0} />
        <Stat icon="calendar" tone="amber" label="Joined" value={when(user.created_at) || "—"} />
      </dl>

      <Panel className="mt-8 max-w-xl" tone="teal" title="Name">
      <form onSubmit={saveName}>
        <input
          className="field mt-4 w-full rounded-2xl border border-line bg-panel px-4 py-3 text-[17px] outline-none"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="How should we address you?"
        />
        <Button className="mt-4" disabled={busy === "name"} type="submit">
          {busy === "name" ? "Saving…" : "Save name"}
        </Button>
      </form>
      </Panel>

      <Panel className="mt-6 max-w-xl" tone="violet" title="Password">
      <form onSubmit={savePassword}>
        <input
          className="field mt-4 w-full rounded-2xl border border-line bg-panel px-4 py-3 outline-none"
          type="password"
          autoComplete="current-password"
          placeholder="Current password"
          value={current}
          onChange={(event) => setCurrent(event.target.value)}
        />
        <input
          className="field mt-3 w-full rounded-2xl border border-line bg-panel px-4 py-3 outline-none"
          type="password"
          autoComplete="new-password"
          placeholder="New password"
          value={next}
          onChange={(event) => setNext(event.target.value)}
        />
        <Button className="mt-4" tone="outline" disabled={busy === "password"} type="submit">
          {busy === "password" ? "Updating…" : "Update password"}
        </Button>
      </form>
      </Panel>

      {note && <p className="mt-6 text-sm text-teal">{note}</p>}
      {error && <p className="mt-6 text-sm text-amber">{error}</p>}

      <div className="mt-8 flex flex-wrap gap-3">
        <Button to="/library" tone="amber">
          Your papers
        </Button>
        <Button tone="rose" onClick={signOut} type="button">
          Sign out
        </Button>
      </div>
    </div>
  );
}
