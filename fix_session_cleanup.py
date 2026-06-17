#!/usr/bin/env python3
"""
fix_session_cleanup.py
======================
問題: 段取シート発行/作業記録ページからダッシュボード等へ遷移した際に
     LocalStorageのセッション情報(work_token等)が残存する。

修正内容:
  1. AuthContext.tsx: useRefでtokenを追跡しlogoutをstale closure対策
  2. mc/[mc_id]/print/page.tsx: isSessionForMcチェック + アンマウント時logout
  3. nc/[nc_id]/print/page.tsx: アンマウント時logout
  4. mc/[mc_id]/record/page.tsx: アンマウント時logout
"""
import os, sys, re, subprocess

REPO = os.path.expanduser("~/projects/machcore")

def patch(filepath, old, new, label):
    full = os.path.join(REPO, filepath)
    with open(full, "r", encoding="utf-8") as f:
        src = f.read()
    if old not in src:
        print(f"  [SKIP] {label}")
        return False
    with open(full, "w", encoding="utf-8") as f:
        f.write(src.replace(old, new, 1))
    print(f"  [OK]   {label}")
    return True

def run(cmd, cwd=None):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr

print("=" * 60)
print("fix_session_cleanup.py - セッションクリーンアップ修正")
print("=" * 60)

ok = True

# ── 1. AuthContext.tsx ─────────────────────────────────────────
# 1a. import に useEffect, useRef を追加
ok &= patch(
    "apps/web/contexts/AuthContext.tsx",
    'import { createContext, useContext, useState, useCallback, ReactNode } from "react";',
    'import { createContext, useContext, useState, useCallback, useEffect, useRef, ReactNode } from "react";',
    "AuthContext: import useEffect/useRef"
)

# 1b. tokenRef を ncProgramId の直後に追加
ok &= patch(
    "apps/web/contexts/AuthContext.tsx",
    "  const [ncProgramId, setNcProgramId] = useState<number | null>(initialPayload?.nc_program_id ?? null);",
    "  const [ncProgramId, setNcProgramId] = useState<number | null>(initialPayload?.nc_program_id ?? null);\n\n  // アンマウント時等のクリーンアップで常に最新のtokenを参照できるようRefで追跡\n  const tokenRef = useRef<string | null>(initial.token);\n  useEffect(() => { tokenRef.current = token; }, [token]);",
    "AuthContext: tokenRef追加"
)

# 1c. logout を tokenRef ベースに変更
ok &= patch(
    "apps/web/contexts/AuthContext.tsx",
    """  const logout = useCallback(() => {
    if (token) {
      authApi.endWorkSession(token).catch(() => {});
    }
    setToken(null);
    setOperator(null);
    setSessionType(null);
    setMcProgramId(null);
    setNcProgramId(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem("work_token");
      localStorage.removeItem("work_operator");
      localStorage.removeItem("work_session_type");
    }
  }, [token]);""",
    """  const logout = useCallback(() => {
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
      localStorage.removeItem("work_token");
      localStorage.removeItem("work_operator");
      localStorage.removeItem("work_session_type");
    }
  }, []);""",
    "AuthContext: logout を tokenRef 参照に変更"
)

# ── 2. mc/[mc_id]/print/page.tsx ──────────────────────────────
# 2a. isSessionForMc 取得
ok &= patch(
    "apps/web/app/mc/[mc_id]/print/page.tsx",
    "  const { operator, isAuthenticated, logout, token } = useAuth();",
    "  const { operator, isAuthenticated, logout, token, isSessionForMc } = useAuth();",
    "mc/print: isSessionForMc 取得"
)

# 2b. タイマーuseEffect の前にアンマウントuseEffect + isSessionForMcチェック挿入
old_timer = """  useEffect(() => {
    if (isAuthenticated) {
      timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setElapsed(0);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isAuthenticated]);"""

new_timer = """  // -- 別mc_id向けセッションが残っていれば強制ログアウト --
  useEffect(() => {
    if (isAuthenticated && !isSessionForMc(mcId)) {
      console.warn("[MC-PRINT] 認証セッションが別のmc_id向けのため強制ログアウト", { mcId });
      logout();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mcId, isAuthenticated]);

  // -- ページ離脱時（アンマウント）に確実にセッションをクリア --
  useEffect(() => {
    return () => {
      logout();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setElapsed(0);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isAuthenticated]);"""

