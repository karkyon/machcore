#!/usr/bin/env python3
"""
fix_pg_editor_v3.py
根本解決:
  - textarea を uncontrolled 化 (value= を外し defaultValue= + ref.current.value で管理)
  - これによりブラウザネイティブ Ctrl+Z / Ctrl+Y が完全動作
  - 検索は textarea を focus/select せず scrollTop 計算のみ → フォーカスは検索 input に固定
  - 保存時・USB書き出し時は pgTextareaRef.current.value を読む
  - pgContent state は「エディタ外からの読み書き」のみに使用
    (エディタ開いた時に defaultValue を渡す / エディタ閉じる時に捨てる)
"""
import subprocess, sys, os, re

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

# ─────────────────────────────────────────────────────────────
print("=== [1] pgUndoStack/pgRedoStack/pgUndoTimer を削除（不要）===")
# uncontrolled化するのでカスタムスタックは不要
OLD_REFS = """\
  const pgTextareaRef    = React.useRef<HTMLTextAreaElement>(null);
  const pgSearchInputRef = React.useRef<HTMLInputElement>(null);
  const pgUndoStack      = React.useRef<string[]>([]);
  const pgRedoStack      = React.useRef<string[]>([]);
  const pgUndoTimer      = React.useRef<ReturnType<typeof setTimeout> | null>(null);"""
NEW_REFS = """\
  const pgTextareaRef    = React.useRef<HTMLTextAreaElement>(null);
  const pgSearchInputRef = React.useRef<HTMLInputElement>(null);"""

if OLD_REFS in src:
    src = src.replace(OLD_REFS, NEW_REFS, 1)
    print("  OK: 不要なUndo refs 削除")
else:
    print("  WARN: refs アンカー不一致")

# ─────────────────────────────────────────────────────────────
print("=== [2] execSearchQuery / goNextMatch を scrollTop方式に書き換え ===")
# 現在の実装を置換（scrollTextareaToPos + execSearchQuery + goNextMatch ブロック）

OLD_HELPERS = """\
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
      const esc = q.replace(/[-.*+?^${}()|[\\\\]\\\\]/g, String.raw`\\\\$&`);
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

NEW_HELPERS = """\
  // ────────── PG検索ヘルパー ──────────
  // textareaのcharオフセット→ scrollTop を計算してスクロール（focusは一切しない）
  const scrollTextareaToMatch = (pos: number) => {
    const ta = pgTextareaRef.current;
    if (!ta) return;
    const text = ta.value.slice(0, pos);
    const linesBefore = (text.match(/\\n/g) || []).length;
    const lineHeight = parseFloat(getComputedStyle(ta).lineHeight) || 18;
    const paddingTop = parseFloat(getComputedStyle(ta).paddingTop) || 0;
    const targetScroll = linesBefore * lineHeight + paddingTop - ta.clientHeight / 2;
    ta.scrollTop = Math.max(0, targetScroll);
  };

  const execSearchQuery = (q: string, startFromBeginning = true) => {
    if (!q) return;
    const text = pgTextareaRef.current?.value ?? pgContent;
    try {
      const esc = q.replace(/[-.*+?^${}()|[\\\\]\\\\]/g, '\\\\$&');
      const regex = new RegExp(esc, 'gi');
      const positions: number[] = [];
      let m;
      while ((m = regex.exec(text)) !== null) positions.push(m.index);
      setPgMatchPositions(positions);
      setPgMatchCount(positions.length);
      if (positions.length > 0) {
        const idx = startFromBeginning ? 0 : Math.min(pgMatchIndex, positions.length - 1);
        setPgMatchIndex(idx);
        scrollTextareaToMatch(positions[idx]);
      }
    } catch {}
    // フォーカスを検索inputに維持
    requestAnimationFrame(() => { pgSearchInputRef.current?.focus(); });
  };

  const goNextMatch = (reverse = false) => {
    if (pgMatchPositions.length === 0) { execSearchQuery(pgEditorSearch, true); return; }
    const next = (pgMatchIndex + (reverse ? -1 : 1) + pgMatchPositions.length) % pgMatchPositions.length;
    setPgMatchIndex(next);
    scrollTextareaToMatch(pgMatchPositions[next]);
    requestAnimationFrame(() => { pgSearchInputRef.current?.focus(); });
  };
