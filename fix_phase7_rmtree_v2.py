#!/usr/bin/env python3
# coding: utf-8
"""
fix_phase7_rmtree_v2.py
PHASE7 _safe_rmtree_and_mkdir の CIFS rmtree 失敗問題を修正する

変更内容:
  1. import に subprocess 追加
  2. _safe_rmtree_and_mkdir 内の shutil.rmtree を subprocess rm -rf に置換
"""
import sys, os, subprocess

SCRIPT_PATH = os.path.expanduser("~/projects/machcore/scripts/mc_full_import.py")

with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
    src = f.read()

# ── 1. subprocess import 追加 ─────────────────────────────────
OLD_IMPORT = "import sys, os, re, shutil, argparse, traceback"
NEW_IMPORT = "import sys, os, re, shutil, argparse, traceback, subprocess"

if OLD_IMPORT not in src:
    print("ERROR: importパターンが見つからない")
    sys.exit(1)

if "subprocess" not in src.split("def phase7")[0]:
    src = src.replace(OLD_IMPORT, NEW_IMPORT, 1)
    print("✅ subprocess import 追加完了")
else:
    print("✅ subprocess はすでにimport済み")

# ── 2. rmtree → rm -rf 置換 ───────────────────────────────────
OLD_RMTREE = '''        def _safe_rmtree_and_mkdir(dst_dir, label):
            """CIFS上でrmtree後makedirs失敗する問題をリトライで対処"""
            if dst_dir.exists():
                log(f"  {label}: コピー先クリア ({dst_dir})")
                _shutil.rmtree(str(dst_dir))'''

NEW_RMTREE = '''        def _safe_rmtree_and_mkdir(dst_dir, label):
            """CIFS上でrmtree後makedirs失敗する問題をリトライで対処 (rm -rf使用)"""
            if dst_dir.exists():
                log(f"  {label}: コピー先クリア ({dst_dir})")
                # CIFS上ではshutil.rmtreeがos.rmdirで失敗するため subprocess rm -rf を使用
                _res = subprocess.run(["rm", "-rf", str(dst_dir)],
                                      capture_output=True, text=True)
                if _res.returncode != 0:
                    log(f"  [WARN] rm -rf failed: {_res.stderr}", "WARN")'''

if OLD_RMTREE not in src:
    print("ERROR: _safe_rmtree_and_mkdir 置換対象が見つからない（すでに修正済みかも）")
    # 現状確認
    idx = src.find("_safe_rmtree_and_mkdir")
    print(f"  現状の該当箇所:\n{src[idx:idx+400]}")
    sys.exit(1)

src = src.replace(OLD_RMTREE, NEW_RMTREE, 1)
print("✅ rmtree → rm -rf 置換完了")

with open(SCRIPT_PATH, "w", encoding="utf-8") as f:
    f.write(src)
print("✅ ファイル書き込み完了")

# ── 3. git push ───────────────────────────────────────────────
REPO = os.path.expanduser("~/projects/machcore")
def run(cmd):
    r = subprocess.run(cmd, shell=True, cwd=REPO, capture_output=True, text=True)
    print(r.stdout.strip())
    if r.stderr.strip(): print(r.stderr.strip())
    return r.returncode

run("git add scripts/mc_full_import.py")
run('git commit -m "fix: PHASE7 _safe_rmtree_and_mkdir CIFS対応 rm -rf使用"')
rc = run("git push origin main")
if rc == 0:
    print("✅ GitHub push 完了")
else:
    print("ERROR: git push 失敗")
    sys.exit(1)

print("\n✅ 全修正完了 — python3 mc_full_import.py --phase 7 で再実行してください")
