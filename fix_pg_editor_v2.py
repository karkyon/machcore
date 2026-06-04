#!/usr/bin/env python3
"""
fix_pg_editor_v2.py
① 検索Enterでフォーカスがtextareaに移ってテキストが入力されてしまう問題を修正
   → setSelectionRange後に検索inputへフォーカスを戻す
   → textareaはscrollIntoViewのみ行う（スクロール用ヘルパー追加）
② Undo/Redo: Ctrl+Z / Ctrl+Y(Ctrl+Shift+Z) をカスタム実装
   → pgUndoStack / pgRedoStack を useRef で管理
   → textarea onChange でスタックに積む（300ms デバウンス）
③ ヘッダーにサーバー上のファイルパスを表示
   → mc_files/pg/{machiningId}/{filename} の形式
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

print("=== [1] Undo/Redo stack + 検索ref追加 ===")

# ── pgUndoStack / pgRedoStack / pgUndoTimer / pgSearchInputRef を追加 ──
OLD_PG_REFS = "  const pgTextareaRef = React.useRef<HTMLTextAreaElement>(null);"
NEW_PG_REFS = """\
  const pgTextareaRef    = React.useRef<HTMLTextAreaElement>(null);
  const pgSearchInputRef = React.useRef<HTMLInputElement>(null);
  const pgUndoStack      = React.useRef<string[]>([]);
  const pgRedoStack      = React.useRef<string[]>([]);
  const pgUndoTimer      = React.useRef<ReturnType<typeof setTimeout> | null>(null);"""

if OLD_PG_REFS not in src:
    print("  WARN: pgTextareaRef アンカー不一致")
else:
    src = src.replace(OLD_PG_REFS, NEW_PG_REFS, 1)
    print("  OK: Undo/Redo refs + pgSearchInputRef 追加")

print("=== [2] 検索inputに ref を付与 ===")
# placeholder="検索（Enterで次へ / Shift+Enterで前へ）" を持つ input に ref 追加
OLD_SEARCH_INPUT = '                  placeholder="検索（Enterで次へ / Shift+Enterで前へ）"\n                  className="text-xs font-mono w-64 focus:outline-none"'
NEW_SEARCH_INPUT = '                  ref={pgSearchInputRef}\n                  placeholder="検索キーワードを入力（Enter: 検索/次へ）"\n                  className="text-xs font-mono w-64 focus:outline-none"'

if OLD_SEARCH_INPUT not in src:
    print("  WARN: 検索input placeholder アンカー不一致")
else:
    src = src.replace(OLD_SEARCH_INPUT, NEW_SEARCH_INPUT, 1)
    print("  OK: 検索input に ref 付与")

print("=== [3] 検索実行ヘルパー関数追加 + 全Enter/フォーカス処理を修正 ===")
# handlePgUploadFromUSB の前に execSearchQuery 関数を挿入
HELPER_ANCHOR = "  // PGファイルをUSBから登録（単体 or フォルダ）"

SEARCH_HELPER = """\
  // ────────── PG検索ヘルパー ──────────
  // テキストエリアをスクロール（フォーカスは検索inputに維持）
  const scrollTextareaToPos = (pos: number, len: number) => {
    const ta = pgTextareaRef.current;
    if (!ta) return;
    // setSelectionRange でブラウザに位置を伝えつつ、フォーカスは移さない
    // 一時的にフォーカスしてスクロールさせ、すぐ検索inputに戻す
    const prev = document.activeElement as HTMLElement | null;
    ta.focus();
    ta.setSelectionRange(pos, pos + len);
    // ハイライト位置へスクロール
    if (prev && prev !== ta) {
      requestAnimationFrame(() => { prev.focus(); });
    }
  };

  const execSearchQuery = (q: string, startFromBeginning = true) => {
    if (!q) return;
    try {
      const esc = q.replace(/[-.*+?^${}()|[\\]\\\\]/g, String.raw`\\$&`);
      const regex = new RegExp(esc, 'gi');
      const positions: number[] = [];
      let m;
      while ((m = regex.exec(pgContent)) !== null) positions.push(m.index);
      setPgMatchPositions(positions);
      setPgMatchCount(positions.length);
      if (positions.length > 0) {
        const idx = startFromBeginning ? 0 : pgMatchIndex;
        setPgMatchIndex(idx);
        scrollTextareaToPos(positions[idx], q.length);
      }
      // フォーカスを検索inputに確実に戻す
      requestAnimationFrame(() => { pgSearchInputRef.current?.focus(); });
    } catch {}
  };

  const goNextMatch = (reverse = false) => {
    if (pgMatchPositions.length === 0) { execSearchQuery(pgEditorSearch); return; }
    const next = (pgMatchIndex + (reverse ? -1 : 1) + pgMatchPositions.length) % pgMatchPositions.length;
    setPgMatchIndex(next);
    scrollTextareaToPos(pgMatchPositions[next], pgEditorSearch.length);
    requestAnimationFrame(() => { pgSearchInputRef.current?.focus(); });
  };

