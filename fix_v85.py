#!/usr/bin/env python3
"""fix_v85.py - partApproved判定を完全削除。認証済み+部品選択済みのみで仮登録ボタン有効"""
import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")
WEB  = f"{ROOT}/apps/web"

def read(p):
    with open(p,"r",encoding="utf-8") as f: return f.read()
def write(p,c):
    with open(p,"w",encoding="utf-8") as f: f.write(c)
def patch(p,old,new,label):
    c=read(p)
    if old not in c: print(f"WARN: {label} — 不一致"); return False
    write(p,c.replace(old,new,1)); print(f"OK: {label}"); return True
def run(cmd,cwd=ROOT):
    r=subprocess.run(cmd,shell=True,cwd=cwd,capture_output=True,text=True)
    if r.stdout.strip(): print(r.stdout[-4000:])
    if r.stderr.strip(): print("STDERR:",r.stderr[-2000:])
    return r.returncode

f = f"{WEB}/app/mc/new/page.tsx"

# 1. partApproved state削除
patch(f,
    "  const [saving,    setSaving]    = useState(false);\n  const [saveError, setSaveError] = useState<string | null>(null);\n  const [partApproved, setPartApproved] = useState<boolean | null>(null);",
    "  const [saving,    setSaving]    = useState(false);\n  const [saveError, setSaveError] = useState<string | null>(null);",
    "partApproved state削除"
)

# 2. handlePartSelect を元のシンプルな setSelectedPart(p) に戻す
patch(f,
    """  // 部品選択時：承認済みレコードの存在チェック
  const handlePartSelect = async (p: PartResult) => {
    setSelectedPart(p);
    setPartApproved(null); // 確認中→ボタンdisabled
    try {
      const res = await mcApi.search("drawing_no", p.drawing_no ?? "");
      const d   = (res as any).data ?? res;
      const rows: any[] = d.rows ?? [];
      if (rows.length === 0) {
        setPartApproved(true);
      } else {
        const hasApproved = rows.some((r: any) => r.status === "APPROVED");
        setPartApproved(hasApproved);
      }
    } catch {
      setPartApproved(true);
    }
  };""",
    "  const handlePartSelect = (p: PartResult) => {\n    setSelectedPart(p);\n  };",
    "handlePartSelectをシンプルに戻す"
)

# 3. canSubmit から partApproved 条件を削除
patch(f,
    "  // partApproved === true の場合のみ登録可（null=確認中はNG、false=未承認はNG）\n  const canSubmit = !!(authToken && isAuthenticated && selectedPart && machiningId && partApproved === true);",
    "  // 認証済み + 部品選択済み + 加工ID取得済み の場合のみ登録可\n  const canSubmit = !!(authToken && isAuthenticated && selectedPart && machiningId);",
    "canSubmitをシンプルに修正（認証済み+部品+加工IDのみ）"
)

# 4. 未承認警告メッセージブロックを削除
patch(f,
    """          {/* 未承認警告 */}
          {partApproved === false && (
            <div className="bg-amber-50 border border-amber-300 rounded-xl px-4 py-3 text-sm text-amber-800">
              <p className="font-bold mb-0.5">⚠️ この部品は承認済みレコードがありません</p>
              <p className="text-xs text-amber-600">承認済みの段取シートが存在する部品のみ、新たな加工IDを仮登録できます。</p>
            </div>
          )}
          {partApproved === null && selectedPart && (
            <div className="text-xs text-slate-400 animate-pulse">承認ステータスを確認中…</div>
          )}

          """,
    "          ",
    "未承認警告メッセージ削除"
)

print("--- build web ---")
rc = run("pnpm --filter web build", cwd=ROOT)
if rc != 0: rc = run("pnpm run build", cwd=f"{ROOT}/apps/web")
if rc != 0: print("BUILD FAILED — abort"); sys.exit(1)

print("--- pm2 restart ---")
run("pm2 restart machcore-web")

print("--- git push ---")
run("git add -A && git commit -m 'fix(v85): partApproved完全削除-認証済+部品選択のみで仮登録可' && git push", cwd=ROOT)
print("DONE v85")
