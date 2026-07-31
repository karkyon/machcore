"use client";
import React, { useState, useEffect, useCallback, useRef } from "react";
import { agentPgToUsb, isAgentOnline, translateAgentError } from "@/lib/upload-agent";
import { useLanguage } from "@/lib/i18n/LanguageContext";

/**
 * ProgramFileViewer — MC/NC共通・参照/編集共通のプログラムファイル表示・編集コンポーネント。
 *
 * [v076] 新規作成(第1段階)。既存の mc/edit(PGエディタ)・mc/page(PGビューア)・
 * nc/edit・nc/page はまだこのコンポーネントを呼んでいない(次回接続)。
 *
 * - system: "mc" | "nc"  … APIパス /api/{system}/{programId}/... を切り替える
 * - mode:   "view" | "edit"
 *     view: 読み取り専用。保存不可。「USBへ書き出し」はUAチケット経由。
 *     edit: 保存可能(Ctrl+S / 保存ボタン)。pg-files/:id/content へPUT。
 * - 左側にフォルダ単位(複数ファイル)の場合のディレクトリ別ツリーサイドバーを表示。
 * - デフォルトLightモード。ダーク/ライト切替あり。
 */

export type ProgramFileViewerProps = {
  system: "mc" | "nc";
  programId: number;
  mode: "view" | "edit";
  token?: string | null;
  onClose: () => void;
  onAuthRequired?: () => void;
  onSaved?: () => void;
};

type PgFile = {
  id: number;
  original_name: string;
  file_path?: string;
  pg_role?: string;
};

