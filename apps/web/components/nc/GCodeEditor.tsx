"use client";
import { useEffect, useRef, useCallback, useState } from "react";
import { EditorView, lineNumbers, highlightActiveLine, keymap, drawSelection, rectangularSelection } from "@codemirror/view";
import { EditorState, Compartment } from "@codemirror/state";
import { history, historyKeymap, defaultKeymap, undo, redo } from "@codemirror/commands";
import {
  search, searchKeymap,
  findNext, findPrevious, replaceNext, replaceAll,
  openSearchPanel, closeSearchPanel,
  gotoLine,
  getSearchQuery, setSearchQuery, SearchQuery,
} from "@codemirror/search";
import { StreamLanguage } from "@codemirror/language";

// ── Gコード言語定義 ─────────────────────────────────────────
const gcodeLanguage = StreamLanguage.define({
  token(stream) {
    if (stream.match(/\([^)]*\)/)) return "comment";
    if (stream.match(/\bO\d+/))          return "keyword";
    if (stream.match(/\bN\d+/))          return "number";
    if (stream.match(/\bG\d+(\.\d+)?/))  return "string";
    if (stream.match(/\bM\d+/))          return "atom";
    if (stream.match(/\bT\d+/))          return "variableName";
    if (stream.match(/^%/))              return "keyword";
    stream.next();
    return null;
  },
});

// ── テーマ ────────────────────────────────────────────────────
const gcodeTheme = EditorView.theme({
  "&": { fontSize: "13px", fontFamily: "'Consolas','Monaco',monospace", height: "100%" },
  ".cm-scroller": { overflow: "auto", height: "100%" },
  ".cm-content": { padding: "4px 0", minHeight: "100%" },
  ".cm-gutters": { background: "#0f172a", borderRight: "1px solid #1e293b", color: "#334155" },
  ".cm-lineNumbers .cm-gutterElement": { padding: "0 8px 0 12px", minWidth: "44px" },
  ".cm-activeLineGutter": { background: "#1e293b" },
  ".cm-activeLine": { background: "#0f2942" },
  ".cm-selectionBackground, &.cm-focused .cm-selectionBackground": { background: "#1e40af88" },
  ".cm-cursor": { borderLeftColor: "#38bdf8" },
  ".tok-comment":      { color: "#94a3b8", fontStyle: "italic" },
  ".tok-keyword":      { color: "#a78bfa", fontWeight: "bold" },
  ".tok-number":       { color: "#64748b" },
  ".tok-string":       { color: "#38bdf8", fontWeight: "bold" },
  ".tok-atom":         { color: "#f87171", fontWeight: "bold" },
  ".tok-variableName": { color: "#fbbf24" },
  // 検索パネル非表示（独自UIで制御）
  ".cm-search": { display: "none" },
});

const darkBg = EditorView.theme({
  "&": { background: "#0f172a", color: "#e2e8f0" },
});

type Props = {
  content: string;
  encoding: string;
  lineEnding: string;
  readOnly?: boolean;
  dirty?: boolean;
  saving?: boolean;
  onChange?: (val: string) => void;
  onSave?: () => void;
};

