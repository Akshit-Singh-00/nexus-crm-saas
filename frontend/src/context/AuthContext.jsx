import { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [workspaces, setWorkspaces] = useState([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState(
    localStorage.getItem("nexus_workspace_id") || null
  );
  const [loading, setLoading] = useState(true);

  const bootstrap = useCallback(async () => {
    const token = localStorage.getItem("nexus_token");
    if (!token) { setLoading(false); return; }
    try {
      const { data } = await api.get("/auth/me");
      setUser(data.user);
      setWorkspaces(data.workspaces || []);
      const ws = data.workspaces || [];
      if (ws.length) {
        const active = ws.find((w) => w.id === activeWorkspaceId) || ws[0];
        setActiveWorkspaceId(active.id);
        localStorage.setItem("nexus_workspace_id", active.id);
      }
    } catch (e) {
      localStorage.removeItem("nexus_token");
    } finally {
      setLoading(false);
    }
  }, [activeWorkspaceId]);

  useEffect(() => { bootstrap(); }, [bootstrap]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("nexus_token", data.token);
    await bootstrap();
    return data.user;
  };

  const signup = async (email, password, name) => {
    const { data } = await api.post("/auth/signup", { email, password, name });
    localStorage.setItem("nexus_token", data.token);
    setUser(data.user);
    setWorkspaces([]);
    setLoading(false);
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem("nexus_token");
    localStorage.removeItem("nexus_workspace_id");
    setUser(null);
    setWorkspaces([]);
    setActiveWorkspaceId(null);
  };

  const createWorkspace = async (name, industry) => {
    const { data } = await api.post("/workspaces", { name, industry });
    setWorkspaces((prev) => [...prev, data]);
    setActiveWorkspaceId(data.id);
    localStorage.setItem("nexus_workspace_id", data.id);
    return data;
  };

  const switchWorkspace = (id) => {
    setActiveWorkspaceId(id);
    localStorage.setItem("nexus_workspace_id", id);
  };

  const activeWorkspace = workspaces.find((w) => w.id === activeWorkspaceId) || null;

  return (
    <AuthContext.Provider value={{
      user, workspaces, activeWorkspace, activeWorkspaceId,
      loading, login, signup, logout, createWorkspace, switchWorkspace, refresh: bootstrap
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
