#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_record_unicode_final.py
サーバ上の page.tsx の \\uXXXX リテラル問題を修正する。
バイト列レベルで \\\\u (5c 5c 75) → \\u (5c 75) に変換。
"""
import subprocess, shutil, os, sys, re

TARGET = "/home/karkyon/projects/machcore/apps/web/app/mc/[mc_id]/record/page.tsx"
REPO   = "/home/karkyon/projects/machcore"

if not os.path.exists(TARGET):
    print(f"ファイルが見つかりません: {TARGET}")
    sys.exit(1)

shutil.copy(TARGET, TARGET + ".bak_uf")

# バイト列レベルで読み込み
with open(TARGET, "rb") as f:
    raw = f.read()

lines = len(raw.splitlines())
print(f"ファイル: {len(raw)} bytes, {lines}行")

# パターン確認
dbl = raw.count(b'\\\\u')  # 5c 5c 75
sgl = raw.count(b'\\u')    # 5c 75
print(f"\\\\\\\\u (ダブル): {dbl}箇所")
print(f"\\\\u  (シングル): {sgl}箇所 (ダブル含む)")

if dbl == 0:
    print("⚠️  \\\\\\\\u パターンなし。別のパターンを確認...")
    # \\u2014 のような文字列リテラルとして書き込まれている可能性
    # UTF-8テキストとして読んで確認
    text = raw.decode("utf-8", errors="replace")
    # Pythonの文字列上で \\u (バックスラッシュ+u) を検索
    # これはファイル上の単一 \u
    matches = re.findall(r'\\u[0-9a-fA-F]{4}', text)
    print(f"テキスト上の \\uXXXX パターン: {len(matches)}箇所 (これは正常なTSのUnicodeエスケープ)")
    # 画面に表示される問題は、TSが \\u を解釈する場合
    # JSの文字列 "\\u3053" は \u3053 のリテラル（Unicodeエスケープではない）
    # JSの文字列 "\u3053" は こ（Unicodeエスケープが機能）
    # なので問題は "\\u3053" がファイルに書かれているか
    # バイト列確認: 5c 75 と 5c 5c 75
    print(f"\n正常: \\u (5c 75): {raw.count(b'\\u')} => これがTSのUnicodeエスケープとして動作")
    
    # テキストでの確認（問題のある二重バックスラッシュ）
    if '\\\\u' in text:
        cnt = text.count('\\\\u')
        print(f"文字列レベル \\\\\\\\u: {cnt}箇所 → これが問題")
        fixed_text = re.sub(r'\\\\u([0-9a-fA-F]{4})', r'\\u\1', text)
        with open(TARGET, "w", encoding="utf-8") as f:
            f.write(fixed_text)
        print(f"✅ 文字列レベル修正: {len(fixed_text.splitlines())}行")
    else:
        print("✅ 文字列レベルでも問題なし。ファイルは正常です。")
        os.remove(TARGET + ".bak_uf")
        sys.exit(0)
else:
    # バイト列で置換: 5c 5c 75 → 5c 75
    fixed = raw.replace(b'\\\\u', b'\\u')
    print(f"\\\\\\\\u → \\\\u 置換: {dbl}箇所")
    with open(TARGET, "wb") as f:
        f.write(fixed)
    print(f"✅ バイト列修正: {len(fixed.splitlines())}行")

# tsc
print("--- tsc --noEmit ---")
r = subprocess.run(["npx", "tsc", "--noEmit"],
    cwd=f"{REPO}/apps/web",
    capture_output=True, text=True)
if r.returncode != 0:
    print("❌ tsc エラー:")
    print((r.stdout + r.stderr)[-3000:])
    shutil.copy(TARGET + ".bak_uf", TARGET)
    print("⏪ ロールバック")
    sys.exit(1)
print("✅ tsc OK")

# next build
print("--- next build ---")
r = subprocess.run(["npx", "next", "build"],
    cwd=f"{REPO}/apps/web",
    capture_output=True, text=True)
if r.returncode != 0:
    print("❌ next build エラー:")
    print((r.stdout + r.stderr)[-2000:])
    shutil.copy(TARGET + ".bak_uf", TARGET)
    print("⏪ ロールバック")
    sys.exit(1)
print("✅ next build OK")

subprocess.run(["pm2", "restart", "machcore-web"], capture_output=True, text=True)
print("✅ pm2 restart")

subprocess.run(["git", "add", "-A"], cwd=REPO)
subprocess.run(["git", "commit", "-m", "fix: record page - resolve unicode literal escape issue"],
    cwd=REPO)
r2 = subprocess.run(["git", "push"], cwd=REPO, capture_output=True, text=True)
print("✅ git push\n" + (r2.stderr.strip() or r2.stdout.strip()))

os.remove(TARGET + ".bak_uf")
print("✅ 完了")