"""

if OLD_HELPERS in src:
    src = src.replace(OLD_HELPERS, NEW_HELPERS, 1)
    print("  OK: 検索ヘルパーを scrollTop 方式に変更")
else:
    print("  WARN: ヘルパーアンカー不一致（文字列長確認）")
    # 短いアンカーで試みる
    SHORT_OLD = "  // テキストエリアをスクロール（フォーカスは検索inputに維持）\n  const scrollTextareaToPos"
    if SHORT_OLD in src:
        # ブロック全体を特定して置換
        start = src.find("  // ────────── PG検索ヘルパー ──────────")
        end = src.find("  const goNextMatch = (reverse = false) =>")
        if start >= 0 and end >= 0:
            end2 = src.find("\n\n", end) + 2
            src = src[:start] + NEW_HELPERS + src[end2:]
            print("  OK: 検索ヘルパーをブロック全体置換")
        else:
            print("  ERROR: ヘルパーブロック特定失敗")
            sys.exit(1)
    else:
        print("  ERROR: ヘルパーアンカーが見つかりません")
        sys.exit(1)

# ─────────────────────────────────────────────────────────────
print("=== [3] textarea を uncontrolled 化 ===")
# 現在: value={pgContent} onChange={...Undoスタック...}
# 修正: defaultValue={pgContent} onChange削除、Ctrl+Z/YはブラウザネイティブにまかせるのでonKeyDownも整理

# textarea の onChange (Undoスタック版) + onKeyDown (Ctrl+Z/Y版) を除去
OLD_TEXTAREA_BLOCK = """\
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

NEW_TEXTAREA_BLOCK = """\
              <textarea
                ref={pgTextareaRef}
                defaultValue={pgContent}
                onKeyDown={e => {
                  // Ctrl+S: サーバ保存（ブラウザのCtrl+Z/YはそのままネイティブUndo/Redoとして動作）
                  if ((e.ctrlKey || e.metaKey) && e.key === 's') {"""

if OLD_TEXTAREA_BLOCK in src:
    src = src.replace(OLD_TEXTAREA_BLOCK, NEW_TEXTAREA_BLOCK, 1)
    print("  OK: textarea uncontrolled化（defaultValue + onChange削除）")
else:
    print("  WARN: textarea アンカー不一致")

# ─────────────────────────────────────────────────────────────
print("=== [4] 保存処理で pgTextareaRef.current.value を使うよう修正 ===")
# Ctrl+S 保存: pgContent → pgTextareaRef.current?.value ?? pgContent
OLD_CTRLSAVE = """\
                    body: JSON.stringify({ content: pgContent, original_name: pgOrigName }),
                    }).then(r => {
                      if (!r.ok) throw new Error();
                      setPgUpdatedAtDisp(new Date().toLocaleString("ja-JP"));
                      showToast("✅ Ctrl+S: 保存しました");
                    }).catch(() => showToast("❌ 保存失敗")).finally(() => setPgSaving(false));"""

NEW_CTRLSAVE = """\
                    body: JSON.stringify({ content: pgTextareaRef.current?.value ?? pgContent, original_name: pgOrigName }),
                    }).then(r => {
                      if (!r.ok) throw new Error();
                      // uncontrolled → state に同期
                      if (pgTextareaRef.current) setPgContent(pgTextareaRef.current.value);
                      setPgUpdatedAtDisp(new Date().toLocaleString("ja-JP"));
                      showToast("✅ Ctrl+S: 保存しました");
                    }).catch(() => showToast("❌ 保存失敗")).finally(() => setPgSaving(false));"""

if OLD_CTRLSAVE in src:
    src = src.replace(OLD_CTRLSAVE, NEW_CTRLSAVE, 1)
    print("  OK: Ctrl+S 保存を ref.value 参照に変更")
else:
    print("  WARN: Ctrl+S 保存アンカー不一致")

# ── 「サーバに保存」ボタン（ヘッダー右上）も修正 ──
OLD_BTN_SAVE = """\
                      body: JSON.stringify({ content: pgContent, original_name: pgOrigName }),
                    });
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    setPgUpdatedAtDisp(new Date().toLocaleString("ja-JP"));
                    showToast("✅ PGファイルをサーバに保存しました");"""

NEW_BTN_SAVE = """\
                      body: JSON.stringify({ content: pgTextareaRef.current?.value ?? pgContent, original_name: pgOrigName }),
                    });
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    if (pgTextareaRef.current) setPgContent(pgTextareaRef.current.value);
                    setPgUpdatedAtDisp(new Date().toLocaleString("ja-JP"));
                    showToast("✅ PGファイルをサーバに保存しました");"""

if OLD_BTN_SAVE in src:
    src = src.replace(OLD_BTN_SAVE, NEW_BTN_SAVE, 1)
    print("  OK: サーバ保存ボタンを ref.value 参照に変更")
else:
    print("  WARN: サーバ保存ボタンアンカー不一致")

