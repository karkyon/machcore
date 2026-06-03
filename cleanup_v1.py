#!/usr/bin/env python3
"""cleanup_v1.py - ゴミファイル一掃"""
import subprocess, os, glob

BASE = "/home/karkyon/projects/machcore"

# 削除対象: fix_*.py / setup_*.sh / *.bak / *.bak2
targets = (
    glob.glob(f"{BASE}/fix_*.py") +
    glob.glob(f"{BASE}/setup_*.sh") +
    glob.glob(f"{BASE}/**/*.bak", recursive=True) +
    glob.glob(f"{BASE}/**/*.bak2", recursive=True)
)

removed = []
for f in targets:
    try:
        os.remove(f)
        removed.append(os.path.basename(f))
    except Exception as e:
        print(f"  SKIP: {f} ({e})")

if removed:
    print(f"削除: {len(removed)}件")
    for n in removed: print(f"  - {n}")
else:
    print("削除対象なし")

r = subprocess.run(
    ["bash", "-c",
     f"cd {BASE} && git add -A && "
     f"git commit -m 'chore: cleanup fix scripts and bak files' && "
     f"git push origin main 2>&1"],
    capture_output=True, text=True
)
print(r.stdout.strip())
print("完了")
