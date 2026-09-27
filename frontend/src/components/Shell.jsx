import { NavLink, Outlet } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api";

const links = [
  { to: "/", label: "Ingest", end: true },
  { to: "/search", label: "Search" },
];

export default function Shell() {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    let stopped = false;
    const load = () => {
      api("/health")
        .then((body) => {
          if (!stopped) setHealth(body);
        })
        .catch(() => {
          if (!stopped) setHealth({ status: "down", neo4j: "down", postgres: "down", grobid: "down" });
        });
    };
    load();
    const timer = window.setInterval(load, 15000);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="min-h-full bg-ink text-cream font-sans">
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-6 py-4">
          <div>
            <p className="font-serif text-xl tracking-tight">Research Assistant</p>
            <p className="text-xs uppercase tracking-[0.16em] text-mute">Citation graph · local</p>
          </div>
          <nav className="flex items-center gap-5 text-sm">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  isActive ? "text-teal" : "text-mute hover:text-cream"
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
          <p className="text-xs text-mute">
            <Dot on={health?.neo4j === "up"} /> Neo4j
            <span className="mx-2 text-line">/</span>
            <Dot on={health?.postgres === "up"} /> Postgres
            <span className="mx-2 text-line">/</span>
            <Dot on={health?.grobid === "up"} /> GROBID
          </p>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}

function Dot({ on }) {
  return (
    <span
      className={`mr-1 inline-block h-1.5 w-1.5 rounded-full ${on ? "bg-teal" : "bg-amber"}`}
      aria-hidden
    />
  );
}