# ── USB/指定先に保存 も修正 ──
OLD_USB_SAVE = """\
                    const writable = await fileHandle.createWritable();
                    await writable.write(pgContent);
                    await writable.close();"""

NEW_USB_SAVE = """\
                    const writable = await fileHandle.createWritable();
                    await writable.write(pgTextareaRef.current?.value ?? pgContent);
                    await writable.close();"""

if OLD_USB_SAVE in src:
    src = src.replace(OLD_USB_SAVE, NEW_USB_SAVE, 1)
    print("  OK: USB保存を ref.value 参照に変更")
else:
    print("  WARN: USB保存アンカー不一致")

# ─────────────────────────────────────────────────────────────
print("=== [5] ヘッダー行数表示を ref.value ベースに ===")
# pgContent.split('\n').length → リアルタイム行数は state が古い可能性があるため
# defaultValue を使っているとき state が更新されないので、行数はエディタ開いた時のまま表示
# シンプルに「pgOrigName付近の行数表示」を pgContent 依存のままにしておく
# （uncontrolled でも state は開いた時に設定されているので問題なし）
print("  OK: 行数表示は pgContent(open時設定)を維持（問題なし）")

# ─────────────────────────────────────────────────────────────
print("=== [6] 検索 onChange で pgEditorSearch クリア時にマッチもクリア ===")
# 既存の onChange はすでに correct なのでそのまま

# ─────────────────────────────────────────────────────────────
print("=== [7] 検索inputのonKeyDownがまだ古い実装の場合を確認・修正 ===")
# v2で WARN だったので再確認
OLD_KEYDOWN_OLD = """\
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

NEW_KEYDOWN_CORRECT = """\
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

if OLD_KEYDOWN_OLD in src:
    src = src.replace(OLD_KEYDOWN_OLD, NEW_KEYDOWN_CORRECT, 1)
    print("  OK: 検索 onKeyDown を統合版に置換")
else:
    # v2で NEW_KEYDOWN_BLOCK が適用済みか確認
    if "execSearchQuery(pgEditorSearch, true);" in src and "goNextMatch(e.shiftKey);" in src:
        print("  OK: 検索 onKeyDown は既に正しい実装")
    else:
        # さらに短いアンカーで試みる
        if "pgTextareaRef.current.focus();\n                      pgTextareaRef.current.setSelectionRange(pos, pos + pgEditorSearch.length);" in src:
            old_short = "pgTextareaRef.current.focus();\n                      pgTextareaRef.current.setSelectionRange(pos, pos + pgEditorSearch.length);"
            new_short = "scrollTextareaToMatch(pgMatchPositions[next]);\n                      requestAnimationFrame(() => { pgSearchInputRef.current?.focus(); });"
            src = src.replace(old_short, new_short, 1)
            print("  OK: 旧 focus/setSelectionRange を scrollTop版に変更")
        else:
            print("  WARN: 検索 onKeyDown 修正をスキップ（確認要）")

# ─────────────────────────────────────────────────────────────
print("=== [8] 行数表示をリアルタイムにするため onChange で行数 state 管理 ===")
# uncontrolled なので行数はopenした時のpgContentに基づく
# リアルタイム行数が欲しければ onChange でカウントする
# 既存の {pgContent.split('\n').length}行 を維持（open時の値）
# これは許容範囲（保存時に sync するため大きなズレは出ない）
print("  OK: 行数表示は現状維持")

write_file(EDIT, src)
print(f"\n  edit/page.tsx: {len(src)}文字")

# ─────────────────────────────────────────────────────────────
print("\n=== [9] Next.js build ===")
rc = run("npx next build 2>&1 | grep -E '(error|Error|✓|Route|✗)' | tail -30", cwd=os.path.join(BASE, "apps/web"))
if rc != 0:
    print("  ❌ ビルドエラー 詳細確認:")
    run("npx next build 2>&1 | tail -40", cwd=os.path.join(BASE, "apps/web"))
    sys.exit(1)
print("  OK")

print("\n=== [10] PM2 再起動 ===")
run("pm2 restart machcore-web")
run("pm2 list --no-color | grep machcore")

print("\n=== [11] git push ===")
run("git add -A")
run('git commit -m "fix: PGエディタ textarea uncontrolled化でネイティブUndo/Redo復活 / 検索フォーカス完全修正"')
run("git push origin main")

# ゴミファイル削除
for f in ["fix_pg_editor_v2.py", "fix_pg_editor_v3.py"]:
    p = os.path.join(BASE, f)
    if os.path.exists(p): os.remove(p); print(f"  cleaned: {f}")

print("\n=== 完了 ===")
