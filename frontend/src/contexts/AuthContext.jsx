import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = loading, false = anon, obj = authed
  const [bootstrapped, setBootstrapped] = useState(false);

  const refresh = useCallback(async () => {
    const token = localStorage.getItem("dc_token");
    if (!token) {
      setUser(false);
      setBootstrapped(true);
      return;
    }
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch {
      localStorage.removeItem("dc_token");
      setUser(false);
    } finally {
      setBootstrapped(true);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("dc_token", data.token);
    setUser(data.user);
    return data.user;
  };

  const signup = async (email, password, name, ref, twinId, source) => {
    const { data } = await api.post("/auth/signup", { email, password, name, ref, twin_id: twinId, source });
    localStorage.setItem("dc_token", data.token);
    setUser(data.user);
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem("dc_token");
    setUser(false);
  };

  return (
    <AuthCtx.Provider value={{ user, bootstrapped, login, signup, logout, refresh, setUser }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
