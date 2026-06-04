#!/usr/bin/env python3
"""
fix_pg_editor_v4.py
設計方針:
  1. textarea は controlled (value={pgContent}) に戻す
     - 置換・全置換が正しく動作するために必要
  2. Undo/Redo: カスタムスタック実装
     - Ctrl+Z/Y をインターセプトしてスタックから復元
     - onChange でデバウンスなしに即スタックへ積む（1文字1スタックは重いので500ms間隔）
     - スタックサイズ上限200
  3. 検索ハイライト: textarea.setSelectionRange を使う
     - 検索ボタンを押すたびに次のマッチへ移動 (=連続検索)
     - textareaにフォーカスが移るのは許容（選択ハイライトが見えることが優先）
     - searchInputからfocusを移さないためのhackは廃止（不安定だった）
  4. LIGHT/DARK 切り替え: pgDarkMode state で管理
  5. onKeyDown から Enter 検索を廃止（検索ボタンのみ）
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

# ═══════════════════════════════════════════════════════
print("=== [1] refs/state 整理 ===")
# pgSearchInputRef は不要に (focusを検索inputに固定する設計をやめる)
# pgDarkMode state 追加
# Undo/Redo スタック ref 追加
OLD_REFS = """\
  const pgTextareaRef    = React.useRef<HTMLTextAreaElement>(null);
  const pgSearchInputRef = React.useRef<HTMLInputElement>(null);"""
NEW_REFS = """\
  const pgTextareaRef    = React.useRef<HTMLTextAreaElement>(null);
  // Undo/Redo スタック
  const pgUndoStack      = React.useRef<string[]>([]);
  const pgRedoStack      = React.useRef<string[]>([]);
  const pgLastPush       = React.useRef<number>(0);"""

if OLD_REFS in src:
    src = src.replace(OLD_REFS, NEW_REFS, 1)
    print("  OK: refs 整理")
else:
    print("  WARN: refs アンカー不一致")

OLD_PG_CONTENT_STATE = "  const [pgEditorSearch,  setPgEditorSearch]  = useState(\"\");"
NEW_PG_CONTENT_STATE = """\
  const [pgEditorSearch,  setPgEditorSearch]  = useState("");
  const [pgDarkMode,      setPgDarkMode]      = useState(true);"""

if OLD_PG_CONTENT_STATE in src:
    src = src.replace(OLD_PG_CONTENT_STATE, NEW_PG_CONTENT_STATE, 1)
    print("  OK: pgDarkMode state 追加")
else:
    print("  WARN: pgEditorSearch state アンカー不一致")

# ═══════════════════════════════════════════════════════
print("=== [2] PG検索ヘルパーブロックを完全置換 ===")
HELPERS_START = "  // ────────── PG検索ヘルパー ──────────"
HELPERS_END_MARKER = "  // PGファイルをUSBから登録（単体 or フォルダ）"

start_idx = src.find(HELPERS_START)
end_idx   = src.find(HELPERS_END_MARKER)

if start_idx < 0 or end_idx < 0:
    print(f"  ERROR: ヘルパーブロック特定失敗 start={start_idx} end={end_idx}")
    sys.exit(1)

NEW_HELPERS = """\
  // ────────── PG検索ヘルパー ──────────
  const execSearchQuery = (q: string, fromIndex = 0) => {
    if (!q || !pgTextareaRef.current) return;
    const ta   = pgTextareaRef.current;
    const text = ta.value;            // textarea の実際の値
    try {
      const esc  = q.replace(/[-.*+?^${}()|[\\]\\]/g, "\\\\$&");
      const regex = new RegExp(esc, "gi");
      const positions: number[] = [];
      let m: RegExpExecArray | null;
      while ((m = regex.exec(text)) !== null) positions.push(m.index);
      setPgMatchPositions(positions);
      setPgMatchCount(positions.length);
      if (positions.length === 0) return;
      // fromIndex を超える最初のマッチ（なければ先頭に折り返し）
      let idx = positions.findIndex(p => p >= fromIndex);
      if (idx === -1) idx = 0;
      setPgMatchIndex(idx);
      // textarea をフォーカスしてハイライト表示
      ta.focus();
      ta.setSelectionRange(positions[idx], positions[idx] + q.length);
    } catch {}
  };

  // 検索ボタン押下: 連続クリックで次のマッチへ
  const handleSearchBtn = () => {
    if (!pgEditorSearch) return;
    const ta = pgTextareaRef.current;
    if (!ta) return;
    if (pgMatchPositions.length === 0) {
      // 初回: 先頭から検索
      execSearchQuery(pgEditorSearch, 0);
    } else {
      // 次のマッチへ（折り返しあり）
      const nextIdx = (pgMatchIndex + 1) % pgMatchPositions.length;
      setPgMatchIndex(nextIdx);
      ta.focus();
      ta.setSelectionRange(pgMatchPositions[nextIdx], pgMatchPositions[nextIdx] + pgEditorSearch.length);
    }
  };

  // Undo: スタックから1つ戻す
  const pgUndo = () => {
    if (pgUndoStack.current.length === 0) return;
    pgRedoStack.current.push(pgContent);
    const prev = pgUndoStack.current.pop()!;
    setPgContent(prev);
    requestAnimationFrame(() => { pgTextareaRef.current?.focus(); });
  };

  // Redo: スタックから1つ進める
  const pgRedo = () => {
    if (pgRedoStack.current.length === 0) return;
    pgUndoStack.current.push(pgContent);
    const next = pgRedoStack.current.pop()!;
    setPgContent(next);
    requestAnimationFrame(() => { pgTextareaRef.current?.focus(); });
  };

