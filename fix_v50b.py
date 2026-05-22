#!/usr/bin/env python3
"""
fix_v50b.py
fix_v50の誤修正を元に戻す
storedNameに拡張子を戻す: ${machId}-${n} → ${machId}-${n}${ext}
ただしmaxSeqDbは残す（DB+ファイルシステム両方から確実な連番取得）
"""
import subprocess, sys, os

ROOT = os.path.expanduser("~/projects/machcore")

def read(p):
    with open(p, encoding="utf-8") as f: return f.read()
def write(p, c):
    with open(p, "w", encoding="utf-8") as f: f.write(c)
def patch(path, old, new, label):
    c = read(path)
    if old not in c:
        print(f"WARN: {label} — パターン不一致")
        return False
    write(path, c.replace(old, new, 1))
    print(f"OK: {label}")
    return True

SERVICE = os.path.join(ROOT, "apps/api/src/mc/mc-files.service.ts")

# storedNameに拡張子を戻す
patch(SERVICE,
    "      const n = await this.maxSeqDb(mcProgramId, 'DRAWING', flatDir, String(machId)) + 1;\n      storedName = `${machId}-${n}`;   // 拡張子なし",
    "      const n = await this.maxSeqDb(mcProgramId, 'DRAWING', flatDir, String(machId)) + 1;\n      storedName = `${machId}-${n}${ext}`;   // 加工ID-連番.拡張子",
    "mc-files.service.ts DRAWING storedName拡張子を戻す"
)

patch(SERVICE,
    "      const n = await this.maxSeqDb(mcProgramId, 'PHOTO', flatDir, String(machId)) + 1;\n      storedName = `${machId}-${n}`;   // 拡張子なし",
    "      const n = await this.maxSeqDb(mcProgramId, 'PHOTO', flatDir, String(machId)) + 1;\n      storedName = `${machId}-${n}${ext}`;   // 加工ID-連番.拡張子",
    "mc-files.service.ts PHOTO storedName拡張子を戻す"
)

# サムネイル命名も戻す（storedNameに拡張子が付くので元の形式で正しい）
patch(SERVICE,
    "        const thumbName = `thumb_${storedName}.jpg`;",
    "        const thumbName = `thumb_${path.basename(storedName, path.extname(storedName))}.jpg`;",
    "mc-files.service.ts サムネイル命名修正（storedName拡張子あり対応）"
)

print("\n--- API npx tsc --noEmit ---")
r2 = subprocess.run("cd ~/projects/machcore/apps/api && npx tsc --noEmit", shell=True, capture_output=True, text=True)
if r2.returncode != 0:
    print(r2.stdout); print("STDERR:", r2.stderr)
    print("API TSC FAILED — abort"); sys.exit(1)
else:
    print("(no output)")

print("\n--- API nest build ---")
r3 = subprocess.run("cd ~/projects/machcore/apps/api && npx nest build", shell=True, capture_output=True, text=True)
if r3.returncode != 0:
    print(r3.stdout); print("STDERR:", r3.stderr)
    print("API BUILD FAILED — abort"); sys.exit(1)
else:
    print("(no output)")

print("\n--- pm2 restart api ---")
subprocess.run("pm2 restart machcore-api --update-env && pm2 save", shell=True)

print("\n--- git commit & push ---")
subprocess.run(
    'cd ~/projects/machcore && git add -A && git commit -m "fix: MCファイル命名 加工ID-連番+拡張子維持(例:1234-1.jpg) v50b" && git push',
    shell=True
)
print("DONE")
