#!/usr/bin/env python3
"""
fix_pg_search_scroll_v1.py
検索マッチ時にtextareaを適切にスクロールさせる修正
ta.focus() + setSelectionRange() の後に scrollTop 計算を追加
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

print("=== [1] scrollToMatch ヘルパーを追加 + execSearchQuery / handleSearchBtn に適用 ===")

# ── scrollToMatch ヘルパーを execSearchQuery の直前に追加 ──
OLD_EXEC = """\
  const execSearchQuery = (q: string, fromIndex = 0) => {"""

NEW_EXEC = """\
  // textareaの指定文字オフセット位置へスクロール（中央表示）
  const scrollToMatch = (ta: HTMLTextAreaElement, pos: number) => {
    const text   = ta.value.slice(0, pos);
    const lines  = (text.match(/\\n/g) || []).length;
    const style  = getComputedStyle(ta);
    const lh     = parseFloat(style.lineHeight) || 18;
    const pt     = parseFloat(style.paddingTop)  || 0;
    // マッチ行をビューポート中央に表示
    ta.scrollTop = Math.max(0, lines * lh + pt - ta.clientHeight / 2);
  };

  const execSearchQuery = (q: string, fromIndex = 0) => {"""

if OLD_EXEC in src:
    src = src.replace(OLD_EXEC, NEW_EXEC, 1)
    print("  OK: scrollToMatch ヘルパー追加")
else:
    print("  WARN: execSearchQuery アンカー不一致")

# ── execSearchQuery 内の ta.focus()/setSelectionRange 後に scrollToMatch を追加 ──
OLD_FOCUS_IN_EXEC = """\
      // textarea をフォーカスしてハイライト表示
      ta.focus();
      ta.setSelectionRange(positions[idx], positions[idx] + q.length);
    } catch {}
  };"""

NEW_FOCUS_IN_EXEC = """\
      // textarea をフォーカスしてハイライト表示、マッチ位置へスクロール
      ta.focus();
      ta.setSelectionRange(positions[idx], positions[idx] + q.length);
      scrollToMatch(ta, positions[idx]);
    } catch {}
  };"""

if OLD_FOCUS_IN_EXEC in src:
    src = src.replace(OLD_FOCUS_IN_EXEC, NEW_FOCUS_IN_EXEC, 1)
    print("  OK: execSearchQuery にスクロール追加")
else:
    print("  WARN: execSearchQuery フォーカスアンカー不一致")

# ── handleSearchBtn 内の次マッチ処理にも scrollToMatch を追加 ──
OLD_NEXT_IN_BTN = """\
      // 次のマッチへ（折り返しあり）
      const nextIdx = (pgMatchIndex + 1) % pgMatchPositions.length;
      setPgMatchIndex(nextIdx);
      ta.focus();
      ta.setSelectionRange(pgMatchPositions[nextIdx], pgMatchPositions[nextIdx] + pgEditorSearch.length);"""

NEW_NEXT_IN_BTN = """\
      // 次のマッチへ（折り返しあり）
      const nextIdx = (pgMatchIndex + 1) % pgMatchPositions.length;
      setPgMatchIndex(nextIdx);
      ta.focus();
      ta.setSelectionRange(pgMatchPositions[nextIdx], pgMatchPositions[nextIdx] + pgEditorSearch.length);
      scrollToMatch(ta, pgMatchPositions[nextIdx]);"""

if OLD_NEXT_IN_BTN in src:
    src = src.replace(OLD_NEXT_IN_BTN, NEW_NEXT_IN_BTN, 1)
    print("  OK: handleSearchBtn 次マッチにスクロール追加")
else:
    print("  WARN: handleSearchBtn アンカー不一致")

write_file(EDIT, src)
print(f"  edit/page.tsx: {len(src)}文字")

print("\n=== [2] Next.js build ===")
rc = run("npx next build 2>&1 | tail -25", cwd=os.path.join(BASE, "apps/web"))
if rc != 0:
    print("  ❌ ビルドエラー")
    sys.exit(1)
print("  OK")

print("\n=== [3] PM2 再起動 ===")
run("pm2 restart machcore-web")
run("pm2 list --no-color | grep machcore")

print("\n=== [4] git push ===")
run("git add -A")
run('git commit -m "fix: PGエディタ検索マッチ位置へ自動スクロール"')
run("git push origin main")

p = os.path.join(BASE, "fix_pg_search_scroll_v1.py")
if os.path.exists(p): os.remove(p); print(f"  cleaned: fix_pg_search_scroll_v1.py")

print("\n=== 完了 ===")
