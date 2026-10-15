import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";

const HealthContext = createContext(null);

export function HealthProvider({ children }) {
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
    const timer = window.setInterval(load, 60000);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, []);

  return <HealthContext.Provider value={health}>{children}</HealthContext.Provider>;
}

export function useHealth() {
  return useContext(HealthContext);
}
