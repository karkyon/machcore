#!/usr/bin/env python3
# coding: utf-8
"""
fix_v33.py
  問題1: edit/page.tsx handleSave で sbMode時も logout() を呼んでいる
          → AuthContextのtokenがnullになった状態でrecordへ遷移
          → record/page.tsxでtoken=nullのままAPIを叩いてしまい400エラー
          → isAuthenticated=false になるため「この作業を開始する」が表示される

  修正:
    1. edit/page.tsx handleSave: sbMode時は logout() しない
       sb_next_record の削除もしない（record側でのみ削除）
    2. record/page.tsx handleSubmit: sbMode時は token が AuthContext にある前提
       console.log デバッグを追加して状況を可視化
    3. record/page.tsx: sbMode時の !isAuthenticated パネル非表示条件を確認・強化
"""
import pathlib, subprocess, sys

ROOT = "/home/karkyon/projects/machcore"

def apply(path_str, old, new, label):
    p = pathlib.Path(path_str)
    s = p.read_text(encoding="utf-8")
    if old in s:
        p.write_text(s.replace(old, new, 1), encoding="utf-8")
        print(f"OK: {label}")
        return True
    else:
        print(f"WARN: {label} — パターン不一致")
        return False

EDIT = ROOT + "/apps/web/app/mc/[mc_id]/edit/page.tsx"
REC  = ROOT + "/apps/web/app/mc/[mc_id]/record/page.tsx"

# ─────────────────────────────────────────────────────────────
# 1. edit/page.tsx handleSave:
#    sbMode時は logout() しない。sb_next_record も削除しない。
#    recordへの遷移パスを sbMode専用に変更。
# ─────────────────────────────────────────────────────────────
apply(
    EDIT,
    """      showToast("✅ 保存しました");
      logout();
      setTimeout(() => {
        if (typeof window !== "undefined") {
          const nextMcId = sessionStorage.getItem("sb_next_record");
          if (nextMcId && parseInt(nextMcId) === mcId) {
            sessionStorage.removeItem("sb_next_record");
            router.push(`/mc/${mcId}/record`);
            return;
          }
        }
        router.push(`/mc/${mcId}`);
      }, 1200);""",
    """      showToast("✅ 保存しました");
      if (sbMode) {
        // sbMode: logout()しない（tokenをrecordページへ引き継ぐ）
        // sb_next_record はrecord側でのみ削除する
        console.log("[STEP1] 保存完了 sbMode=true → recordへ遷移 token=", token ? "あり" : "なし");
        setTimeout(() => router.push(`/mc/${mcId}/record`), 800);
      } else {
        logout();
        setTimeout(() => router.push(`/mc/${mcId}`), 1200);
      }""",
    "edit/page.tsx handleSave sbMode時logout()しない"
)

# ─────────────────────────────────────────────────────────────
# 2. record/page.tsx handleSubmit: console.log追加 + sbMode時のtoken確認
# ─────────────────────────────────────────────────────────────
apply(
    REC,
    """  const handleSubmit = async () => {
    if (!token && !sbMode) return;
    setSaving(true); setSaveError(null);
    try {""",
    """  const handleSubmit = async () => {
    console.log("[STEP2] handleSubmit sbMode=", sbMode, "token=", token ? "あり" : "なし", "isAuthenticated=", isAuthenticated);
    if (!token && !sbMode) { console.log("[STEP2] token/sbMode なし — 中断"); return; }
    if (!token) { console.error("[STEP2] token が null — APIコール不可"); setSaveError("認証セッションが切れています。ページを再読み込みしてください。"); return; }
    setSaving(true); setSaveError(null);
    try {""",
    "record/page.tsx handleSubmit console.log追加 + token確認"
)

# ─────────────────────────────────────────────────────────────
# 3. record/page.tsx sbMode検出時の console.log追加
# ─────────────────────────────────────────────────────────────
apply(
    REC,
    """  useLayoutEffect(() => {
    if (typeof window !== "undefined") {
      const v = sessionStorage.getItem("sb_next_record");
      if (v && parseInt(v) === mcId) {
        setSbMode(true);
        const lid = sessionStorage.getItem("sb_sheet_log_id");
        if (lid) setSbSheetLogId(parseInt(lid));
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);""",
    """  useLayoutEffect(() => {
    if (typeof window !== "undefined") {
      const v = sessionStorage.getItem("sb_next_record");
      console.log("[STEP2] useLayoutEffect sb_next_record=", v, "mcId=", mcId);
      if (v && parseInt(v) === mcId) {
        setSbMode(true);
        const lid = sessionStorage.getItem("sb_sheet_log_id");
        if (lid) setSbSheetLogId(parseInt(lid));
        console.log("[STEP2] sbMode=true に設定 logId=", lid);
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);""",
    "record/page.tsx useLayoutEffect console.log追加"
)

# ─────────────────────────────────────────────────────────────
# 4. record/page.tsx isAuthenticated / sbMode の useEffect で log追加
# ─────────────────────────────────────────────────────────────
apply(
    REC,
    """  useEffect(() => {
    if (isAuthenticated) {
      timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setElapsed(0);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isAuthenticated]);""",
    """  useEffect(() => {
    console.log("[STEP2] isAuthenticated=", isAuthenticated, "sbMode=", sbMode, "token=", token ? "あり" : "なし");
    if (isAuthenticated) {
      timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setElapsed(0);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isAuthenticated]);""",
    "record/page.tsx isAuthenticated useEffect console.log追加"
)

# ─────────────────────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────────────────────
print("\n--- npm run build ---")
r = subprocess.run(
    "cd /home/karkyon/projects/machcore/apps/web && npm run build",
    shell=True, capture_output=True, text=True
)
out = r.stdout
print(out[-5000:] if len(out) > 5000 else out)
if r.returncode != 0:
    print("STDERR:", r.stderr[-2000:])
    print("BUILD FAILED — abort")
    sys.exit(1)

print("\n--- pm2 restart web ---")
r2 = subprocess.run(
    'export NVM_DIR="$HOME/.nvm" && source "$NVM_DIR/nvm.sh" && '
    'cd /home/karkyon/projects/machcore && '
    'pm2 delete machcore-web && pm2 start ecosystem.config.js --only machcore-web',
    shell=True, executable="/bin/bash", capture_output=True, text=True
)
print(r2.stdout)

print("\n--- git commit & push ---")
r3 = subprocess.run(
    "cd /home/karkyon/projects/machcore && "
    "git add -A && "
    "git commit -m 'fix: sbMode時logout()しない→tokenをrecordへ引き継ぎ 400エラー+認証前表示修正 v33' && "
    "git push origin main && pm2 save",
    shell=True, capture_output=True, text=True
)
print(r3.stdout)
if r3.returncode != 0:
    print("STDERR:", r3.stderr[-500:])

print("\nDONE")
