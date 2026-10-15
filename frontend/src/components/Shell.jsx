import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { AuthProvider, useAuth } from "../auth";
import { HealthProvider, useHealth } from "../health";
import { Icon } from "./Icons";

export default function Shell() {
  return (
    <HealthProvider>
      <AuthProvider>
        <Frame />
      </AuthProvider>
    </HealthProvider>
  );
}

function Frame() {
  const health = useHealth();
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [night, setNight] = useState(() => document.documentElement.classList.contains("dark"));

  const links = [
    { to: "/", label: "Submit", end: true, icon: "upload", active: "bg-teal text-ink", idle: "text-teal" },
    { to: "/search", label: "Search", icon: "search", active: "bg-violet text-ink", idle: "text-violet" },
    ...(user ? [{ to: "/library", label: "Your papers", icon: "books", active: "bg-amber text-ink", idle: "text-amber" }] : []),
  ];

  async function signOut() {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    setUser(null);
    navigate("/");
  }

  function toggleTheme() {
    const next = night ? "light" : "dark";
    document.documentElement.classList.remove("light", "dark");
    document.documentElement.classList.add(next);
    localStorage.setItem("ira-theme", next);
    setNight(next === "dark");
  }

  return (
    <div className="min-h-full font-sans text-cream lg:flex">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-line bg-panel/80 px-4 py-5 backdrop-blur-xl lg:flex">
        <Brand />
        <Nav links={links} stacked />
        <div className="mt-auto space-y-3">
          <div className="flex flex-wrap gap-1.5">
            <Status on={health?.neo4j === "up"} label="Library" />
            <Status on={health?.postgres === "up"} label="Jobs" />
            <Status on={health?.grobid === "up"} label="PDF" />
          </div>
          <Account user={user} night={night} onTheme={toggleTheme} onSignOut={signOut} />
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 border-b border-line/80 bg-ink/85 backdrop-blur-xl lg:hidden">
          <div className="flex items-center gap-2 px-4 py-3">
            <Brand compact />
            <div className="ml-auto">
              <Account user={user} night={night} onTheme={toggleTheme} onSignOut={signOut} compact />
            </div>
          </div>
          <div className="px-3 pb-3">
            <Nav links={links} />
          </div>
        </header>
        <main className={`min-w-0 px-4 py-8 sm:px-8 lg:px-10 lg:py-10 ${wash(location.pathname)}`}>
          <div key={location.pathname} className="rise mx-auto max-w-6xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

function wash(path) {
  if (path.startsWith("/search")) return "bg-gradient-to-b from-violet/15 via-transparent to-transparent";
  if (path.startsWith("/library")) return "bg-gradient-to-b from-amber/15 via-transparent to-transparent";
  if (path.startsWith("/papers")) return "bg-gradient-to-b from-sky/15 via-transparent to-transparent";
  if (path.startsWith("/login") || path.startsWith("/profile")) return "bg-gradient-to-b from-sky/15 via-transparent to-transparent";
  if (path.startsWith("/register")) return "bg-gradient-to-b from-violet/15 via-transparent to-transparent";
  if (path.startsWith("/verify")) return "bg-gradient-to-b from-lime/15 via-transparent to-transparent";
  return "bg-gradient-to-b from-teal/15 via-transparent to-transparent";
}

function Brand({ compact = false }) {
  return (
    <NavLink to="/" className="flex items-center gap-2">
      <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-teal via-sky to-violet text-ink shadow-card">
        <Icon name="spark" className="h-5 w-5" />
      </span>
      <span className={`font-serif tracking-tight ${compact ? "text-2xl" : "text-3xl"}`}>Ira</span>
    </NavLink>
  );
}

function Nav({ links, stacked = false }) {
  return (
    <nav className={stacked ? "mt-8 flex flex-col gap-1.5" : "flex gap-1.5 overflow-x-auto"}>
      {links.map((link) => (
        <NavLink
          key={link.to}
          to={link.to}
          end={link.end}
          className={({ isActive }) =>
            `inline-flex items-center gap-2 rounded-2xl px-3 py-2.5 text-sm transition duration-200 ${
              isActive ? link.active : `${link.idle} hover:bg-lift`
            }`
          }
        >
          <Icon name={link.icon} className="h-4 w-4" />
          {link.label}
        </NavLink>
      ))}
    </nav>
  );
}

function Account({ user, night, onTheme, onSignOut, compact = false }) {
  return (
    <div className={`flex items-center gap-2 ${compact ? "" : "rounded-2xl border border-line bg-ink/40 p-2"}`}>
      <button
        className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-line bg-panel text-mute transition hover:text-cream"
        onClick={onTheme}
        type="button"
        title={night ? "Light" : "Dark"}
      >
        <Icon name={night ? "sun" : "moon"} className="h-4 w-4" />
      </button>
      {user ? (
        <>
          <NavLink
            className="flex h-9 min-w-0 flex-1 items-center gap-2 rounded-xl px-1 text-sm"
            title={user.display_name || user.email}
            to="/profile"
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-teal to-violet text-xs font-medium text-ink">
              {(user.display_name || user.email || "?").slice(0, 1).toUpperCase()}
            </span>
            {!compact && (
              <span className="truncate text-cream">{user.display_name || "Profile"}</span>
            )}
          </NavLink>
          <button className="inline-flex h-9 w-9 items-center justify-center rounded-xl text-rose" onClick={onSignOut} type="button" title="Sign out">
            <Icon name="out" className="h-4 w-4" />
          </button>
        </>
      ) : user === null ? (
        <NavLink className="inline-flex items-center gap-1.5 px-2 text-sm text-teal" to="/login">
          <Icon name="user" className="h-4 w-4" />
          Sign in
        </NavLink>
      ) : null}
    </div>
  );
}

function Status({ on, label }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[11px] ${
        on ? "border-line text-mute" : "border-amber/40 text-amber"
      }`}
      title={on ? `${label} ready` : `${label} offline`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${on ? "bg-teal" : "bg-amber"}`} />
      {label}
    </span>
  );
}
