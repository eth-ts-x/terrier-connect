import React, { createContext, useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../services/apiClient";

const AuthContext = createContext(null);

/**
 * AuthProvider wraps the application.
 * On every page load it calls GET /users/me/ to rehydrate auth state from
 * the HttpOnly cookie — no token ever touches localStorage or JS memory.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);   // null = unauthenticated / unknown
  const [loading, setLoading] = useState(true); // true while the /me check is in flight
  const navigate = useNavigate();

  // On mount, try to restore session from the access cookie
  useEffect(() => {
    apiClient
      .get("/users/me/")
      .then((res) => setUser(res.data))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const logout = async () => {
    try {
      await apiClient.post("/users/logout/");
    } catch {
      // ignore errors — clear state regardless
    }
    setUser(null);
    navigate("/login");
  };

  return (
    <AuthContext.Provider value={{ user, setUser, loading, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export default AuthContext;
