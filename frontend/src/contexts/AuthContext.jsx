import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, setAuthToken } from "@/lib/api";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => window.localStorage.getItem("bank_auth_token"));
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    window.localStorage.removeItem("bank_auth_token");
    setAuthToken(null);
    setToken(null);
    setUser(null);
  }, []);

  const refreshMe = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return null;
    }
    try {
      setAuthToken(token);
      const response = await api.get("/auth/me");
      setUser(response.data);
      return response.data;
    } catch {
      logout();
      return null;
    } finally {
      setLoading(false);
    }
  }, [token, logout]);

  useEffect(() => {
    refreshMe();
  }, [refreshMe]);

  const loginWithToken = useCallback((newToken, nextUser) => {
    window.localStorage.setItem("bank_auth_token", newToken);
    setAuthToken(newToken);
    setToken(newToken);
    setUser(nextUser);
  }, []);

  const value = useMemo(() => ({ token, user, loading, loginWithToken, logout, refreshMe }), [token, user, loading, loginWithToken, logout, refreshMe]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => useContext(AuthContext);
