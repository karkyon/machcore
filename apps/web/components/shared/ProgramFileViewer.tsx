"use client";
import React, { useState, useEffect, useCallback, useRef } from "react";
import { agentPgToUsb, isAgentOnline } from "@/lib/upload-agent";

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
  const { system, programId, mode, token, onClose, onAuthRequired, onSaved } = props;

  const [fileList, setFileList] = useState<PgFile[]>([]);
  const [fileListLoading, setFileListLoading] = useState(false);
  const [activeFile, setActiveFile] = useState<PgFile | null>(null);
  const [content, setContent] = useState("");
  const [contentLoading, setContentLoading] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [usbBusy, setUsbBusy] = useState(false);
  const [darkMode, setDarkMode] = useState(false); // デフォルトLight
  const [search, setSearch] = useState("");
  const [replace, setReplace] = useState("");
  const [toast, setToast] = useState<string | null>(null);

  const undoStack = useRef<string[]>([]);
  const redoStack = useRef<string[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

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
    if (mode === "edit" && dirty && !window.confirm("編集中の内容が破棄されます。よろしいですか？")) return;
    setActiveFile(f);
    setContentLoading(true);
    undoStack.current = [];
    redoStack.current = [];
    setDirty(false);
    try {
      const res = await fetch(`${apiBase}/pg-files/${f.id}/content`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      const json = await res.json();
      setContent((json as any).content ?? "");
    } catch {
      setContent("(読み込みに失敗しました)");
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
      setDirty(false);
      showToast(`✅ 保存しました: ${activeFile.original_name}`);
      onSaved?.();
    } catch (e: any) {
      showToast(`❌ 保存に失敗しました: ${e?.message ?? ""}`);
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
    setDirty(true);
  };

  // ── 全置換(簡易) ──
  const handleReplaceAll = () => {
    if (mode !== "edit" || !search) return;
    const count = content.split(search).length - 1;
    if (count === 0) { showToast("見つかりません"); return; }
    pushUndo(content);
    setContent(content.split(search).join(replace));
    setDirty(true);
    showToast(`${count}件を全置換しました`);
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
        window.alert("UploadAgentが起動していません。タスクトレイを確認し、UploadAgentを起動してください。");
        return;
      }
      const res = await fetch(`${apiBase}/pg-to-usb-ticket`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`チケット発行失敗: HTTP ${res.status}`);
      const { ticket } = await res.json();
      const apiBaseUrl = window.location.origin + "/api";
      const result = await agentPgToUsb(ticket, apiBaseUrl);
      if (!result.success) {
        showToast(`❌ ${result.error ?? "USBへの書き出しに失敗しました"}`);
        return;
      }
      showToast(`✅ USBへ書き出しました（${result.copiedFiles.length}件）`);
    } catch (e: any) {
      showToast(`❌ ${e?.message ?? "USBへの書き出しに失敗しました"}`);
    } finally {
      setUsbBusy(false);
    }
  };

  // ── ディレクトリ別グルーピング(簡易ツリー) ──
  const groups: Record<string, PgFile[]> = {};
  fileList.forEach(f => {
    const parts = String(f.file_path ?? "").split("/").filter(Boolean);
    const dir = parts.length > 2 ? parts[parts.length - 2] : "";
    const key = dir || "（ルート）";
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
              {mode === "edit" ? "PGエディタ" : "PGビューア（参照専用）"}
              <span className="ml-1 text-xs font-normal text-slate-400">[{system.toUpperCase()}共通]</span>
            </span>
            {activeFile && (
              <span className={`text-xs font-mono px-2.5 py-1 rounded-lg border ${darkMode ? "text-slate-300 bg-slate-700 border-slate-600" : "text-slate-500 bg-slate-100 border-slate-200"}`}>
                {activeFile.original_name}
              </span>
            )}
            <span className="text-xs text-slate-400">{content.split("\n").length}行 / {content.length}文字</span>
          </div>
          <div className="flex items-center gap-2">
            {mode === "edit" && (
              <>
                <button onClick={handleSave} disabled={saving || !activeFile}
                  className="px-3 py-1.5 text-xs font-bold bg-teal-600 hover:bg-teal-700 text-white rounded-lg disabled:opacity-50">
                  {saving ? "⏳ 保存中..." : "✓ サーバに保存"}
                </button>
                <button onClick={handleUndo} disabled={undoStack.current.length === 0} title="Undo (Ctrl+Z)"
                  className="px-2.5 py-1.5 text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg border border-slate-300 disabled:opacity-40">↩</button>
                <button onClick={handleRedo} disabled={redoStack.current.length === 0} title="Redo (Ctrl+Y)"
                  className="px-2.5 py-1.5 text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg border border-slate-300 disabled:opacity-40">↪</button>
              </>
            )}
            <button onClick={handleUsbExport} disabled={usbBusy}
              className="px-3 py-1.5 text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white rounded-lg disabled:opacity-50">
              {usbBusy ? "⏳ 書き出し中..." : "💾 USBへ書き出し(UA経由)"}
            </button>
            <button onClick={() => setDarkMode(m => !m)} title="表示切替"
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
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="検索"
            className={`text-xs font-mono px-2 py-1 rounded border w-40 ${darkMode ? "bg-slate-900 text-slate-200 border-slate-600" : "bg-white text-slate-700 border-slate-300"}`} />
          {mode === "edit" && (
            <>
              <input value={replace} onChange={e => setReplace(e.target.value)} placeholder="置換後"
                className={`text-xs font-mono px-2 py-1 rounded border w-40 ${darkMode ? "bg-slate-900 text-slate-200 border-slate-600" : "bg-white text-slate-700 border-slate-300"}`} />
              <button onClick={handleReplaceAll} className="px-3 py-1 text-xs bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-bold">全置換</button>
            </>
          )}
          <div className="ml-auto text-[10px] text-slate-400">
            {mode === "edit" ? "Ctrl+S: 保存" : "参照専用（編集はできません）"}
          </div>
        </div>

        {/* 本体: ツリー + テキストエリア */}
        <div className="flex flex-1 min-h-0">
          {fileList.length > 1 && (
            <div className={`w-60 shrink-0 border-r overflow-y-auto py-1 ${sidebarBg}`}>
              {fileListLoading ? (
                <div className="p-3 text-[11px] text-slate-400">読込中...</div>
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
              <div className="flex items-center justify-center h-full text-xs text-slate-400">読込中...</div>
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
              <span>💡 Ctrl+S: サーバ保存</span>
              <span>|</span>
              <span>💾 USBへ書き出し: UploadAgent経由で設定済みUSBドライブへ直接コピー</span>
            </>
          ) : (
            <span>👁 参照専用モード（内容の編集・保存はできません）</span>
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
