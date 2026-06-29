# -*- coding: utf-8 -*-
"""
v025クリーンアップ: リポジトリルートに残った調査済み診断スクリプトの残骸を削除
対象: diag_v024_unique_constraint_missing.py (調査完了済み、再利用不要)
"""
import subprocess
import sys

REPO = "/home/karkyon/projects/machcore"
TARGET = f"{REPO}/diag_v024_unique_constraint_missing.py"

def run(cmd, cwd=None):
    print(f"[CMD] {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.stdout:
        print(r.stdout)
    if r.returncode != 0:
        print(f"[ERROR] {r.stderr}")
    return r.returncode == 0

print("=" * 70)
print("【v025】リポジトリルートの残骸ファイル削除")
print("=" * 70)

import os
if os.path.exists(TARGET):
    subprocess.run(["rm", "-f", TARGET])
    print(f"[OK] 削除: {TARGET}")
else:
    print(f"[SKIP] 既に存在しません: {TARGET}")

# git status確認
print("\n=== git status ===")
run(["git", "status", "--short"], cwd=REPO)

# コミット&push（このファイルだけの削除なので軽量。ビルド不要だが念のためAPIビルドのみ確認）
print("\n=== コミット & push ===")
run(["git", "add", "-A"], cwd=REPO)
r = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO)
if r.returncode == 0:
    print("[INFO] 差分なし。コミット不要。")
else:
    run(["git", "commit", "-m", "chore: 調査完了済み診断スクリプトの残骸を削除(diag_v024)"], cwd=REPO)
    run(["git", "push"], cwd=REPO)
    print("[OK] push完了")

print("\n【完了】")
