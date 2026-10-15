import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined);

  useEffect(() => {
    let stopped = false;
    api("/auth/me")
      .then((body) => {
        if (!stopped) setUser(body);
      })
      .catch(() => {
        if (!stopped) setUser(null);
      });
    return () => {
      stopped = true;
    };
  }, []);

  return <AuthContext.Provider value={{ user, setUser }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
