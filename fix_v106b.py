#!/usr/bin/env python3
"""
fix_v106b.py - ツーリング折り返し+縮小修正（正規表現問題を回避）
"""
import subprocess, sys, os

PROJECT = os.path.expanduser("~/projects/machcore")
SVC     = f"{PROJECT}/apps/api/src/mc/mc.service.ts"
src     = open(SVC, encoding="utf-8").read()

# 問題のある wrapTextInWidth の正規表現を文字列split方式に変更
OLD_WRAP = r"        for (const raw of text.split(/\r\n|\n/g)) {"
NEW_WRAP =  "        const rawLines = text.split('\\n').flatMap((l:string) => l.split('\\r')).filter((_:string,i:number,a:string[]) => i===0||a[i-1]!=='');"
NEW_WRAP2 = "        for (const raw of rawLines) {"

# まず正規表現splitをflatMap方式に置換
if OLD_WRAP in src:
    src2 = src.replace(OLD_WRAP,
        "        const rawLines2 = text.replace(/\\r\\n/g,'\\n').replace(/\\r/g,'\\n').split('\\n');\n" +
        "        for (const raw of rawLines2) {", 1)
    open(SVC, "w", encoding="utf-8").write(src2)
    print("OK: 正規表現をsplit方式に変更")
else:
    # 既に変換済みか別のパターン - 直接grep確認
    import subprocess as sp
    r = sp.run(["grep", "-n", "wrapTextInWidth", SVC], capture_output=True, text=True)
    print("wrapTextInWidth行:", r.stdout[:500])
    r2 = sp.run(["grep", "-n", r"text\.split\(\/", SVC], capture_output=True, text=True)
    print("split(/行:", r2.stdout[:500])
    print("WARNING: パターン未検出")

# ビルド確認
src_now = open(SVC, encoding="utf-8").read()
print("--- ビルド ---")
r = subprocess.run(["npx","tsc","--noEmit","-p","apps/api/tsconfig.json"],
    capture_output=True, text=True, cwd=PROJECT)
errors = [l for l in r.stdout.splitlines()+r.stderr.splitlines() if "error TS" in l]
if errors:
    print(f"TSエラー: {len(errors)}件"); [print(f"  {e}") for e in errors[:10]]
    open(SVC,"w",encoding="utf-8").write(src); sys.exit(1)
print("TypeScriptエラー: 0件")

nest_candidates = [f"{PROJECT}/node_modules/.bin/nest", f"{PROJECT}/apps/api/node_modules/.bin/nest"]
nest_bin = next((p for p in nest_candidates if os.path.exists(p)), None)
if not nest_bin:
    found = subprocess.run(["find",PROJECT,"-path","*/node_modules/.bin/nest",
        "-not","-path","*/node_modules/*/node_modules/*"],
        capture_output=True,text=True).stdout.strip().split('\n')
    nest_bin = next((p for p in found if p.strip()), None)
if nest_bin:
    r2 = subprocess.run([nest_bin,"build","api"],capture_output=True,text=True,cwd=f"{PROJECT}/apps/api")
    if r2.returncode != 0:
        print(f"nest build 失敗: {(r2.stdout+r2.stderr)[:300]}")
        open(SVC,"w",encoding="utf-8").write(src); sys.exit(1)
    print("nest build 成功!")

subprocess.run(["pm2","restart","machcore-api"], capture_output=True, cwd=PROJECT)
print("PM2再起動完了")
subprocess.run(["git","add","-A"], cwd=PROJECT)
subprocess.run(["git","commit","-m","fix_v106b: ツーリング折り返し正規表現修正"], cwd=PROJECT)
r3 = subprocess.run(["git","push"],capture_output=True,text=True,cwd=PROJECT)
print("fix_v106b 完了" if r3.returncode==0 else f"push警告: {r3.stderr[:100]}")
