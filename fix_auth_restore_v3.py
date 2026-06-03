#!/usr/bin/env python3
"""
fix_auth_restore_v3.py
AuthContext の完全修正:
  - isAuthenticated = !!token && operator !== null  (token + operator 両方必要)
  - token はあるが operator が復元できない(localStorage.work_operator なし)場合は即logout
  - これにより isAuthenticated=true && operator=null の状態を完全に排除
"""
import subprocess, sys

BASE         = "/home/karkyon/projects/machcore"
AUTH_CONTEXT = f"{BASE}/apps/web/contexts/AuthContext.tsx"

with open(AUTH_CONTEXT, "r") as f:
    src = f.read()

OLD = '''"use client";
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
  const [token, setToken] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const t = localStorage.getItem("work_token");
    if (!t) return null;
    // JWTのexpを確認（base64デコードのみ、ライブラリ不要）
    try {
      const payload = JSON.parse(atob(t.split('.')[1].replace(/-/g,'+').replace(/_/g,'/')));
      if (payload.exp && payload.exp * 1000 < Date.now()) {
        // 期限切れ → 即クリア
        localStorage.removeItem("work_token");
        return null;
      }
    } catch {
      localStorage.removeItem("work_token");
      return null;
    }
    return t;
  });
  const [operator, setOperator] = useState<Operator | null>(() => {
    if (typeof window === "undefined") return null;
    try {
      const s = localStorage.getItem("work_operator");
      return s ? JSON.parse(s) : null;
    } catch { return null; }
  });
  const [sessionType, setSessionType] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("work_session_type") ?? null;
  });

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

export const useAuth = () => useContext(AuthContext);'''

NEW = '''"use client";
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

export const useAuth = () => useContext(AuthContext);'''

if OLD in src:
    src = src.replace(OLD, NEW)
    print("  OK: AuthContext 完全書き換え")
else:
    print("  WARN: パターン不一致 — 現在のAuthContextを確認")
    # 部分確認
    if 'isAuthenticated: !!token,' in src:
        print("  → isAuthenticated行を直接置換")
        src = src.replace(
            'isAuthenticated: !!token,',
            '// isAuthenticated = token AND operator 両方必要 (operator=null は isAuthenticated=false)\n      isAuthenticated: !!token && operator !== null,'
        )
        print("  OK: isAuthenticated 条件修正のみ適用")
    else:
        sys.exit(1)

with open(AUTH_CONTEXT, "w") as f:
    f.write(src)
print("  SAVED:", AUTH_CONTEXT)

print("=== ビルド ===")
r = subprocess.run(
    "cd /home/karkyon/projects/machcore/apps/web && npx next build 2>&1 | tail -15",
    shell=True, capture_output=True, text=True
)
print(r.stdout)
if r.returncode != 0:
    print("BUILD ERROR:", r.stderr[-300:])
    sys.exit(1)

print("=== PM2 再起動 ===")
subprocess.run("pm2 restart machcore-web", shell=True)

print("=== git push ===")
r = subprocess.run(
    'cd /home/karkyon/projects/machcore && git add -A && git commit -m "fix: AuthContext v3 - enforce isAuthenticated=token+operator, auto-clear on operator missing" && git push origin main',
    shell=True, capture_output=True, text=True
)
print(r.stdout)
print("=== 完了 ===")
