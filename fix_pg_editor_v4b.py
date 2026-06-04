#!/usr/bin/env python3
"""
fix_pg_editor_v4b.py
ビルドエラー修正:
1. edit/page.tsx 239行: 正規表現リテラルのエスケープが壊れている
   /[-.*+?^${}()|[\]\]/g → new RegExp(...) に変更して文字列として安全に渡す
2. JSX の onKeyDown に余分な } がある可能性を修正
"""
import subprocess, sys, os

BASE = os.path.expanduser("~/projects/machcore")

def read_file(rel):
    return open(os.path.join(BASE, rel), encoding="utf-8").read()

def write_file(rel, content):
    open(os.path.join(BASE, rel), "w", encoding="utf-8").write(content)

def run(cmd, cwd=None):
    r = subprocess.run(cmd, shell=True, cwd=cwd or BASE, capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout.strip())
    if r.stderr.strip(): print(r.stderr.strip(), file=sys.stderr)
    return r.returncode

EDIT = "apps/web/app/mc/[mc_id]/edit/page.tsx"
src = read_file(EDIT)

print("=== [1] execSearchQuery の正規表現を文字列ベースに修正 ===")
# 壊れたパターンを全候補で修正
BAD_PATTERNS = [
    'q.replace(/[-.*+?^${}()|[\\]\\]/g, "\\\\$&")',
    'q.replace(/[-.*+?^${}()|[\\]\\]/g, "\\$&")',
    "q.replace(/[-.*+?^${}()|[\\]\\]/g, '\\\\$&')",
    "q.replace(/[-.*+?^${}()|[\\]\\]/g, '\\$&')",
    'q.replace(/[-.\\*\\+\\?\\^\\$\\{\\}\\(\\)|\\[\\]\\\\]/g, "\\\\$&")',
]

GOOD = 'q.replace(new RegExp("[\\\\-\\\\.\\\\*\\\\+\\\\?\\\\^\\\\$\\\\{\\\\}\\\\(\\\\)\\\\|\\\\[\\\\]\\\\\\\\]", "g"), "\\\\$&")'

# まず現在の正規表現箇所を確認
import re as re_mod
# execSearchQuery内のesc行を探す
esc_match = re_mod.search(r'const esc\s*=\s*q\.replace\([^;]+;', src)
if esc_match:
    old_esc = esc_match.group(0)
    print(f"  現在のesc行: {old_esc[:80]}...")
    new_esc = 'const esc  = q.replace(new RegExp("[-.*+?^${}()|\\\\[\\\\]\\\\\\\\]", "g"), "\\\\$&");'
    src = src[:esc_match.start()] + new_esc + src[esc_match.end():]
    print("  OK: esc行を RegExp文字列に修正")
else:
    print("  WARN: esc行が見つからない")
    for p in BAD_PATTERNS:
        if p in src:
            new_esc = 'q.replace(new RegExp("[-.*+?^${}()|\\\\[\\\\]\\\\\\\\]", "g"), "\\\\$&")'
            src = src.replace(p, new_esc, 1)
            print(f"  OK: バッドパターン修正: {p[:50]}...")
            break

print("=== [2] JSX onKeyDown の余分な } を修正 ===")
# `}}` が `}}}` になっている箇所（onKeyDown の閉じ括弧 + JSX属性の閉じ）
# onKeyDown={e => { ... }}} → onKeyDown={e => { ... }}
# 具体的には検索input の onKeyDown のあとの "}}" が "}}}になっている場合
if "}}\n                  ref={pgSearchInputRef}" in src:
    src = src.replace(
        "}}\n                  ref={pgSearchInputRef}",
        "}\n                  ref={pgSearchInputRef}",
        1
    )
    print("  OK: 余分な } 削除 (ref前)")
elif "}}\n                  placeholder=" in src:
    # onKeyDown の閉じ数を確認
    # 正常: onKeyDown={e => { if(...){...} }} の }} → JSX属性の }
    pass

# pgSearchInputRef が削除されたにも関わらず残っている場合も修正
if "ref={pgSearchInputRef}" in src:
    src = src.replace(
        "                  ref={pgSearchInputRef}\n",
        "",
        1
    )
    print("  OK: 不要な ref={pgSearchInputRef} 削除")
else:
    print("  OK: pgSearchInputRef は既にない")

# placeholder も旧来のものが残っていれば修正
if 'placeholder="検索キーワードを入力（Enter: 検索/次へ）"' in src:
    src = src.replace(
        'placeholder="検索キーワードを入力（Enter: 検索/次へ）"',
        'placeholder="キーワードを入力 → 検索ボタンで次へ"',
        1
    )
    print("  OK: placeholder テキスト更新")

write_file(EDIT, src)
print(f"  edit/page.tsx: {len(src)}文字")

print("\n=== [3] Next.js build ===")
rc = run("npx next build 2>&1 | tail -35", cwd=os.path.join(BASE, "apps/web"))
if rc != 0:
    print("  ❌ ビルドエラー継続")
    sys.exit(1)
print("  OK")

print("\n=== [4] PM2 再起動 ===")
run("pm2 restart machcore-web")
run("pm2 list --no-color | grep machcore")

print("\n=== [5] git push ===")
run("git add -A")
run('git commit -m "fix: PGエディタ正規表現エスケープ修正 / JSX構文修正"')
run("git push origin main")

for f in ["fix_pg_editor_v4b.py"]:
    p = os.path.join(BASE, f)
    if os.path.exists(p): os.remove(p); print(f"  cleaned: {f}")

print("\n=== 完了 ===")