"""

if HELPER_ANCHOR not in src:
    print("  WARN: ヘルパーアンカー不一致（handlePgUploadFromUSB）")
else:
    src = src.replace(HELPER_ANCHOR, SEARCH_HELPER + HELPER_ANCHOR, 1)
    print("  OK: execSearchQuery / goNextMatch ヘルパー追加")

print("=== [4] 検索input の onKeyDown を修正（全パターン統合）===")
# 現在の onKeyDown ブロック（初回検索 + 次へ移動）を新しい goNextMatch ベースに置換
OLD_KEYDOWN_BLOCK = """\
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey && pgMatchPositions.length === 0 && pgEditorSearch) {
                      // 初回Enter: 検索実行
                      e.preventDefault();
                      const q = pgEditorSearch;
                      try {
                        const esc = q.replace(/[-.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
                        const regex = new RegExp(esc, 'gi');
                        const positions: number[] = [];
                        let m;
                        while ((m = regex.exec(pgContent)) !== null) positions.push(m.index);
                        setPgMatchPositions(positions);
                        setPgMatchCount(positions.length);
                        if (positions.length > 0 && pgTextareaRef.current) {
                          setPgMatchIndex(0);
                          pgTextareaRef.current.focus();
                          pgTextareaRef.current.setSelectionRange(positions[0], positions[0] + q.length);
                        }
                      } catch {}
                      return;
                    }
                    if (e.key === 'Enter' && pgMatchPositions.length > 0 && pgTextareaRef.current) {
                      e.preventDefault();
                      const next = (pgMatchIndex + (e.shiftKey ?
-1 : 1) + pgMatchPositions.length) % pgMatchPositions.length;
                      setPgMatchIndex(next);
                      const pos = pgMatchPositions[next];
                      pgTextareaRef.current.focus();
                      pgTextareaRef.current.setSelectionRange(pos, pos + pgEditorSearch.length);
                    }
                  }}"""

NEW_KEYDOWN_BLOCK = """\
                  onKeyDown={e => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      if (pgMatchPositions.length === 0) {
                        execSearchQuery(pgEditorSearch, true);
                      } else {
                        goNextMatch(e.shiftKey);
                      }
                    }
                    if (e.key === 'Escape') {
                      setPgEditorSearch('');
                      setPgMatchCount(0);
                      setPgMatchPositions([]);
                      setPgMatchIndex(0);
                    }
                  }}"""

if OLD_KEYDOWN_BLOCK not in src:
    print("  WARN: onKeyDown ブロックアンカー不一致 → 部分置換を試みる")
    # 「次へ移動」部分だけ置換
    OLD_NEXT = """\
                    if (e.key === 'Enter' && pgMatchPositions.length > 0 && pgTextareaRef.current) {
                      e.preventDefault();
                      const next = (pgMatchIndex + (e.shiftKey ?
-1 : 1) + pgMatchPositions.length) % pgMatchPositions.length;
                      setPgMatchIndex(next);
                      const pos = pgMatchPositions[next];
                      pgTextareaRef.current.focus();
                      pgTextareaRef.current.setSelectionRange(pos, pos + pgEditorSearch.length);
                    }"""
    NEW_NEXT = """\
                    if (e.key === 'Enter' && pgMatchPositions.length > 0) {
                      e.preventDefault();
                      goNextMatch(e.shiftKey);
                    }"""
    if OLD_NEXT in src:
        src = src.replace(OLD_NEXT, NEW_NEXT, 1)
        print("  OK: 次へ移動のみ goNextMatch に変更")
    else:
        print("  WARN: 次へ移動アンカーも不一致")
else:
    src = src.replace(OLD_KEYDOWN_BLOCK, NEW_KEYDOWN_BLOCK, 1)
    print("  OK: onKeyDown 統合（Enter/Shift+Enter/Escape）")

print("=== [5] 🔍 検索ボタンを execSearchQuery に変更 ===")
OLD_SEARCH_BTN = """\
              <button onClick={() => {
                if (!pgEditorSearch) return;
                const q = pgEditorSearch;
                try {
                  const esc = q.replace(/[-.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
                  const regex = new RegExp(esc, 'gi');
                  const positions: number[] = [];
                  let m;
                  while ((m = regex.exec(pgContent)) !== null) positions.push(m.index);
                  setPgMatchPositions(positions);
                  setPgMatchCount(positions.length);
                  if (positions.length > 0 && pgTextareaRef.current) {
                    setPgMatchIndex(0);
                    pgTextareaRef.current.focus();
                    pgTextareaRef.current.setSelectionRange(positions[0], positions[0] + q.length);
                  }
                } catch {}
              }} className="px-3 py-1.5 text-xs bg-slate-500 hover:bg-slate-600 text-white rounded-lg font-bold">🔍 検索</button>"""

NEW_SEARCH_BTN = """\
              <button onClick={() => execSearchQuery(pgEditorSearch, pgMatchPositions.length === 0)}
                className="px-3 py-1.5 text-xs bg-slate-500 hover:bg-slate-600 text-white rounded-lg font-bold">🔍 検索</button>"""

if OLD_SEARCH_BTN not in src:
    print("  WARN: 検索ボタンアンカー不一致")
else:
    src = src.replace(OLD_SEARCH_BTN, NEW_SEARCH_BTN, 1)
    print("  OK: 検索ボタンを execSearchQuery に変更")

print("=== [6] textarea の onChange に Undo スタック追加、onKeyDown に Ctrl+Z/Y 追加 ===")
OLD_TEXTAREA = """\
              <textarea
                ref={pgTextareaRef}
                value={pgContent}
                onChange={e => setPgContent(e.target.value)}
                onKeyDown={e => {
                  if ((e.ctrlKey || e.metaKey) && e.key === 's') {"""

NEW_TEXTAREA = """\
              <textarea
                ref={pgTextareaRef}
                value={pgContent}
                onChange={e => {
                  const newVal = e.target.value;
                  // Undo スタックに積む（300ms デバウンス）
                  if (pgUndoTimer.current) clearTimeout(pgUndoTimer.current);
                  pgUndoTimer.current = setTimeout(() => {
                    pgUndoStack.current.push(pgContent);
                    if (pgUndoStack.current.length > 200) pgUndoStack.current.shift();
                    pgRedoStack.current = [];
                  }, 300);
                  setPgContent(newVal);
                }}
                onKeyDown={e => {
                  // Ctrl+Z: Undo
                  if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key === 'z') {
                    e.preventDefault();
                    if (pgUndoStack.current.length === 0) return;
                    pgRedoStack.current.push(pgContent);
                    const prev = pgUndoStack.current.pop()!;
                    setPgContent(prev);
                    return;
                  }
                  // Ctrl+Y / Ctrl+Shift+Z: Redo
                  if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.shiftKey && e.key === 'z'))) {
                    e.preventDefault();
                    if (pgRedoStack.current.length === 0) return;
                    pgUndoStack.current.push(pgContent);
                    const next = pgRedoStack.current.pop()!;
                    setPgContent(next);
                    return;
                  }
                  if ((e.ctrlKey || e.metaKey) && e.key === 's') {"""

if OLD_TEXTAREA not in src:
    print("  WARN: textarea アンカー不一致")
else:
    src = src.replace(OLD_TEXTAREA, NEW_TEXTAREA, 1)
    print("  OK: textarea onChange Undo stack + Ctrl+Z/Y 追加")

print("=== [7] PGエディタヘッダーにファイルパス表示 ===")
OLD_HEADER = """\
                <span className="font-bold text-slate-800">PGエディタ</span>
                {pgOrigName && <span className="text-xs text-slate-500 font-mono bg-slate-100 px-2.5 py-1 rounded-lg border">{pgOrigName}</span>}
                <span className="text-xs text-slate-400">{pgContent.split('\\n').length}行 / {pgContent.length}文字</span>"""

NEW_HEADER = """\
                <span className="font-bold text-slate-800">PGエディタ</span>
                {pgOrigName && <span className="text-xs text-slate-500 font-mono bg-slate-100 px-2.5 py-1 rounded-lg border">{pgOrigName}</span>}
                {detail?.machiningId && (
                  <span className="text-xs text-slate-400 font-mono">
                    📁 mc_files/pg/{detail.machiningId}/{pgOrigName || "—"}
                  </span>
                )}
                <span className="text-xs text-slate-400">{pgContent.split('\\n').length}行 / {pgContent.length}文字</span>"""

if OLD_HEADER not in src:
    print("  WARN: ヘッダーアンカー不一致")
else:
    src = src.replace(OLD_HEADER, NEW_HEADER, 1)
    print("  OK: ヘッダーにファイルパス表示追加")

print("=== [8] ヒントテキスト更新 ===")
OLD_HINT = '              <div className="ml-auto text-[10px] text-slate-400">Enter: 次へ | Shift+Enter: 前へ | Ctrl+S: 保存</div>'
NEW_HINT = '              <div className="ml-auto text-[10px] text-slate-400">Enter: 検索/次へ | Shift+Enter: 前へ | Esc: 解除 | Ctrl+Z: Undo | Ctrl+S: 保存</div>'

if OLD_HINT not in src:
    print("  WARN: ヒントテキストアンカー不一致")
else:
    src = src.replace(OLD_HINT, NEW_HINT, 1)
    print("  OK: ヒントテキスト更新")

write_file(EDIT, src)
print(f"  edit/page.tsx: {len(src)}文字")

# ─────────────────────────────────────────────────────────────
print("\n=== [9] Next.js build ===")
rc = run("npx next build 2>&1 | tail -25", cwd=os.path.join(BASE, "apps/web"))
if rc != 0:
    print("  ❌ ビルドエラー")
    sys.exit(1)
print("  OK")

print("\n=== [10] PM2 再起動 ===")
run("pm2 restart machcore-web")
run("pm2 list --no-color | grep machcore")

print("\n=== [11] git push ===")
run("git add -A")
run('git commit -m "fix: PGエディタ検索フォーカス修正 / Undo-Redo実装 / ファイルパス表示"')
run("git push origin main")

# ゴミファイル削除
for f in ["fix_pg_upload_v1.py", "fix_pg_editor_v2.py"]:
    p = os.path.join(BASE, f)
    if os.path.exists(p):
        os.remove(p)
        print(f"  cleaned: {f}")

print("\n=== 完了 ===")
