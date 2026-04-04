"use client";
import { createContext, useContext, useState, useCallback, ReactNode } from "react";
import { authApi, WorkSessionResponse } from "../lib/api";

type Operator = { id: number; name: string; role: string };

type AuthContextType = {
  token: string | null;
  operator: Operator | null;
  sessionType: string | null;
  isAuthenticated: boolean;
  login: (res: WorkSessionResponse) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType>({
  token: null,
  operator: null,
  sessionType: null,
  isAuthenticated: false,
  login: () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [operator, setOperator] = useState<Operator | null>(null);
  const [sessionType, setSessionType] = useState<string | null>(null);

  const login = useCallback((res: WorkSessionResponse) => {
    setToken(res.access_token);
    setOperator(res.operator);
    setSessionType(res.session_type);
    if (typeof window !== "undefined") {
      localStorage.setItem("work_token", res.access_token);
    }
  }, []);

  const logout = useCallback(() => {
    if (token) {
      authApi.endWorkSession(token).catch(() => {});
    }
    setToken(null);
    setOperator(null);
    setSessionType(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem("work_token");
    }
  }, [token]);

  return (
    <AuthContext.Provider value={{
      token,
      operator,
      sessionType,
      isAuthenticated: !!token,
      login,
      logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
