#!/usr/bin/env python3
"""
fix_auth_restore_v2.py
edit/page.tsx: isAuthenticated && !operator の場合も赤バナー+登録ボタンを表示保証
条件を operator に依存せず token だけで判定し、operator.name は ?? でフォールバック
"""
import subprocess, sys

BASE      = "/home/karkyon/projects/machcore"
EDIT_PAGE = f"{BASE}/apps/web/app/mc/[mc_id]/edit/page.tsx"

with open(EDIT_PAGE, "r") as f:
    src = f.read()

# 赤バナー条件を isAuthenticated && operator から isAuthenticated (token) のみに変更
# operator.name は "（作業中）" にフォールバック
OLD_RED_BANNER = '''      {isAuthenticated && operator && !sbMode && !sbRepeatMode && (
        <div className="bg-red-600 text-white px-5 py-1.5 flex items-center justify-between text-xs shrink-0">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 bg-red-300 rounded-full animate-pulse" />
            <span>編集セッション: {operator.name}</span>
          </div>
          <div className="flex gap-3">
            <button onClick={() => {
                logout();
                router.push(`/mc/${mcId}`);
              }}
              className="text-red-200 hover:text-white">キャンセル</button>
            <button onClick={handleSave} disabled={saving}
              className="bg-white text-red-700 px-3 py-0.5 rounded font-bold hover:bg-red-50 disabled:opacity-50">
              {saving ? "保存中..." : sbMode ? "STEP1完了 → STEP2(作業記録)へ" : "作業完了（登録）"}
            </button>
          </div>
        </div>
      )}'''

NEW_RED_BANNER = '''      {isAuthenticated && !sbMode && !sbRepeatMode && (
        <div className="bg-red-600 text-white px-5 py-1.5 flex items-center justify-between text-xs shrink-0">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 bg-red-300 rounded-full animate-pulse" />
            <span>編集セッション: {operator?.name ?? "（作業中）"}</span>
          </div>
          <div className="flex gap-3">
            <button onClick={() => {
                logout();
                router.push(`/mc/${mcId}`);
              }}
              className="text-red-200 hover:text-white">キャンセル</button>
            <button onClick={handleSave} disabled={saving}
              className="bg-white text-red-700 px-3 py-0.5 rounded font-bold hover:bg-red-50 disabled:opacity-50">
              {saving ? "保存中..." : sbMode ? "STEP1完了 → STEP2(作業記録)へ" : "作業完了（登録）"}
            </button>
          </div>
        </div>
      )}'''

if OLD_RED_BANNER in src:
    src = src.replace(OLD_RED_BANNER, NEW_RED_BANNER, 1)
    print("  OK: 赤バナー条件修正 (operator不要)")
else:
    print("  WARN: 赤バナーパターン不一致")
    sys.exit(1)

# sbモードバナーも同様に operator 依存を外す
OLD_SB_BANNER = '''      {isAuthenticated && operator && (sbMode || sbRepeatMode) && ('''
NEW_SB_BANNER = '''      {isAuthenticated && (sbMode || sbRepeatMode) && ('''

if OLD_SB_BANNER in src:
    src = src.replace(OLD_SB_BANNER, NEW_SB_BANNER, 1)
    print("  OK: sbモードバナー条件修正")
else:
    print("  INFO: sbバナーパターン不一致（スキップ）")

# ロック画面条件: !isAuthenticated のみで十分（変更なし、確認のみ）
if '!isAuthenticated && detail &&' in src:
    print("  OK: ロック画面条件 (!isAuthenticated) 確認済み")

with open(EDIT_PAGE, "w") as f:
    f.write(src)
print("  SAVED:", EDIT_PAGE)

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
    'cd /home/karkyon/projects/machcore && git add -A && git commit -m "fix: edit page - show red banner on isAuthenticated (not operator-dependent)" && git push origin main',
    shell=True, capture_output=True, text=True
)
print(r.stdout)
print("=== 完了 ===")