"""

src = src[:start_idx] + NEW_HELPERS + src[end_idx:]
print("  OK: PG検索ヘルパーブロック完全置換")

# ═══════════════════════════════════════════════════════
print("=== [3] textarea を controlled + onChange(Undo) + onKeyDown(Ctrl+Z/Y/S) に変更 ===")
OLD_TEXTAREA = """\
              <textarea
                ref={pgTextareaRef}
                defaultValue={pgContent}
                onKeyDown={e => {
                  // Ctrl+S: サーバ保存（ブラウザのCtrl+Z/YはそのままネイティブUndo/Redoとして動作）
                  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                    e.preventDefault();
                    if (!token || pgSaving) return;
                    setPgSaving(true);
                    fetch(`/api/mc/${mcId}/pg-content`, {
                      method: "PUT",
                      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                      body: JSON.stringify({ content: pgTextareaRef.current?.value ?? pgContent, original_name: pgOrigName }),
                    }).then(r => {
                      if (!r.ok) throw new Error();
                      // uncontrolled → state に同期
                      if (pgTextareaRef.current) setPgContent(pgTextareaRef.current.value);
                      setPgUpdatedAtDisp(new Date().toLocaleString("ja-JP"));
                      showToast("✅ Ctrl+S: 保存しました");
                    }).catch(() => showToast("❌ 保存失敗")).finally(() => setPgSaving(false));
                  }
                }}
                className="w-full h-full p-5 font-mono text-sm text-green-300 bg-slate-900 resize-none focus:outline-none leading-relaxed"
                spellCheck={false}
              />"""

NEW_TEXTAREA = """\
              <textarea
                ref={pgTextareaRef}
                value={pgContent}
                onChange={e => {
                  const newVal = e.target.value;
                  const now = Date.now();
                  // 500ms 以上経過したらスタックに積む（細かい入力は1エントリにまとめる）
                  if (now - pgLastPush.current > 500) {
                    pgUndoStack.current.push(pgContent);
                    if (pgUndoStack.current.length > 200) pgUndoStack.current.shift();
                    pgRedoStack.current = [];
                    pgLastPush.current = now;
                  }
                  setPgContent(newVal);
                  // 検索結果をリセット（テキスト変更後は再検索が必要）
                  if (pgMatchPositions.length > 0) {
                    setPgMatchPositions([]);
                    setPgMatchCount(0);
                    setPgMatchIndex(0);
                  }
                }}
                onKeyDown={e => {
                  // Ctrl+Z: Undo
                  if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key === 'z') {
                    e.preventDefault();
                    pgUndo();
                    return;
                  }
                  // Ctrl+Y / Ctrl+Shift+Z: Redo
                  if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.shiftKey && e.key === 'z'))) {
                    e.preventDefault();
                    pgRedo();
                    return;
                  }
                  // Ctrl+S: サーバ保存
                  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                    e.preventDefault();
                    if (!token || pgSaving) return;
                    setPgSaving(true);
                    fetch(`/api/mc/${mcId}/pg-content`, {
                      method: "PUT",
                      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                      body: JSON.stringify({ content: pgContent, original_name: pgOrigName }),
                    }).then(r => {
                      if (!r.ok) throw new Error();
                      setPgUpdatedAtDisp(new Date().toLocaleString("ja-JP"));
                      showToast("✅ Ctrl+S: 保存しました");
                    }).catch(() => showToast("❌ 保存失敗")).finally(() => setPgSaving(false));
                  }
                }}
                className={`w-full h-full p-5 font-mono text-sm resize-none focus:outline-none leading-relaxed ${
                  pgDarkMode
                    ? "text-green-300 bg-slate-900"
                    : "text-slate-800 bg-white border border-slate-200"
                }`}
                spellCheck={false}
              />"""

if OLD_TEXTAREA in src:
    src = src.replace(OLD_TEXTAREA, NEW_TEXTAREA, 1)
    print("  OK: textarea controlled化 + Undo/Redo + onKeyDown 完成")
else:
    print("  WARN: textarea アンカー不一致 → 部分修正を試みる")
    # defaultValue → value + onChange 追加
    if "defaultValue={pgContent}" in src:
        src = src.replace(
            "defaultValue={pgContent}",
            "value={pgContent}\n                onChange={e => { const n=Date.now(); if(n-pgLastPush.current>500){pgUndoStack.current.push(pgContent); if(pgUndoStack.current.length>200)pgUndoStack.current.shift(); pgRedoStack.current=[]; pgLastPush.current=n;} setPgContent(e.target.value); if(pgMatchPositions.length>0){setPgMatchPositions([]);setPgMatchCount(0);setPgMatchIndex(0);} }}",
            1
        )
        print("  OK: defaultValue→value+onChange 部分修正")

# ═══════════════════════════════════════════════════════
print("=== [4] サーバ保存ボタンを pgContent 参照に統一 ===")
# uncontrolled 時代の ref.value 参照を pgContent に戻す
src = src.replace(
    "body: JSON.stringify({ content: pgTextareaRef.current?.value ?? pgContent, original_name: pgOrigName }),\n                    });",
    "body: JSON.stringify({ content: pgContent, original_name: pgOrigName }),\n                    });",
)
src = src.replace(
    "if (pgTextareaRef.current) setPgContent(pgTextareaRef.current.value);\n                    setPgUpdatedAtDisp",
    "setPgUpdatedAtDisp",
)
# USB保存
src = src.replace(
    "await writable.write(pgTextareaRef.current?.value ?? pgContent);",
    "await writable.write(pgContent);",
)
print("  OK: 保存系を pgContent 参照に統一")

# ═══════════════════════════════════════════════════════
print("=== [5] 検索バー: onKeyDown から Enter 検索を完全削除、Esc のみ残す ===")
# 検索 input の onKeyDown ブロックを特定して置換
# パターン1: まだ古い実装が残っている場合
SEARCH_KD_PATTERNS = [
    # 初回Enter + 次へ移動の複合パターン
    "                  onKeyDown={e => {\n                    if (e.key === 'Enter' && !e.shiftKey && pgMatchPositions.length === 0 && pgEditorSearch) {",
    # goNextMatch ベースのパターン
    "                  onKeyDown={e => {\n                    if (e.key === 'Enter') {\n                      e.preventDefault();\n                      if (pgMatchPositions.length === 0) {",
    # scrollTop ベースのパターン（v3）
    "                  onKeyDown={e => {\n                    if (e.key === 'Enter' && pgMatchPositions.length > 0) {",
]

NEW_SEARCH_KD = """\
                  onKeyDown={e => {
                    if (e.key === 'Escape') {
                      setPgEditorSearch('');
                      setPgMatchCount(0);
                      setPgMatchPositions([]);
                      setPgMatchIndex(0);
                    }
                  }}"""

replaced_kd = False
for pattern in SEARCH_KD_PATTERNS:
    if pattern in src:
        # このパターンから始まる onKeyDown ブロックの終端 `}}` を探す
        start = src.find(pattern)
        # onKeyDown={e => { ... }} の終端を探す（ネスト考慮）
        depth = 0
        i = src.find("{", start + len("                  onKeyDown={e => "))
        end = i
        for j in range(i, min(i + 3000, len(src))):
            if src[j] == '{': depth += 1
            elif src[j] == '}':
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
        old_block = src[start:end]
        src = src[:start] + NEW_SEARCH_KD + src[end:]
        print(f"  OK: 検索 onKeyDown を Esc のみに置換")
        replaced_kd = True
        break

if not replaced_kd:
    if "Escape" in src and "setPgEditorSearch('');" in src:
        print("  OK: 検索 onKeyDown は既に正しい（Escのみ）")
    else:
        print("  WARN: 検索 onKeyDown 置換スキップ")

# ═══════════════════════════════════════════════════════
print("=== [6] 検索ボタンを handleSearchBtn に変更 ===")
OLD_SEARCH_BTN = 'onClick={() => execSearchQuery(pgEditorSearch, pgMatchPositions.length === 0)}'
NEW_SEARCH_BTN = 'onClick={handleSearchBtn}'
if OLD_SEARCH_BTN in src:
    src = src.replace(OLD_SEARCH_BTN, NEW_SEARCH_BTN, 1)
    print("  OK: 検索ボタン → handleSearchBtn")
else:
    print("  WARN: 検索ボタンアンカー不一致")

# ═══════════════════════════════════════════════════════
print("=== [7] ヘッダーに Undo/Redo ボタン + LIGHT/DARK 切り替えボタン追加 ===")
# 「✕ 閉じる」ボタンの前に挿入
OLD_CLOSE_BTN = """\
                <button onClick={() => setPgEditorOpen(false)}
                  className="px-3 py-1.5 text-xs font-bold bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg">
                  ✕ 閉じる
                </button>"""

NEW_CLOSE_BTN = """\
                <button onClick={pgUndo} title="Undo (Ctrl+Z)"
                  className="px-2.5 py-1.5 text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg border border-slate-300 disabled:opacity-40"
                  disabled={pgUndoStack.current.length === 0}>
                  ↩ Undo
                </button>
                <button onClick={pgRedo} title="Redo (Ctrl+Y)"
                  className="px-2.5 py-1.5 text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg border border-slate-300 disabled:opacity-40"
                  disabled={pgRedoStack.current.length === 0}>
                  ↪ Redo
                </button>
                <button onClick={() => setPgDarkMode(m => !m)} title="表示切替"
                  className={`px-2.5 py-1.5 text-xs font-bold rounded-lg border transition-colors ${
                    pgDarkMode
                      ? "bg-slate-700 hover:bg-slate-600 text-slate-200 border-slate-600"
                      : "bg-white hover:bg-slate-50 text-slate-700 border-slate-300"
                  }`}>
                  {pgDarkMode ? "☀ LIGHT" : "🌙 DARK"}
                </button>
                <button onClick={() => setPgEditorOpen(false)}
                  className="px-3 py-1.5 text-xs font-bold bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg">
                  ✕ 閉じる
                </button>"""

if OLD_CLOSE_BTN in src:
    src = src.replace(OLD_CLOSE_BTN, NEW_CLOSE_BTN, 1)
    print("  OK: Undo/Redo/DARK ボタン追加")
else:
    print("  WARN: 閉じるボタンアンカー不一致")

# ═══════════════════════════════════════════════════════
print("=== [8] ヒントテキスト更新 ===")
OLD_HINT = '<div className="ml-auto text-[10px] text-slate-400">Enter: 検索/次へ | Shift+Enter: 前へ | Esc: 解除 | Ctrl+Z: Undo | Ctrl+S: 保存</div>'
NEW_HINT = '<div className="ml-auto text-[10px] text-slate-400">Ctrl+Z: Undo | Ctrl+Y: Redo | Ctrl+S: 保存 | Esc: 検索解除</div>'
if OLD_HINT in src:
    src = src.replace(OLD_HINT, NEW_HINT, 1)
    print("  OK: ヒント更新")
else:
    # フォールバック
    src = src.replace(
        '>Enter: 次へ | Shift+Enter: 前へ | Ctrl+S: 保存</div>',
        '>Ctrl+Z: Undo | Ctrl+Y: Redo | Ctrl+S: 保存 | Esc: 検索解除</div>'
    )
    print("  OK: ヒント更新（フォールバック）")

# ═══════════════════════════════════════════════════════
print("=== [9] DARK/LIGHT に合わせてモーダル背景も変更 ===")
OLD_MODAL_BG = 'style={{width:"90vw", height:"95vh", maxWidth:"1400px"}}>'
NEW_MODAL_BG = 'style={{width:"90vw", height:"95vh", maxWidth:"1400px"}} className={pgDarkMode ? "bg-slate-900 rounded-2xl shadow-2xl flex flex-col" : "bg-white rounded-2xl shadow-2xl flex flex-col"}>'
# まずオリジナルのclassNameを探して削除してからstyleにclassNameを統合
OLD_MODAL_DIV = '<div className="bg-white rounded-2xl shadow-2xl flex flex-col" style={{width:"90vw", height:"95vh", maxWidth:"1400px"}}>'
NEW_MODAL_DIV = '<div style={{width:"90vw", height:"95vh", maxWidth:"1400px"}} className={`${pgDarkMode ? "bg-slate-900" : "bg-white"} rounded-2xl shadow-2xl flex flex-col`}>'
if OLD_MODAL_DIV in src:
    src = src.replace(OLD_MODAL_DIV, NEW_MODAL_DIV, 1)
    print("  OK: モーダル背景 DARK/LIGHT 対応")
else:
    print("  WARN: モーダル背景アンカー不一致")

# ── ヘッダー bg も切り替え ──
OLD_HEADER_BG = 'className="flex items-center justify-between px-5 py-3 border-b border-slate-200 bg-slate-50 rounded-t-2xl shrink-0">'
NEW_HEADER_BG = 'className={`flex items-center justify-between px-5 py-3 border-b shrink-0 rounded-t-2xl ${pgDarkMode ? "border-slate-700 bg-slate-800" : "border-slate-200 bg-slate-50"}`}>'
if OLD_HEADER_BG in src:
    src = src.replace(OLD_HEADER_BG, NEW_HEADER_BG, 1)
    print("  OK: ヘッダー背景 DARK/LIGHT 対応")

# ── 検索バー bg も切り替え ──
OLD_SEARCH_BAR = 'className="flex items-center gap-2 px-5 py-2 border-b border-slate-100 bg-slate-50 shrink-0">'
NEW_SEARCH_BAR = 'className={`flex items-center gap-2 px-5 py-2 border-b shrink-0 ${pgDarkMode ? "border-slate-700 bg-slate-800" : "border-slate-100 bg-slate-50"}`}>'
if OLD_SEARCH_BAR in src:
    src = src.replace(OLD_SEARCH_BAR, NEW_SEARCH_BAR, 1)
    print("  OK: 検索バー DARK/LIGHT 対応")

# ── フッター bg ──
OLD_FOOTER = 'className="px-5 py-2 border-t border-slate-200 bg-slate-50 rounded-b-2xl shrink-0 flex items-center gap-4 text-[10px] text-slate-400">'
NEW_FOOTER = 'className={`px-5 py-2 border-t rounded-b-2xl shrink-0 flex items-center gap-4 text-[10px] ${pgDarkMode ? "border-slate-700 bg-slate-800 text-slate-400" : "border-slate-200 bg-slate-50 text-slate-400"}`}>'
if OLD_FOOTER in src:
    src = src.replace(OLD_FOOTER, NEW_FOOTER, 1)
    print("  OK: フッター DARK/LIGHT 対応")

# ── ヘッダー テキスト色 ──
OLD_HDR_TEXT = '<span className="font-bold text-slate-800">PGエディタ</span>'
NEW_HDR_TEXT = '<span className={`font-bold ${pgDarkMode ? "text-slate-100" : "text-slate-800"}`}>PGエディタ</span>'
if OLD_HDR_TEXT in src:
    src = src.replace(OLD_HDR_TEXT, NEW_HDR_TEXT, 1)

write_file(EDIT, src)
print(f"\n  edit/page.tsx: {len(src)}文字")

# ═══════════════════════════════════════════════════════
print("\n=== [10] Next.js build ===")
rc = run("npx next build 2>&1 | tail -30", cwd=os.path.join(BASE, "apps/web"))
if rc != 0:
    print("  ❌ ビルドエラー")
    sys.exit(1)
print("  OK")

print("\n=== [11] PM2 再起動 ===")
run("pm2 restart machcore-web")
run("pm2 list --no-color | grep machcore")

print("\n=== [12] git push ===")
run("git add -A")
run('git commit -m "fix: PGエディタ完全再設計 - Undo/Redo/検索ハイライト/LIGHT-DARK切替"')
run("git push origin main")

for f in ["fix_pg_editor_v3.py", "fix_pg_editor_v4.py"]:
    p = os.path.join(BASE, f)
    if os.path.exists(p): os.remove(p); print(f"  cleaned: {f}")

print("\n=== 完了 ===")