export default function GCodeEditor({
  content, encoding, lineEnding,
  readOnly = false, dirty = false, saving = false,
  onChange, onSave,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef      = useRef<EditorView | null>(null);
  const wrapComp     = useRef(new Compartment());
  const roComp       = useRef(new Compartment());
  const wrapOn       = useRef(false);

  // カーソル位置
  const [pos, setPos] = useState({ line: 1, col: 1, total: 1 });

  // 検索バー表示
  const [findOpen,    setFindOpen]    = useState(false);
  const [replaceOpen, setReplaceOpen] = useState(false);
  const [findQuery,   setFindQuery]   = useState("");
  const [replaceStr,  setReplaceStr]  = useState("");
  const [caseSens,    setCaseSens]    = useState(false);
  const [useRegex,    setUseRegex]    = useState(false);
  const [matchCount,  setMatchCount]  = useState<string>("");

  // ── エディタ初期化 ──────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;

    const updateListener = EditorView.updateListener.of(update => {
      if (update.docChanged) {
        onChange?.(update.state.doc.toString());
      }
      // カーソル位置更新
      const sel = update.state.selection.main;
      const line = update.state.doc.lineAt(sel.head);
      setPos({
        line: line.number,
        col: sel.head - line.from + 1,
        total: update.state.doc.lines,
      });
    });

    const saveKey = keymap.of([
      { key: "Mod-s", run: () => { onSave?.(); return true; } },
      { key: "Mod-g", run: (v) => { gotoLine(v); return true; } },
    ]);

    const state = EditorState.create({
      doc: content,
      extensions: [
        lineNumbers(),
        highlightActiveLine(),
        drawSelection(),
        history(),
        gcodeLanguage,
        gcodeTheme,
        darkBg,
        search(),
        keymap.of([...defaultKeymap, ...historyKeymap, ...searchKeymap]),
        saveKey,
        wrapComp.current.of([]),
        rectangularSelection(),
        roComp.current.of(EditorState.readOnly.of(readOnly)),
        updateListener,
      ],
    });

    const view = new EditorView({ state, parent: containerRef.current });
    viewRef.current = view;
    setPos({ line: 1, col: 1, total: state.doc.lines });

    return () => { view.destroy(); viewRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // content 外部変更反映
  const prevContent = useRef(content);
  useEffect(() => {
    const view = viewRef.current;
    if (!view || content === prevContent.current) return;
    prevContent.current = content;
    const cur = view.state.doc.toString();
    if (cur !== content) {
      view.dispatch({ changes: { from: 0, to: cur.length, insert: content } });
    }
  }, [content]);

  // readOnly 変更
  useEffect(() => {
    viewRef.current?.dispatch({
      effects: roComp.current.reconfigure(EditorState.readOnly.of(readOnly)),
    });
  }, [readOnly]);

  // 折り返し切替
  const toggleWrap = useCallback(() => {
    wrapOn.current = !wrapOn.current;
    viewRef.current?.dispatch({
      effects: wrapComp.current.reconfigure(
        wrapOn.current ? EditorView.lineWrapping : [],
      ),
    });
  }, []);

  // 行へ移動
  const handleGotoLine = useCallback(() => {
    const view = viewRef.current;
    if (!view) return;
    const n = prompt("移動する行番号:");
    if (!n || isNaN(Number(n))) return;
    const lineNo = Math.max(1, Math.min(Number(n), view.state.doc.lines));
    const line = view.state.doc.line(lineNo);
    view.dispatch({ selection: { anchor: line.from }, scrollIntoView: true });
    view.focus();
  }, []);

  // 検索バー開閉
  const openFind = useCallback(() => {
    setFindOpen(true);
    setReplaceOpen(false);
    setMatchCount("");
    setTimeout(() => (document.getElementById("gce-find-input") as HTMLInputElement)?.focus(), 50);
  }, []);

  const openReplace = useCallback(() => {
    setFindOpen(true);
    setReplaceOpen(true);
    setMatchCount("");
    setTimeout(() => (document.getElementById("gce-find-input") as HTMLInputElement)?.focus(), 50);
  }, []);

  const closeFind = useCallback(() => {
    setFindOpen(false);
    setReplaceOpen(false);
    setMatchCount("");
    viewRef.current?.focus();
  }, []);

  // 検索クエリをエディタに同期
  const syncQuery = useCallback((q: string, cs: boolean, rx: boolean) => {
    const view = viewRef.current;
    if (!view || !q) return;
    try {
      view.dispatch({
        effects: setSearchQuery.of(new SearchQuery({
          search: q,
          caseSensitive: cs,
          regexp: rx,
          replace: replaceStr,
        })),
      });
    } catch {}
  }, [replaceStr]);

  const handleFindNext = useCallback(() => {
    const view = viewRef.current;
    if (!view || !findQuery) return;
    syncQuery(findQuery, caseSens, useRegex);
    findNext(view);
    updateMatchCount(findQuery, caseSens, useRegex);
  }, [findQuery, caseSens, useRegex, syncQuery]);

  const handleFindPrev = useCallback(() => {
    const view = viewRef.current;
    if (!view || !findQuery) return;
    syncQuery(findQuery, caseSens, useRegex);
    findPrevious(view);
    updateMatchCount(findQuery, caseSens, useRegex);
  }, [findQuery, caseSens, useRegex, syncQuery]);

  const updateMatchCount = useCallback((q: string, cs: boolean, rx: boolean) => {
    const view = viewRef.current;
    if (!view || !q) { setMatchCount(""); return; }
    try {
      const text = view.state.doc.toString();
      let count = 0;
      if (rx) {
        const flags = cs ? "g" : "gi";
        count = (text.match(new RegExp(q, flags)) || []).length;
      } else {
        const haystack = cs ? text : text.toLowerCase();
        const needle   = cs ? q    : q.toLowerCase();
        let idx = 0;
        while ((idx = haystack.indexOf(needle, idx)) !== -1) { count++; idx += needle.length; }
      }
      setMatchCount(count === 0 ? "見つかりません" : `${count}件`);
    } catch { setMatchCount(""); }
  }, []);

  const handleReplaceOne = useCallback(() => {
    const view = viewRef.current;
    if (!view || !findQuery) return;
    view.dispatch({
      effects: setSearchQuery.of(new SearchQuery({
        search: findQuery, caseSensitive: caseSens, regexp: useRegex, replace: replaceStr,
      })),
    });
    replaceNext(view);
    updateMatchCount(findQuery, caseSens, useRegex);
  }, [findQuery, replaceStr, caseSens, useRegex, updateMatchCount]);

  const handleReplaceAll = useCallback(() => {
    const view = viewRef.current;
    if (!view || !findQuery) return;
    view.dispatch({
      effects: setSearchQuery.of(new SearchQuery({
        search: findQuery, caseSensitive: caseSens, regexp: useRegex, replace: replaceStr,
      })),
    });
    replaceAll(view);
    updateMatchCount(findQuery, caseSens, useRegex);
  }, [findQuery, replaceStr, caseSens, useRegex, updateMatchCount]);

  // キーボードショートカット（バー上）
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter") { handleFindNext(); }
    if (e.key === "Escape") { closeFind(); }
  }, [handleFindNext, closeFind]);

  // ── ボタンスタイル ─────────────────────────────────────
  const btnCls = "px-2 py-1 text-xs text-slate-300 hover:text-white hover:bg-slate-600 rounded transition-colors whitespace-nowrap";
  const sepCls = "border-r border-slate-600 mx-1 self-stretch";

  return (
    <div className="flex flex-col h-full border border-slate-700 rounded-lg overflow-hidden" style={{ background: "#0f172a" }}>

      {/* ── メニューバー ───────────────────────────────── */}
      <div className="flex items-center flex-wrap gap-0 px-2 py-1 shrink-0"
        style={{ background: "#162032", borderBottom: "1px solid #1e40af" }}>

        {/* ファイル */}
        <div className="flex items-center">
          <button onClick={onSave} disabled={readOnly || saving}
            className={`${btnCls} ${dirty ? "text-amber-400 font-bold" : ""}`}
            title="上書き保存 (Ctrl+S)">
            💾 保存
          </button>
        </div>
        <div className={sepCls} />

        {/* 編集 */}
        <div className="flex items-center">
          <button onClick={() => viewRef.current && undo(viewRef.current)} disabled={readOnly}
            className={btnCls} title="元に戻す (Ctrl+Z)">↩ 元に戻す</button>
          <button onClick={() => viewRef.current && redo(viewRef.current)} disabled={readOnly}
            className={btnCls} title="やり直し (Ctrl+Y)">↪ やり直し</button>
        </div>
        <div className={sepCls} />

        {/* 検索・置換 */}
        <div className="flex items-center">
          <button onClick={openFind}    className={`${btnCls} ${findOpen && !replaceOpen ? "text-sky-400" : ""}`}
            title="検索 (Ctrl+F)">🔍 検索</button>
          <button onClick={openReplace} className={`${btnCls} ${replaceOpen ? "text-sky-400" : ""}`}
            title="置換 (Ctrl+H)">🔄 置換</button>
        </div>
        <div className={sepCls} />

        {/* 表示 */}
        <div className="flex items-center">
          <button onClick={toggleWrap} className={btnCls} title="折り返し切替">
            ↵ 折返:{wrapOn.current ? "ON" : "OFF"}
          </button>
          <button onClick={handleGotoLine} className={btnCls} title="行へ移動 (Ctrl+G)">
            # 行移動
          </button>
        </div>

        {/* 右端: ステータス */}
        <div className="flex-1" />
        <div className="flex items-center gap-2 pr-1">
          {saving && <span className="text-xs text-sky-400">保存中…</span>}
          {dirty && !saving && <span className="text-xs text-amber-400 font-bold">● 未保存</span>}
          <span className="text-[11px] text-slate-500 font-mono">
            行:{pos.line} / 列:{pos.col} / 全{pos.total}行
          </span>
          <span className="text-[11px] bg-slate-700 text-slate-300 px-1.5 rounded">{encoding}</span>
          <span className="text-[11px] bg-slate-700 text-slate-300 px-1.5 rounded">{lineEnding}</span>
        </div>
      </div>

      {/* ── 検索バー ───────────────────────────────────── */}
      {findOpen && (
        <div className="shrink-0 px-3 py-2" style={{ background: "#162032", borderBottom: "1px solid #1e3a5f" }}>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-slate-400">検索:</span>
            <input
              id="gce-find-input"
              type="text"
              value={findQuery}
              onChange={e => { setFindQuery(e.target.value); updateMatchCount(e.target.value, caseSens, useRegex); }}
              onKeyDown={handleKeyDown}
              placeholder="検索する文字列"
              className="text-xs px-2 py-1 rounded font-mono"
              style={{ background:"#0f172a", color:"#e2e8f0", border:"1px solid #334155", width:"180px", outline:"none" }}
            />
            <label className="flex items-center gap-1 text-xs text-slate-400 cursor-pointer">
              <input type="checkbox" checked={caseSens}
                onChange={e => { setCaseSens(e.target.checked); updateMatchCount(findQuery, e.target.checked, useRegex); }}
                className="accent-sky-500" />
              大小区別
            </label>
            <label className="flex items-center gap-1 text-xs text-slate-400 cursor-pointer">
              <input type="checkbox" checked={useRegex}
                onChange={e => { setUseRegex(e.target.checked); updateMatchCount(findQuery, caseSens, e.target.checked); }}
                className="accent-sky-500" />
              正規表現
            </label>
            <button onClick={handleFindNext} className={btnCls}>▶ 次を検索</button>
            <button onClick={handleFindPrev} className={btnCls}>◀ 前を検索</button>
            <span className="text-[11px] text-slate-400">{matchCount}</span>
            <button onClick={closeFind} className="ml-auto text-slate-500 hover:text-white text-xs">✕</button>
          </div>

          {/* 置換行 */}
          {replaceOpen && (
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              <span className="text-xs text-slate-400">置換:</span>
              <input
                type="text"
                value={replaceStr}
                onChange={e => setReplaceStr(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="置換後の文字列"
                className="text-xs px-2 py-1 rounded font-mono"
                style={{ background:"#0f172a", color:"#e2e8f0", border:"1px solid #334155", width:"180px", outline:"none" }}
              />
              <button onClick={handleReplaceOne} className={btnCls}>1件置換</button>
              <button onClick={handleReplaceAll} className={btnCls}>全て置換</button>
            </div>
          )}
        </div>
      )}

      {/* ── CodeMirror 本体 ─────────────────────────────── */}
      <div ref={containerRef} className="flex-1 overflow-hidden" style={{ minHeight: 0 }} />
    </div>
  );
}
