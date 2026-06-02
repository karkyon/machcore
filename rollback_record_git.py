#!/usr/bin/env python3
import subprocess, os

TARGET_REL = "apps/web/app/mc/[mc_id]/record/page.tsx"
TARGET     = f"/home/karkyon/projects/machcore/{TARGET_REL}"
REPO       = "/home/karkyon/projects/machcore"

# git log で確認
r = subprocess.run(["git", "log", "--oneline", "-15"], cwd=REPO, capture_output=True, text=True)
print("=== git log ===")
print(r.stdout)

# fix_record_validation.py のコミット = 64fabbe
# これが「文字化け前・TC参照ボタン2個ある・日時バリデーション有り」の最後の正常版
# fix_record_clean_write のコミット = 2d72ce4 (文字化け開始)
RESTORE_COMMIT = "64fabbe"

print(f"\n{RESTORE_COMMIT} のファイルを復元します...")
r2 = subprocess.run(
    ["git", "show", f"{RESTORE_COMMIT}:{TARGET_REL}"],
    cwd=REPO, capture_output=True
)
if r2.returncode != 0:
    print(f"❌ git show 失敗: {r2.stderr.decode()}")
    import sys; sys.exit(1)

content = r2.stdout
print(f"取得: {len(content)} bytes, {len(content.splitlines())}行")

# 書き込み
with open(TARGET, "wb") as f:
    f.write(content)
print("✅ ファイル書き込み完了")

# tsc
print("--- tsc ---")
r3 = subprocess.run(["npx", "tsc", "--noEmit"], cwd=f"{REPO}/apps/web", capture_output=True, text=True)
if r3.returncode != 0:
    print("❌ tsc エラー:")
    print((r3.stdout+r3.stderr)[-2000:])
    import sys; sys.exit(1)
print("✅ tsc OK")

# next build
print("--- next build ---")
r4 = subprocess.run(["npx", "next", "build"], cwd=f"{REPO}/apps/web", capture_output=True, text=True)
if r4.returncode != 0:
    print("❌ next build エラー:")
    print((r4.stdout+r4.stderr)[-2000:])
    import sys; sys.exit(1)
print("✅ next build OK")

subprocess.run(["pm2", "restart", "machcore-web"], capture_output=True)
print("✅ pm2 restart")

subprocess.run(["git", "add", "-A"], cwd=REPO)
subprocess.run(["git", "commit", "-m", f"revert: record page restore to {RESTORE_COMMIT} (pre-unicode-issue)"], cwd=REPO)
r5 = subprocess.run(["git", "push"], cwd=REPO, capture_output=True, text=True)
print("✅ git push\n" + (r5.stderr.strip() or r5.stdout.strip()))
print("✅ 完了")