export default function ProgramFileViewer(props: ProgramFileViewerProps) {
  const { t: tr } = useLanguage();
  const { system, programId, mode, token, onClose, onAuthRequired, onSaved } = props;

  const [fileList, setFileList] = useState<PgFile[]>([]);
  const [fileListLoading, setFileListLoading] = useState(false);
  const [activeFile, setActiveFile] = useState<PgFile | null>(null);
  const [content, setContent] = useState("");
  const [contentLoading, setContentLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [usbBusy, setUsbBusy] = useState(false);
  const [darkMode, setDarkMode] = useState(false); // デフォルトLight
  const [search, setSearch] = useState("");
  const [replace, setReplace] = useState("");
  const [matchPositions, setMatchPositions] = useState<number[]>([]);
  const [currentMatchIdx, setCurrentMatchIdx] = useState(-1);
  const [toast, setToast] = useState<string | null>(null);

  const undoStack = useRef<string[]>([]);
  const redoStack = useRef<string[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  // [FIX] dirtyは「現在のcontentが最後に読み込み/保存した内容と異なるか」で
  // 都度算出する。useStateで手動管理していた際は、Undoで編集前の内容に
  // ちょうど戻した場合でもdirty=trueのまま残ってしまう不具合があった。
  const savedContentRef = useRef<string>("");
  const dirty = content !== savedContentRef.current;

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  }, []);

  const apiBase = `/api/${system}/${programId}`;

  // ── ファイル一覧取得 ──
  const loadFileList = useCallback(async () => {
    setFileListLoading(true);
    try {
      const res = await fetch(`${apiBase}/pg-files-list`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      const json = await res.json();
      const list: PgFile[] = (json as any).data ?? json ?? [];
      setFileList(Array.isArray(list) ? list : []);
      if (Array.isArray(list) && list.length > 0) {
        selectFile(list[0]);
      }
    } catch {
      setFileList([]);
    } finally {
      setFileListLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase, token]);

  useEffect(() => {
    loadFileList();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [system, programId]);

  // ── ファイル選択 ──
  const selectFile = useCallback(async (f: PgFile) => {
    if (mode === "edit" && dirty && !window.confirm(tr("programFileViewer.discardConfirm","編集中の内容が破棄されます。よろしいですか？"))) return;
    setActiveFile(f);
    setContentLoading(true);
    undoStack.current = [];
    redoStack.current = [];
    try {
      const res = await fetch(`${apiBase}/pg-files/${f.id}/content`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      const json = await res.json();
      const loaded = (json as any).content ?? "";
      setContent(loaded);
      savedContentRef.current = loaded;
    } catch {
      setContent(tr("programFileViewer.loadFailedContent","(読み込みに失敗しました)"));
      savedContentRef.current = tr("programFileViewer.loadFailedContent","(読み込みに失敗しました)");
    } finally {
      setContentLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase, token, mode, dirty]);

  // ── 保存(editモードのみ) ──
  const handleSave = useCallback(async () => {
    if (mode !== "edit" || !activeFile) return;
    if (!token) { onAuthRequired?.(); return; }
    setSaving(true);
    try {
      const res = await fetch(`${apiBase}/pg-files/${activeFile.id}/content`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ content }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      savedContentRef.current = content;
      showToast(tr("programFileViewer.saveSuccessMsg","✅ 保存しました: {name}").replace("{name}", activeFile.original_name));
      onSaved?.();
    } catch (e: any) {
      showToast(tr("programFileViewer.saveFailedMsg","❌ 保存に失敗しました: {msg}").replace("{msg}", e?.message ?? ""));
    } finally {
      setSaving(false);
    }
  }, [mode, activeFile, token, apiBase, content, onAuthRequired, onSaved, showToast]);

  // ── Undo/Redo ──
  const pushUndo = useCallback((prev: string) => {
    undoStack.current.push(prev);
    if (undoStack.current.length > 200) undoStack.current.shift();
    redoStack.current = [];
  }, []);
  const handleUndo = useCallback(() => {
    if (undoStack.current.length === 0) return;
    redoStack.current.push(content);
    const prev = undoStack.current.pop()!;
    setContent(prev);
  }, [content]);
  const handleRedo = useCallback(() => {
    if (redoStack.current.length === 0) return;
    undoStack.current.push(content);
    const next = redoStack.current.pop()!;
    setContent(next);
  }, [content]);

  const handleChange = (v: string) => {
    if (mode !== "edit") return;
    pushUndo(content);
    setContent(v);
  };

  // ── 検索(マッチ箇所へジャンプ・選択・循環移動) ──
  const selectMatch = useCallback((idx: number, positions: number[]) => {
    if (idx < 0 || idx >= positions.length || !search) return;
    const start = positions[idx];
    const end = start + search.length;
    const ta = textareaRef.current;
    if (ta) {
      ta.focus();
      ta.setSelectionRange(start, end);
      const before = content.slice(0, start);
      const lineNo = before.split("\n").length;
      const lineHeight = 20;
      ta.scrollTop = Math.max(0, (lineNo - 5) * lineHeight);
    }
    setCurrentMatchIdx(idx);
  }, [search, content]);

  const handleSearch = useCallback(() => {
    if (!search) { showToast(tr("programFileViewer.inputSearchKeyword","検索キーワードを入力してください")); return; }
    const positions: number[] = [];
    let idx = content.indexOf(search);
    while (idx !== -1) {
      positions.push(idx);
      idx = content.indexOf(search, idx + search.length);
    }
    if (positions.length === 0) {
      setMatchPositions([]);
      setCurrentMatchIdx(-1);
      showToast(tr("programFileViewer.notFound","見つかりません"));
      return;
    }
    const sameSearch = positions.length === matchPositions.length &&
      positions.every((p, i) => p === matchPositions[i]);
    const nextIdx = sameSearch && currentMatchIdx >= 0
      ? (currentMatchIdx + 1) % positions.length
      : 0;
    setMatchPositions(positions);
    selectMatch(nextIdx, positions);
  }, [search, content, matchPositions, currentMatchIdx, selectMatch, showToast]);

  const handleReplaceOne = () => {
    if (mode !== "edit") return;
    if (currentMatchIdx < 0 || matchPositions.length === 0) {
      showToast(tr("programFileViewer.searchFirst","先に検索してください"));
      return;
    }
    const start = matchPositions[currentMatchIdx];
    const end = start + search.length;
    pushUndo(content);
    const newContent = content.slice(0, start) + replace + content.slice(end);
    setContent(newContent);
    showToast(tr("programFileViewer.oneReplacedMsg","1件置換しました"));
    setMatchPositions([]);
    setCurrentMatchIdx(-1);
  };

  // ── 全置換(簡易) ──
  const handleReplaceAll = () => {
    if (mode !== "edit" || !search) return;
    const count = content.split(search).length - 1;
    if (count === 0) { showToast(tr("programFileViewer.notFound","見つかりません")); return; }
    pushUndo(content);
    setContent(content.split(search).join(replace));
    setMatchPositions([]);
    setCurrentMatchIdx(-1);
    showToast(tr("programFileViewer.allReplacedMsg","{n}件を全置換しました").replace("{n}", String(count)));
  };

  // ── Ctrl+S ──
  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "s") {
      e.preventDefault();
      handleSave();
    }
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key === "z") { e.preventDefault(); handleUndo(); }
    if ((e.ctrlKey || e.metaKey) && (e.key === "y" || (e.shiftKey && e.key === "z"))) { e.preventDefault(); handleRedo(); }
  };

  // ── USBへ書き出し(UAチケット経由) ──
  const handleUsbExport = async () => {
    if (!token) { onAuthRequired?.(); return; }
    setUsbBusy(true);
    try {
      const online = await isAgentOnline();
      if (!online) {
        window.alert(tr("programFileViewer.agentNotRunningAlert2","UploadAgentが起動していません。タスクトレイを確認し、UploadAgentを起動してください。"));
        return;
      }
      const res = await fetch(`${apiBase}/pg-to-usb-ticket`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(tr("programFileViewer.ticketIssueFailedHttp2","チケット発行失敗: HTTP {status}").replace("{status}", String(res.status)));
      const { ticket } = await res.json();
      const apiBaseUrl = window.location.origin + "/api";
      // [v116] system("mc"/"nc")を必ずAgentへ渡す。渡さないとNC側のPG→USBが
      // 常にMC用エンドポイントへ問い合わせて404になるバグがあったため修正。
      const result = await agentPgToUsb(ticket, apiBaseUrl, system);
      if (!result.success) {
        const fallback = result.error ?? tr("programFileViewer.usbExportFailedLabel2","USBへの書き出しに失敗しました");
        showToast(`❌ ${translateAgentError(tr, result.errorCode, result.errorParams, fallback) ?? fallback}`);
        return;
      }
      showToast(tr("programFileViewer.usbExportSuccessLabel2","✅ USBへ書き出しました（{n}件）").replace("{n}", String(result.copiedFiles.length)));
    } catch (e: any) {
      showToast(`❌ ${e?.message ?? tr("programFileViewer.usbExportFailedLabel2","USBへの書き出しに失敗しました")}`);
    } finally {
      setUsbBusy(false);
    }
  };

  // ── ディレクトリ別グルーピング(簡易ツリー) ──
  const groups: Record<string, PgFile[]> = {};
  fileList.forEach(f => {
    const parts = String(f.file_path ?? "").split("/").filter(Boolean);
    const dir = parts.length > 2 ? parts[parts.length - 2] : "";
    const key = dir || tr("programFileViewer.rootFolderLabel2","（ルート）");
    (groups[key] = groups[key] ?? []).push(f);
  });

  const bg = darkMode ? "bg-slate-900" : "bg-white";
  const headerBg = darkMode ? "border-slate-700 bg-slate-800" : "border-slate-200 bg-slate-50";
  const sidebarBg = darkMode ? "border-slate-700 bg-slate-800" : "border-slate-200 bg-slate-50";
  const textareaCls = darkMode
    ? "text-green-300 bg-slate-900"
    : "text-slate-800 bg-white border border-slate-200";

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-2">
      <div style={{ width: "90vw", height: "95vh", maxWidth: "1400px" }} className={`${bg} rounded-2xl shadow-2xl flex flex-col`}>
        {/* ヘッダー */}
        <div className={`flex items-center justify-between px-5 py-3 border-b shrink-0 rounded-t-2xl ${headerBg}`}>
          <div className="flex items-center gap-3">
            <span className="text-slate-400 text-lg">📄</span>
            <span className={`font-bold ${darkMode ? "text-slate-100" : "text-slate-800"}`}>
              {mode === "edit" ? tr("programFileViewer.editorTitle", "PGエディタ") : tr("programFileViewer.viewerTitle", "PGビューア（参照専用）")}
              <span className="ml-1 text-xs font-normal text-slate-400">[{system.toUpperCase()}{tr("programFileViewer.commonSuffix", "共通")}]</span>
            </span>
            {activeFile && (
              <span className={`text-xs font-mono px-2.5 py-1 rounded-lg border ${darkMode ? "text-slate-300 bg-slate-700 border-slate-600" : "text-slate-500 bg-slate-100 border-slate-200"}`}>
                {activeFile.original_name}
              </span>
            )}
            <span className="text-xs text-slate-400">{tr("programFileViewer.lineCharCountLabel2", "{lines}行 / {chars}文字").replace("{lines}", String(content.split("\n").length)).replace("{chars}", String(content.length))}</span>
          </div>
          <div className="flex items-center gap-2">
            {mode === "edit" && (
              <>
                <button onClick={handleSave} disabled={saving || !activeFile || !dirty}
                  className="px-3 py-1.5 text-xs font-bold bg-teal-600 hover:bg-teal-700 text-white rounded-lg disabled:opacity-50">
                  {saving ? tr("programFileViewer.savingLabel", "⏳ 保存中...") : tr("programFileViewer.saveToServerButton", "✓ サーバに保存")}
                </button>
                <button onClick={handleUndo} disabled={undoStack.current.length === 0} title="Undo (Ctrl+Z)"
                  className="px-2.5 py-1.5 text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg border border-slate-300 disabled:opacity-40">↩</button>
                <button onClick={handleRedo} disabled={redoStack.current.length === 0} title="Redo (Ctrl+Y)"
                  className="px-2.5 py-1.5 text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg border border-slate-300 disabled:opacity-40">↪</button>
              </>
            )}
            <button onClick={handleUsbExport} disabled={usbBusy}
              className="px-3 py-1.5 text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white rounded-lg disabled:opacity-50">
              {usbBusy ? tr("programFileViewer.exportingLabel2", "⏳ 書き出し中...") : tr("programFileViewer.exportToUsbLabel2", "💾 USBへ書き出し(UA経由)")}
            </button>
            <button onClick={() => setDarkMode(m => !m)} title={tr("programFileViewer.displayToggleTitle", "表示切替")}
              className={`px-2.5 py-1.5 text-xs font-bold rounded-lg border transition-colors ${
                darkMode ? "bg-slate-700 hover:bg-slate-600 text-slate-200 border-slate-600" : "bg-white hover:bg-slate-50 text-slate-700 border-slate-300"
              }`}>
              {darkMode ? "☀" : "🌙"}
            </button>
            <button onClick={onClose} className="px-2.5 py-1.5 text-sm font-bold bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg">✕</button>
          </div>
        </div>

        {/* 検索・置換バー(editモードのみ全置換可) */}
        <div className={`flex items-center gap-2 px-5 py-2 border-b shrink-0 ${darkMode ? "border-slate-700 bg-slate-800" : "border-slate-200 bg-slate-50"}`}>
          <input value={search}
            onChange={e => { setSearch(e.target.value); setMatchPositions([]); setCurrentMatchIdx(-1); }}
            onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); handleSearch(); } }}
            placeholder={tr("programFileViewer.searchPlaceholder", "検索")}
            className={`text-xs font-mono px-2 py-1 rounded border w-40 ${darkMode ? "bg-slate-900 text-slate-200 border-slate-600" : "bg-white text-slate-700 border-slate-300"}`} />
          <button onClick={handleSearch} className="px-3 py-1 text-xs bg-slate-500 hover:bg-slate-600 text-white rounded-lg font-bold">{tr("programFileViewer.searchButton2", "検索")}</button>
          {matchPositions.length > 0 && (
            <span className="text-[10px] text-slate-400 whitespace-nowrap">{tr("programFileViewer.matchCountLabel", "{cur} / {total}件").replace("{cur}", String(currentMatchIdx + 1)).replace("{total}", String(matchPositions.length))}</span>
          )}
          {mode === "edit" && (
            <>
              <input value={replace} onChange={e => setReplace(e.target.value)} placeholder={tr("programFileViewer.replacePlaceholder", "置換後")}
                className={`text-xs font-mono px-2 py-1 rounded border w-40 ${darkMode ? "bg-slate-900 text-slate-200 border-slate-600" : "bg-white text-slate-700 border-slate-300"}`} />
              <button onClick={handleReplaceOne} className="px-3 py-1 text-xs bg-indigo-500 hover:bg-indigo-600 text-white rounded-lg font-bold">{tr("programFileViewer.replaceButton", "置換")}</button>
              <button onClick={handleReplaceAll} className="px-3 py-1 text-xs bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-bold">{tr("programFileViewer.replaceAllButton", "全置換")}</button>
            </>
          )}
          <div className="ml-auto text-[10px] text-slate-400">
            {mode === "edit" ? tr("programFileViewer.editModeHint", "Ctrl+S: 保存 / Enter: 検索") : tr("programFileViewer.viewModeHint", "参照専用（編集はできません）")}
          </div>
        </div>

        {/* 本体: ツリー + テキストエリア */}
        <div className="flex flex-1 min-h-0">
          {fileList.length > 1 && (
            <div className={`w-60 shrink-0 border-r overflow-y-auto py-1 ${sidebarBg}`}>
              {fileListLoading ? (
                <div className="p-3 text-[11px] text-slate-400">{tr("programFileViewer.loadingShort3", "読込中...")}</div>
              ) : Object.entries(groups).map(([dir, fs]) => (
                <div key={dir} className="mb-1">
                  <div className="px-3 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wide">📁 {dir}</div>
                  {fs.map(f => (
                    <button key={f.id} onClick={() => selectFile(f)}
                      className={"w-full text-left pl-6 pr-3 py-1.5 text-[11px] font-mono truncate " +
                        (activeFile?.id === f.id
                          ? "bg-teal-600 text-white font-bold"
                          : darkMode ? "text-slate-300 hover:bg-slate-700" : "text-slate-600 hover:bg-slate-100")}>
                      📄 {f.original_name}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}
          <div className="flex-1 overflow-hidden">
            {contentLoading ? (
              <div className="flex items-center justify-center h-full text-xs text-slate-400">{tr("programFileViewer.loadingShort3", "読込中...")}</div>
            ) : (
              <textarea
                ref={textareaRef}
                value={content}
                readOnly={mode !== "edit"}
                onChange={e => handleChange(e.target.value)}
                onKeyDown={onKeyDown}
                spellCheck={false}
                className={`w-full h-full p-5 font-mono text-sm resize-none focus:outline-none leading-relaxed ${textareaCls}`}
              />
            )}
          </div>
        </div>

        {/* フッター */}
        <div className={`px-5 py-2 border-t rounded-b-2xl shrink-0 flex items-center gap-4 text-[10px] ${darkMode ? "border-slate-700 bg-slate-800 text-slate-400" : "border-slate-200 bg-slate-50 text-slate-400"}`}>
          {mode === "edit" ? (
            <>
              <span>{tr("programFileViewer.footerSaveHint", "💡 Ctrl+S: サーバ保存")}</span>
              <span>|</span>
              <span>{tr("programFileViewer.footerUsbHint", "💾 USBへ書き出し: UploadAgent経由で設定済みUSBドライブへ直接コピー")}</span>
            </>
          ) : (
            <span>{tr("programFileViewer.footerViewOnlyHint", "👁 参照専用モード（内容の編集・保存はできません）")}</span>
          )}
        </div>
      </div>

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-bold z-[60]">
          {toast}
        </div>
      )}
    </div>
  );
}
