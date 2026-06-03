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

/** localStorage から token + operator + sessionType を一括復元する。
 *  token があっても operator が復元できない場合は全クリアして null を返す。
 *  これにより isAuthenticated=true && operator=null の状態を完全に排除する。
 */
function restoreAuthState(): { token: string | null; operator: Operator | null; sessionType: string | null } {
  if (typeof window === "undefined") return { token: null, operator: null, sessionType: null };

  const clearAll = () => {
    localStorage.removeItem("work_token");
    localStorage.removeItem("work_operator");
    localStorage.removeItem("work_session_type");
  };

  // トークン取得・有効期限チェック
  const t = localStorage.getItem("work_token");
  if (!t) return { token: null, operator: null, sessionType: null };
  try {
    const payload = JSON.parse(atob(t.split('.')[1].replace(/-/g,'+').replace(/_/g,'/')));
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      clearAll();
      return { token: null, operator: null, sessionType: null };
    }
  } catch {
    clearAll();
    return { token: null, operator: null, sessionType: null };
  }

  // operator 復元 — 存在しない場合は全クリア（isAuthenticated=true && operator=null を防ぐ）
  const opStr = localStorage.getItem("work_operator");
  if (!opStr) {
    // work_operator が未保存（fix_auth_restore_v1 適用前のセッション）→ 全クリアして再認証を促す
    clearAll();
    return { token: null, operator: null, sessionType: null };
  }
  let operator: Operator | null = null;
  try {
    operator = JSON.parse(opStr);
  } catch {
    clearAll();
    return { token: null, operator: null, sessionType: null };
  }
  if (!operator || !operator.id || !operator.name) {
    clearAll();
    return { token: null, operator: null, sessionType: null };
  }

  const sessionType = localStorage.getItem("work_session_type") ?? null;
  return { token: t, operator, sessionType };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const initial = restoreAuthState();

  const [token,       setToken]       = useState<string | null>(initial.token);
  const [operator,    setOperator]    = useState<Operator | null>(initial.operator);
  const [sessionType, setSessionType] = useState<string | null>(initial.sessionType);

  const login = useCallback((res: WorkSessionResponse) => {
    setToken(res.access_token);
    setOperator(res.operator);
    setSessionType(res.session_type);
    if (typeof window !== "undefined") {
      localStorage.setItem("work_token",        res.access_token);
      localStorage.setItem("work_operator",     JSON.stringify(res.operator));
      localStorage.setItem("work_session_type", res.session_type);
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
      localStorage.removeItem("work_operator");
      localStorage.removeItem("work_session_type");
    }
  }, [token]);

  // isAuthenticated = token AND operator の両方が揃っているときのみ true
  // これにより isAuthenticated=true && operator=null の状態を完全に排除する
  const isAuthenticated = !!token && operator !== null;

  return (
    <AuthContext.Provider value={{
      token,
      operator,
      sessionType,
      isAuthenticated,
      login,
      logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
