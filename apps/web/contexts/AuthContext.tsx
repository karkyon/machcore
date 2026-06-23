"use client";
import { createContext, useContext, useState, useCallback, useEffect, useRef, ReactNode } from "react";
import { authApi, WorkSessionResponse } from "../lib/api";

type Operator = { id: number; name: string; role: string };

type AuthContextType = {
  token: string | null;
  operator: Operator | null;
  sessionType: string | null;
  isAuthenticated: boolean;
  /** このセッション(トークン)が対象とする mc_program_id (無い場合 null) */
  mcProgramId: number | null;
  /** このセッション(トークン)が対象とする nc_program_id (無い場合 null) */
  ncProgramId: number | null;
  login: (res: WorkSessionResponse) => void;
  logout: () => void;
  /**
   * 現在のセッションが指定の mc_id/nc_id に対して有効かどうかを判定する。
   * トークンに program_id が埋め込まれていない場合(後方互換)は true を返す。
   * 不一致の場合、この画面でその認証情報を使うのは誤りであることを示す。
   */
  isSessionForMc: (mcId: number) => boolean;
  isSessionForNc: (ncId: number) => boolean;
};

const AuthContext = createContext<AuthContextType>({
  token: null,
  operator: null,
  sessionType: null,
  isAuthenticated: false,
  mcProgramId: null,
  ncProgramId: null,
  login: () => {},
  logout: () => {},
  isSessionForMc: () => true,
  isSessionForNc: () => true,
});

/** sessionStorage から token + operator + sessionType を一括復元する。
 *  token があっても operator が復元できない場合は全クリアして null を返す。
 *  これにより isAuthenticated=true && operator=null の状態を完全に排除する。
 */
/** JWTのpayload部分をデコードする。失敗時は null を返す。 */
function decodeJwtPayload(token: string): any | null {
  try {
    return JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
  } catch {
    return null;
  }
}

function restoreAuthState(): { token: string | null; operator: Operator | null; sessionType: string | null } {
  if (typeof window === "undefined") return { token: null, operator: null, sessionType: null };

  const clearAll = () => {
    sessionStorage.removeItem("work_token");
    sessionStorage.removeItem("work_operator");
    sessionStorage.removeItem("work_session_type");
  };

  // トークン取得・有効期限チェック
  const t = sessionStorage.getItem("work_token");
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
  const opStr = sessionStorage.getItem("work_operator");
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

  const sessionType = sessionStorage.getItem("work_session_type") ?? null;
  return { token: t, operator, sessionType };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const initial = restoreAuthState();
  const initialPayload = initial.token ? decodeJwtPayload(initial.token) : null;

  const [token,       setToken]       = useState<string | null>(initial.token);
  const [operator,    setOperator]    = useState<Operator | null>(initial.operator);
  const [sessionType, setSessionType] = useState<string | null>(initial.sessionType);
  const [mcProgramId, setMcProgramId] = useState<number | null>(initialPayload?.mc_program_id ?? null);
  const [ncProgramId, setNcProgramId] = useState<number | null>(initialPayload?.nc_program_id ?? null);

  // アンマウント時等のクリーンアップで常に最新のtokenを参照できるようRefで追跡
  const tokenRef = useRef<string | null>(initial.token);
  useEffect(() => { tokenRef.current = token; }, [token]);

  const login = useCallback((res: WorkSessionResponse) => {
    setToken(res.access_token);
    setOperator(res.operator);
    setSessionType(res.session_type);
    const payload = decodeJwtPayload(res.access_token);
    setMcProgramId(payload?.mc_program_id ?? null);
    setNcProgramId(payload?.nc_program_id ?? null);
    if (typeof window !== "undefined") {
      sessionStorage.setItem("work_token",        res.access_token);
      sessionStorage.setItem("work_operator",     JSON.stringify(res.operator));
      sessionStorage.setItem("work_session_type", res.session_type);
    }
  }, []);

  const logout = useCallback(() => {
    const t = tokenRef.current;
    if (t) {
      authApi.endWorkSession(t).catch(() => {});
    }
    setToken(null);
    setOperator(null);
    setSessionType(null);
    setMcProgramId(null);
    setNcProgramId(null);
    tokenRef.current = null;
    if (typeof window !== "undefined") {
      sessionStorage.removeItem("work_token");
      sessionStorage.removeItem("work_operator");
      sessionStorage.removeItem("work_session_type");
    }
  }, []);

  // isAuthenticated = token AND operator の両方が揃っているときのみ true
  // これにより isAuthenticated=true && operator=null の状態を完全に排除する
  const isAuthenticated = !!token && operator !== null;

  // 現在保持しているセッションが指定の mc_id/nc_id に対して有効かどうか。
  // トークンに program_id が埋め込まれていない(=旧トークンや管理者ログイン)場合は
  // 後方互換のため true を返すが、mc_program_id/nc_program_id が設定されている
  // トークンで対象が異なる場合は false を返す。
  // これにより、編集セッションが残ったまま別の mc_id/nc_id 画面に遷移した際に
  // 「再認証なしで編集・発行ができてしまう」状態を画面側で検知できる。
  const isSessionForMc = useCallback((mcId: number) => {
    if (!isAuthenticated) return false;
    if (mcProgramId == null) return true;
    return mcProgramId === mcId;
  }, [isAuthenticated, mcProgramId]);

  const isSessionForNc = useCallback((ncId: number) => {
    if (!isAuthenticated) return false;
    if (ncProgramId == null) return true;
    return ncProgramId === ncId;
  }, [isAuthenticated, ncProgramId]);

  return (
    <AuthContext.Provider value={{
      token,
      operator,
      sessionType,
      isAuthenticated,
      mcProgramId,
      ncProgramId,
      login,
      logout,
      isSessionForMc,
      isSessionForNc,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