ok &= patch("apps/web/app/mc/[mc_id]/print/page.tsx", old_timer, new_timer,
            "mc/print: isSessionForMcチェック + アンマウントlogout")

# ── 3. nc/[nc_id]/print/page.tsx ──────────────────────────────
# regex で全角ダッシュコメント行を探して前に挿入
nc_print_path = os.path.join(REPO, "apps/web/app/nc/[nc_id]/print/page.tsx")
with open(nc_print_path, "r", encoding="utf-8") as f:
    nc_src = f.read()
m = re.search(r"  // ── タイマー（認証後に起動） ──\n  useEffect\(\(\) => \{", nc_src)
if m:
    insert_pos = m.start()
    insert_text = ("  // -- ページ離脱時（アンマウント）に確実にセッションをクリア --\n"
                   "  useEffect(() => {\n"
                   "    return () => {\n"
                   "      logout();\n"
                   "    };\n"
                   "  // eslint-disable-next-line react-hooks/exhaustive-deps\n"
                   "  }, []);\n\n  ")
    nc_src = nc_src[:insert_pos] + insert_text + nc_src[insert_pos:]
    with open(nc_print_path, "w", encoding="utf-8") as f:
        f.write(nc_src)
    print("  [OK]   nc/print: アンマウントlogout")
else:
    print("  [SKIP] nc/print: アンマウントlogout - anchor not found")
    ok = False

# ── 4. mc/[mc_id]/record/page.tsx ─────────────────────────────
ok &= patch(
    "apps/web/app/mc/[mc_id]/record/page.tsx",
    """    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [sbMode, isAuthenticated]);""",
    """    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [sbMode, isAuthenticated]);

  // -- ページ離脱時（アンマウント）に確実にセッションをクリア --
  React.useEffect(() => {
    return () => {
      logout();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);""",
    "mc/record: アンマウントlogout"
)

if not ok:
    print("\n[ERROR] 一部パッチが失敗しました。処理を中断します。")
    sys.exit(1)

print("\n[全パッチ適用完了]\n")

# ── ビルド ──────────────────────────────────────────────────────
print("── npx prisma generate ──")
rc, out, err = run(". $NVM_DIR/nvm.sh && npx prisma generate", cwd=os.path.join(REPO, "apps/api"))
if rc != 0:
    print("[prisma generate ERROR]"); print(err[-1000:]); sys.exit(1)
print("  OK")

print("\n── nest build ──")
rc, out, err = run(". $NVM_DIR/nvm.sh && npx nest build", cwd=os.path.join(REPO, "apps/api"))
if rc != 0:
    print("[nest build ERROR]"); print(err[-2000:]); sys.exit(1)
print("  OK")

print("\n── next build ──")
rc, out, err = run(". $NVM_DIR/nvm.sh && npx next build", cwd=os.path.join(REPO, "apps/web"))
if rc != 0:
    print("[next build ERROR]"); print(err[-2000:]); print(out[-1000:]); sys.exit(1)
print("  OK")

print("\n── pm2 restart ──")
rc, out, err = run(". $NVM_DIR/nvm.sh && pm2 restart ecosystem.config.js", cwd=REPO)
print(out[-300:] if out else "", err[-200:] if err else "")

print("\n── git push ──")
run("git add -A", cwd=REPO)
run('git commit -m "fix: 全権限作業ページでアンマウント時にセッションを確実にクリア\\n\\nAuthContext: logoutをtokenRefベースに変更(stale closure対策)\\nmc/print: isSessionForMcチェック + アンマウントlogout追加\\nnc/print: アンマウントlogout追加\\nmc/record: アンマウントlogout追加"', cwd=REPO)
rc, out, err = run("git push", cwd=REPO)
if rc != 0:
    print("[GIT PUSH ERROR]"); print(err[-500:]); sys.exit(1)
print("  Git push OK\n")
print("[完了] 全処理成功")
