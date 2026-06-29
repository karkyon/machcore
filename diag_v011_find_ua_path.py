#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diag_v011_find_ua_path.py
1. UploadAgentリポジトリの実際のクローン先パスをサーバ上で検索する
2. v011パッチがmachcore側に部分適用されていないか確認する(B/C部分は未実行のはず)
コード変更は一切行わない。
"""
import subprocess
import os

def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.stdout + r.stderr

print("=" * 70)
print("【診断1】UploadAgentリポジトリの実際のパスを検索")
print("=" * 70)
print(run("find / -maxdepth 6 -iname 'UploadAgent.sln' -type f 2>/dev/null"))
print(run("find / -maxdepth 6 -iname 'UploadAgent' -type d 2>/dev/null"))

print("\n" + "=" * 70)
print("【診断2】machcore側にv011のB/C部分が適用されていないか確認(未適用のはず)")
print("=" * 70)
REPO = "/home/karkyon/projects/machcore"
nc_ctrl = os.path.join(REPO, "apps/api/src/nc/nc.controller.ts")
upload_lib = os.path.join(REPO, "apps/web/lib/upload-agent.ts")
nc_detail = os.path.join(REPO, "apps/web/app/nc/[nc_id]/page.tsx")

for label, path, needle in [
    ("B-1 (nc.controller.ts upload_path)", nc_ctrl, "upload_path:"),
    ("B-2 (upload-agent.ts uploadPath param)", upload_lib, "uploadPath?:"),
    ("C-1 (nc detail max-w-3xl)", nc_detail, 'className="max-w-3xl mx-auto space-y-4"'),
]:
    if os.path.exists(path):
        content = open(path, encoding="utf-8").read()
        print(f"  {label}: {'適用済み' if needle in content else '未適用'}")
    else:
        print(f"  {label}: ファイルが見つかりません ({path})")

print("\n" + "=" * 70)
print("【診断3】machcore側のgit statusとREPO存在確認")
print("=" * 70)
print(run(f"cd {REPO} && git status --short"))
print(run(f"cd {REPO} && git log --oneline -3"))

print("=" * 70)
print("【完了】")
print("=" * 70)
